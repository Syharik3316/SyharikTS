import os
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.utils.helpers import (
    extract_typescript_code,
    looks_like_incomplete_typescript,
    ensure_json_object,
    best_match_key,
)


class LLMClient:
    def __init__(self) -> None:
        self.provider = (os.getenv("LLM_PROVIDER", "stub") or "stub").strip().lower()

    def generate_ts_code(
        self,
        *,
        prompt: str,
        extracted_input_json: Any,
        schema_obj: Any,
        interface_ts: str,
    ) -> str:
        if self.provider == "stub":
            return self._generate_stub_code(
                extracted_input_json=extracted_input_json,
                schema_obj=schema_obj,
                interface_ts=interface_ts,
            )

        if self.provider == "ollama":
            return self._generate_via_ollama(prompt)

        if self.provider == "openai_compatible":
            return self._generate_via_openai_compatible(prompt)

        if self.provider == "gigachat":
            return self._generate_via_gigachat(prompt)

        raise ValueError(f"Unsupported LLM_PROVIDER: {self.provider}")

    def _coerce_value(self, value: Any, example: Any) -> Any:
        # Use the *type* of the schema example to coerce values.
        if isinstance(example, bool):
            if isinstance(value, bool):
                return value
            s = str(value).strip().lower()
            return s in {"1", "true", "yes", "y"}

        if isinstance(example, (int, float)) and not isinstance(example, bool):
            try:
                s = str(value).strip().replace(",", ".")
                return float(s) if isinstance(example, float) else int(float(s))
            except Exception:
                return 0.0 if isinstance(example, float) else 0

        if value is None:
            return ""

        # Default: stringification.
        if isinstance(example, str):
            return str(value)

        # For null/objects/arrays we keep raw.
        return value

    def _generate_stub_code(self, *, extracted_input_json: Any, schema_obj: Any, interface_ts: str) -> str:
        schema = ensure_json_object(schema_obj)
        schema_keys = list(schema.keys())

        # Stub only maps structured rows (CSV/XLS converted to list[dict]).
        result: List[Dict[str, Any]] = []
        if isinstance(extracted_input_json, list) and extracted_input_json and isinstance(extracted_input_json[0], dict):
            for row in extracted_input_json:
                out: Dict[str, Any] = {}
                row_keys = list(row.keys())
                for k in schema_keys:
                    match = best_match_key(k, row_keys)
                    raw_val = row.get(match) if match else ""
                    out[k] = self._coerce_value(raw_val, schema.get(k))
                result.append(out)

        # Compact JSON in TS literal.
        result_json = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        return (
            f"{interface_ts}\n\n"
            "export default function (base64file: string): DealData[] {\n"
            f"  const result: DealData[] = {result_json} as any;\n"
            "  return result;\n"
            "}\n"
        )

    def _generate_via_ollama(self, prompt: str) -> str:
        from langchain_community.chat_models import ChatOllama
        from langchain_core.messages import HumanMessage

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "llama3")

        llm = ChatOllama(
            base_url=base_url,
            model=model,
            temperature=0,
        )
        msg = llm.invoke([HumanMessage(content=prompt)])
        return extract_typescript_code(msg.content or "")

    def _generate_via_openai_compatible(self, prompt: str) -> str:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage

        base_url = os.getenv("OPENAI_COMPAT_BASE_URL", "").strip()
        api_key = os.getenv("OPENAI_COMPAT_API_KEY", "").strip()
        model = os.getenv("OPENAI_COMPAT_MODEL", "").strip()

        if not base_url or not model:
            raise ValueError(
                "For openai_compatible set OPENAI_COMPAT_BASE_URL and OPENAI_COMPAT_MODEL (and optionally OPENAI_COMPAT_API_KEY)."
            )

        llm = ChatOpenAI(
            base_url=base_url,
            api_key=api_key or None,
            model=model,
            temperature=0,
        )
        msg = llm.invoke([HumanMessage(content=prompt)])
        return extract_typescript_code(msg.content or "")

    def _generate_via_gigachat(self, prompt: str) -> str:
        """
        GigaChat via Authorization key (OAuth) + REST chat completions.

        Реализует логику из ваших примеров:
          1) POST https://ngw.devices.sberbank.ru:9443/api/v2/oauth -> access_token
          2) POST {GIGACHAT_BASE_URL}/chat/completions -> content

        Для работы нужен минимум:
          - GIGACHAT_AUTHORIZATION_KEY (ключ авторизации; Basic base64 из личного кабинета)
          - GIGACHAT_MODEL (опционально; иначе используется дефолт)

        TLS: GigaChat иногда требует отключения проверки сертификатов из-за самоподписанных цепочек.
        Управляется через env `GIGACHAT_VERIFY_TLS` (по умолчанию `false`).
        """

        auth_key = (os.getenv("GIGACHAT_AUTHORIZATION_KEY") or "").strip()
        if not auth_key:
            raise ValueError("For gigachat set GIGACHAT_AUTHORIZATION_KEY.")

        base_url = (os.getenv("GIGACHAT_BASE_URL") or "https://gigachat.devices.sberbank.ru/api/v1").strip().rstrip("/")
        model = (os.getenv("GIGACHAT_MODEL") or "").strip() or "GigaChat-2-Max"

        verify_tls_env = (os.getenv("GIGACHAT_VERIFY_TLS") or "false").strip().lower()
        verify_tls = verify_tls_env in {"1", "true", "yes", "y", "on"}

        token, _expires_at = self._get_gigachat_access_token(auth_key=auth_key, verify_tls=verify_tls)

        chat_url = f"{base_url}/chat/completions"
        max_tokens = int((os.getenv("GIGACHAT_MAX_TOKENS") or "1400").strip() or "1400")
        timeout_sec = int((os.getenv("GIGACHAT_TIMEOUT_SECONDS") or "90").strip() or "90")

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0,
            "max_tokens": max_tokens,
            "n": 1,
            "repetition_penalty": 1,
            "update_interval": 0,
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        resp = requests.post(chat_url, headers=headers, json=payload, timeout=timeout_sec, verify=verify_tls)
        if resp.status_code != 200:
            try:
                body = resp.json()
            except Exception:
                body = None
            msg = ""
            if isinstance(body, dict):
                msg = body.get("error", {}).get("message") or body.get("message") or json.dumps(body)
            raise RuntimeError(f"GigaChat chat error {resp.status_code}: {msg or resp.text[:300]}")

        data = resp.json()
        content = ""
        if isinstance(data, dict):
            choices = data.get("choices") or []
            if choices and isinstance(choices, list):
                first = choices[0] or {}
                message = first.get("message") or {}
                content = message.get("content") or ""

        if not content:
            raise RuntimeError("GigaChat returned empty content")
        code = extract_typescript_code(content)

        # Retry once with stricter short instruction if output seems truncated.
        if looks_like_incomplete_typescript(code):
            retry_payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Previous output was truncated. Return FULL TypeScript code from start to end. "
                            "No markdown, no explanation.\n" + prompt
                        ),
                    }
                ],
                "stream": False,
                "temperature": 0,
                "max_tokens": max(max_tokens, 2200),
                "n": 1,
                "repetition_penalty": 1,
                "update_interval": 0,
            }
            retry_resp = requests.post(
                chat_url,
                headers=headers,
                json=retry_payload,
                timeout=max(timeout_sec, 120),
                verify=verify_tls,
            )
            if retry_resp.status_code == 200:
                retry_data = retry_resp.json()
                retry_content = ""
                if isinstance(retry_data, dict):
                    choices = retry_data.get("choices") or []
                    if choices and isinstance(choices, list):
                        retry_content = ((choices[0] or {}).get("message") or {}).get("content") or ""
                if retry_content:
                    code_retry = extract_typescript_code(retry_content)
                    if code_retry and not looks_like_incomplete_typescript(code_retry):
                        return code_retry

        return code

    _gigachat_token_cache: Optional[Tuple[str, float]] = None

    def _get_gigachat_access_token(self, *, auth_key: str, verify_tls: bool) -> Tuple[str, float]:
        """
        Возвращает (access_token, expires_at_unix_seconds) и кеширует токен в памяти.
        """
        cached = getattr(self.__class__, "_gigachat_token_cache", None)
        if cached:
            token, expires_at = cached
            if expires_at > time.time() + 60:
                return token, expires_at

        oauth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        rq_uid = str(uuid.uuid4())

        # Authorization header должен быть Basic <base64...>
        if auth_key.lower().startswith("basic "):
            auth_header = auth_key
        else:
            auth_header = f"Basic {auth_key}"

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": rq_uid,
            "Authorization": auth_header,
        }
        configured_scope = (os.getenv("GIGACHAT_SCOPE") or "").strip()
        scope_candidates: List[str] = []
        if configured_scope:
            scope_candidates.append(configured_scope)
        # Keep backward compatibility with setups where only AUTHORIZATION_KEY was configured.
        for candidate in ["GIGACHAT_API_PERS", "GIGACHAT_API_B2B", "GIGACHAT_API_CORP"]:
            if candidate not in scope_candidates:
                scope_candidates.append(candidate)

        last_error: str = ""
        resp = None
        for scope in scope_candidates:
            resp = requests.post(
                oauth_url,
                headers=headers,
                data={"scope": scope},
                timeout=60,
                verify=verify_tls,
            )
            if resp.status_code == 200:
                break

            try:
                body = resp.json()
            except Exception:
                body = None
            msg = ""
            if isinstance(body, dict):
                msg = body.get("error_description") or body.get("error") or json.dumps(body)
            details = msg or resp.text[:300]
            last_error = f"scope={scope}: {details}"

            # For non-scope errors don't continue; fail fast.
            if "scope from db not fully includes consumed scope" not in details:
                raise RuntimeError(f"GigaChat OAuth error {resp.status_code}: {details}")

        if resp is None or resp.status_code != 200:
            raise RuntimeError(
                "GigaChat OAuth error 400: scope mismatch for provided GIGACHAT_AUTHORIZATION_KEY. "
                f"Tried scopes: {', '.join(scope_candidates)}. Last error: {last_error}"
            )

        body = resp.json()
        access_token = body.get("access_token")
        if not access_token:
            raise RuntimeError(f"GigaChat OAuth response missing access_token: {body}")

        expires_at = body.get("expires_at")
        if isinstance(expires_at, (int, float)) and expires_at > 0:
            expires_at_ts = float(expires_at)
        else:
            expires_at_ts = time.time() + 29 * 60

        self.__class__._gigachat_token_cache = (access_token, expires_at_ts)
        return access_token, expires_at_ts

