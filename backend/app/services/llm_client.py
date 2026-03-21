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
)

_CRM_HEADER_ALIASES = {
    "actPlanDate": ["Плановая дата акта"],
    "closeReason": ["Сделка - Причина закрытия"],
    "closeReasonComment": ["Сделка - Комментарий к причине закрытия"],
    "creationDate": ["Дата создания"],
    "creator": ["Сделка - Создал"],
    "deal": ["Сделка"],
    "dealCreationDate": ["Сделка - Дата создания"],
    "dealId": ["Сделка - ID сделки"],
    "dealIdentifier": ["Сделка - Идентификатор"],
    "dealLastUpdateDate": ["Сделка - Дата последнего обновления"],
    "dealName": ["Сделка - Название"],
    "dealProduct": ["Сделка - Продукт"],
    "dealRevenueAmount": ["Сделка - Сумма выручки"],
    "dealSource": ["Сделка - Источник сделки"],
    "dealStage": ["Сделка - Стадия"],
    "dealStageFinal": ["Стадия (Сделка)"],
    "dealStageTransitionDate": ["Сделка - Дата перехода объекта на новую стадию"],
    "deliveryType": ["Тип поставки"],
    "description": ["Сделка - Описание"],
    "directSupply": ["Сделка - Прямая поставка"],
    "distributor": ["Сделка - Дистрибьютор"],
    "finalLicenseAmount": ["Сделка - Итоговая сумма лицензий"],
    "finalServiceAmount": ["Сделка - Итоговая сумма услуг"],
    "finalServiceAmountByRevenueWithVAT": ["Сделка - Итоговая сумма услуг по выручке (с НДС)"],
    "finalServiceAmountWithVAT": ["Сделка - Итоговая сумма услуг (с НДС)"],
    "forecast": ["Сделка - Прогноз"],
    "identifierRevenue": ["Идентификатор (Выручка)"],
    "invoiceAmount": ["Сумма акта"],
    "invoiceAmountWithVAT": ["Сумма акта (с НДС)"],
    "lastUpdateDate": ["Дата последнего обновления"],
    "marketingEvent": ["Сделка - Маркетинговое мероприятие"],
    "organization": ["Сделка - Организация"],
    "partner": ["Сделка - Партнер по сделке"],
    "product": ["Продукт"],
    "quantity": ["Количество"],
    "responsiblePerson": ["Сделка - Ответственный"],
    "revenue": ["Выручка"],
    "siteLead": ["Сделка - Лид с сайта"],
    "stageTransitionTime": ["Время перехода на текущую стадию"],
    "totalProductAmount": ["Сделка - Итоговая сумма продуктов"],
    "unitOfMeasure": ["Единица измерения"],
}


def _build_aliases_for_schema(schema: Dict[str, Any]) -> Dict[str, List[str]]:
    aliases: Dict[str, List[str]] = {}
    for key in schema.keys():
        vals = _CRM_HEADER_ALIASES.get(key, [])
        if vals:
            aliases[key] = vals
    return aliases


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
        file_kind: str,
    ) -> str:
        def finalize_or_fallback(code: str) -> str:
            if self._is_bad_generated_code(code, file_kind=file_kind):
                return self._generate_stub_code(
                    extracted_input_json=extracted_input_json,
                    schema_obj=schema_obj,
                    interface_ts=interface_ts,
                    file_kind=file_kind,
                )
            return code

        if self.provider == "stub":
            return self._generate_stub_code(
                extracted_input_json=extracted_input_json,
                schema_obj=schema_obj,
                interface_ts=interface_ts,
                file_kind=file_kind,
            )

        if self.provider == "openai_compatible":
            return finalize_or_fallback(self._generate_via_openai_compatible(prompt))

        if self.provider == "gigachat":
            return finalize_or_fallback(self._generate_via_gigachat(prompt))

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

    def _is_bad_generated_code(self, code: str, *, file_kind: str) -> bool:
        if not code or "export default function" not in code:
            return True
        if looks_like_incomplete_typescript(code):
            return True

        low = code.lower()

        if "json.parse(base64file)" in low:
            return True

        if "void base64file;" in low:
            return True

        if " as any" in low:
            return True
        if "\\p{l}" in low or "\\p{n}" in low:
            return True

        if "const result: dealdata[] =" in low and "return result;" in low and "parsecsv" not in low:
            return True

        # Require at least basic runtime csv flow.
        has_decode = "decodebase64" in low or "buffer.from(base64file" in low or "atob(" in low
        has_parse = "parsecsv" in low or "split(';')" in low or "separator" in low
        has_typed_return = "dealdata[]" in code
        if not (has_decode and has_parse and has_typed_return):
            return True

        if file_kind in {"png", "jpg", "tiff"} and "transcript_b64" not in low:
            return True

        return False

    def _generate_stub_code(
        self, *, extracted_input_json: Any, schema_obj: Any, interface_ts: str, file_kind: str
    ) -> str:
        schema = ensure_json_object(schema_obj)
        schema_compact = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        aliases_compact = json.dumps(_build_aliases_for_schema(schema), ensure_ascii=False, separators=(",", ":"))

        if file_kind in {"png", "jpg", "tiff"}:
            from app.services.image_transcription import transcript_utf8_base64_for_prompt

            transcript = str(ensure_json_object(extracted_input_json).get("text") or "")
            tb64 = transcript_utf8_base64_for_prompt(transcript)
            return (
                f"{interface_ts}\n\n"
                "export default function (base64file: string): DealData[] {\n"
                f'  const TRANSCRIPT_B64 = "{tb64}";\n'
                "  if (base64file == null || !String(base64file).trim()) return [];\n"
                f"  const schema: Record<string, unknown> = {schema_compact};\n"
                f"  const aliases: Record<string, string[]> = {aliases_compact};\n"
                "  const decodeBase64 = (input: string): string => {\n"
                "    if (!input) return \"\";\n"
                "    const raw = String(input).trim();\n"
                "    const payload = raw.includes(\"base64,\") ? raw.slice(raw.indexOf(\"base64,\") + 7) : raw;\n"
                "    let cleaned = payload.replace(/\\s+/g, \"\").replace(/-/g, \"+\").replace(/_/g, \"/\").replace(/[^A-Za-z0-9+/=]/g, \"\");\n"
                "    const pad = cleaned.length % 4;\n"
                "    if (pad > 0) cleaned += \"=\".repeat(4 - pad);\n"
                "    let text = \"\";\n"
                "    try {\n"
                "      if (typeof Buffer !== \"undefined\") {\n"
                "        text = Buffer.from(cleaned, \"base64\").toString(\"utf-8\");\n"
                "      } else if (typeof atob !== \"undefined\") {\n"
                "        const binary = atob(cleaned);\n"
                "        const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));\n"
                "        text = new TextDecoder(\"utf-8\", { fatal: false }).decode(bytes);\n"
                "      }\n"
                "    } catch {\n"
                "      return \"\";\n"
                "    }\n"
                "    if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);\n"
                "    return text;\n"
                "  };\n"
                "  const parseCsv = (text: string): string[][] => {\n"
                "    const rows: string[][] = [];\n"
                "    let row: string[] = [];\n"
                "    let cell = \"\";\n"
                "    let inQuotes = false;\n"
                "    for (let i = 0; i < text.length; i++) {\n"
                "      const ch = text[i];\n"
                "      if (ch === '\"') {\n"
                "        if (inQuotes && text[i + 1] === '\"') { cell += '\"'; i++; } else { inQuotes = !inQuotes; }\n"
                "      } else if (ch === ';' && !inQuotes) {\n"
                "        row.push(cell); cell = \"\";\n"
                "      } else if ((ch === '\\n' || ch === '\\r') && !inQuotes) {\n"
                "        if (ch === '\\r' && text[i + 1] === '\\n') i++;\n"
                "        row.push(cell); cell = \"\";\n"
                "        if (row.some((x) => x !== \"\")) rows.push(row);\n"
                "        row = [];\n"
                "      } else {\n"
                "        cell += ch;\n"
                "      }\n"
                "    }\n"
                "    row.push(cell);\n"
                "    if (row.some((x) => x !== \"\")) rows.push(row);\n"
                "    return rows;\n"
                "  };\n"
                "  const norm = (s: string): string => s.toLowerCase().replace(/[^a-z0-9а-яё]+/gi, \"\");\n"
                "  const toNumber = (s: string): number => {\n"
                "    const n = Number(String(s || \"\").trim().replace(/\\s+/g, \"\").replace(\",\", \".\"));\n"
                "    return Number.isFinite(n) ? n : 0;\n"
                "  };\n"
                "  const toBoolean = (s: string): boolean => [\"1\",\"true\",\"yes\",\"y\",\"да\"].includes(String(s || \"\").trim().toLowerCase());\n"
                "  const cast = (value: string, example: unknown): unknown => {\n"
                "    if (typeof example === \"number\") return toNumber(value);\n"
                "    if (typeof example === \"boolean\") return toBoolean(value);\n"
                "    if (example === null) {\n"
                "      const t = String(value || \"\").trim();\n"
                "      return t === \"\" ? null : t;\n"
                "    }\n"
                "    return String(value ?? \"\");\n"
                "  };\n"
                "  const csv = decodeBase64(TRANSCRIPT_B64);\n"
                "  const table = parseCsv(csv);\n"
                "  if (!table.length) return [];\n"
                "  const headers = table[0].map((h) => String(h ?? \"\").trim());\n"
                "  const idxByHeader = new Map<string, number>();\n"
                "  headers.forEach((h, i) => idxByHeader.set(norm(h), i));\n"
                "  const keys = Object.keys(schema);\n"
                "  const result: DealData[] = [];\n"
                "  for (let r = 1; r < table.length; r++) {\n"
                "    const line = table[r];\n"
                "    const obj: Record<string, unknown> = {};\n"
                "    for (const key of keys) {\n"
                "      const names = [key, ...(aliases[key] ?? [])];\n"
                "      let idx: number | undefined = undefined;\n"
                "      for (const name of names) {\n"
                "        const found = idxByHeader.get(norm(name));\n"
                "        if (found !== undefined) { idx = found; break; }\n"
                "      }\n"
                "      const raw = idx === undefined ? \"\" : String(line[idx] ?? \"\");\n"
                "      if (key === \"dealStageFinal\") {\n"
                "        const stageIdx = idxByHeader.get(norm(\"Стадия (Сделка)\"));\n"
                "        const stageRaw = stageIdx === undefined ? \"\" : String(line[stageIdx] ?? \"\");\n"
                "        const st = stageRaw.trim().toLowerCase();\n"
                "        obj[key] = st === \"закрыта\" || st === \"отклонена\";\n"
                "      } else {\n"
                "        obj[key] = cast(raw, schema[key]);\n"
                "      }\n"
                "    }\n"
                "    result.push(obj as DealData);\n"
                "  }\n"
                "  return result;\n"
                "}\n"
            )

        return (
            f"{interface_ts}\n\n"
            "export default function (base64file: string): DealData[] {\n"
            f"  const schema: Record<string, unknown> = {schema_compact};\n"
            f"  const aliases: Record<string, string[]> = {aliases_compact};\n"
            "  const decodeBase64 = (input: string): string => {\n"
            "    if (!input) return \"\";\n"
            "    const raw = String(input).trim();\n"
            "    const payload = raw.includes(\"base64,\") ? raw.slice(raw.indexOf(\"base64,\") + 7) : raw;\n"
            "    let cleaned = payload.replace(/\\s+/g, \"\").replace(/-/g, \"+\").replace(/_/g, \"/\").replace(/[^A-Za-z0-9+/=]/g, \"\");\n"
            "    const pad = cleaned.length % 4;\n"
            "    if (pad > 0) cleaned += \"=\".repeat(4 - pad);\n"
            "    let text = \"\";\n"
            "    try {\n"
            "      if (typeof Buffer !== \"undefined\") {\n"
            "        text = Buffer.from(cleaned, \"base64\").toString(\"utf-8\");\n"
            "      } else if (typeof atob !== \"undefined\") {\n"
            "        const binary = atob(cleaned);\n"
            "        const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));\n"
            "        text = new TextDecoder(\"utf-8\", { fatal: false }).decode(bytes);\n"
            "      }\n"
            "    } catch {\n"
            "      return \"\";\n"
            "    }\n"
            "    if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);\n"
            "    return text;\n"
            "  };\n"
            "  const parseCsv = (text: string): string[][] => {\n"
            "    const rows: string[][] = [];\n"
            "    let row: string[] = [];\n"
            "    let cell = \"\";\n"
            "    let inQuotes = false;\n"
            "    for (let i = 0; i < text.length; i++) {\n"
            "      const ch = text[i];\n"
            "      if (ch === '\"') {\n"
            "        if (inQuotes && text[i + 1] === '\"') { cell += '\"'; i++; } else { inQuotes = !inQuotes; }\n"
            "      } else if (ch === ';' && !inQuotes) {\n"
            "        row.push(cell); cell = \"\";\n"
            "      } else if ((ch === '\\n' || ch === '\\r') && !inQuotes) {\n"
            "        if (ch === '\\r' && text[i + 1] === '\\n') i++;\n"
            "        row.push(cell); cell = \"\";\n"
            "        if (row.some((x) => x !== \"\")) rows.push(row);\n"
            "        row = [];\n"
            "      } else {\n"
            "        cell += ch;\n"
            "      }\n"
            "    }\n"
            "    row.push(cell);\n"
            "    if (row.some((x) => x !== \"\")) rows.push(row);\n"
            "    return rows;\n"
            "  };\n"
            "  const norm = (s: string): string => s.toLowerCase().replace(/[^a-z0-9а-яё]+/gi, \"\");\n"
            "  const toNumber = (s: string): number => {\n"
            "    const n = Number(String(s || \"\").trim().replace(/\\s+/g, \"\").replace(\",\", \".\"));\n"
            "    return Number.isFinite(n) ? n : 0;\n"
            "  };\n"
            "  const toBoolean = (s: string): boolean => [\"1\",\"true\",\"yes\",\"y\",\"да\"].includes(String(s || \"\").trim().toLowerCase());\n"
            "  const cast = (value: string, example: unknown): unknown => {\n"
            "    if (typeof example === \"number\") return toNumber(value);\n"
            "    if (typeof example === \"boolean\") return toBoolean(value);\n"
            "    if (example === null) {\n"
            "      const t = String(value || \"\").trim();\n"
            "      return t === \"\" ? null : t;\n"
            "    }\n"
            "    return String(value ?? \"\");\n"
            "  };\n"
            "  const csv = decodeBase64(base64file);\n"
            "  const table = parseCsv(csv);\n"
            "  if (!table.length) return [];\n"
            "  const headers = table[0].map((h) => String(h ?? \"\").trim());\n"
            "  const idxByHeader = new Map<string, number>();\n"
            "  headers.forEach((h, i) => idxByHeader.set(norm(h), i));\n"
            "  const keys = Object.keys(schema);\n"
            "  const result: DealData[] = [];\n"
            "  for (let r = 1; r < table.length; r++) {\n"
            "    const line = table[r];\n"
            "    const obj: Record<string, unknown> = {};\n"
            "    for (const key of keys) {\n"
            "      const names = [key, ...(aliases[key] ?? [])];\n"
            "      let idx: number | undefined = undefined;\n"
            "      for (const name of names) {\n"
            "        const found = idxByHeader.get(norm(name));\n"
            "        if (found !== undefined) { idx = found; break; }\n"
            "      }\n"
            "      const raw = idx === undefined ? \"\" : String(line[idx] ?? \"\");\n"
            "      if (key === \"dealStageFinal\") {\n"
            "        const stageIdx = idxByHeader.get(norm(\"Стадия (Сделка)\"));\n"
            "        const stageRaw = stageIdx === undefined ? \"\" : String(line[stageIdx] ?? \"\");\n"
            "        const st = stageRaw.trim().toLowerCase();\n"
            "        obj[key] = st === \"закрыта\" || st === \"отклонена\";\n"
            "      } else {\n"
            "        obj[key] = cast(raw, schema[key]);\n"
            "      }\n"
            "    }\n"
            "    result.push(obj as DealData);\n"
            "  }\n"
            "  return result;\n"
            "}\n"
        )

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
        raw_max_tokens = (os.getenv("GIGACHAT_MAX_TOKENS") or "").strip()
        max_tokens = int(raw_max_tokens) if raw_max_tokens else None
        timeout_sec = int((os.getenv("GIGACHAT_TIMEOUT_SECONDS") or "90").strip() or "90")

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0,
            "n": 1,
            "repetition_penalty": 1,
            "update_interval": 0,
        }
        if max_tokens and max_tokens > 0:
            payload["max_tokens"] = max_tokens
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

        # Retry several times with stronger instruction if output seems truncated.
        retry_attempts = int((os.getenv("GIGACHAT_RETRY_ATTEMPTS") or "3").strip() or "3")
        attempt = 0
        while looks_like_incomplete_typescript(code) and attempt < retry_attempts:
            attempt += 1
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
                "n": 1,
                "repetition_penalty": 1,
                "update_interval": 0,
            }
            if max_tokens and max_tokens > 0:
                retry_payload["max_tokens"] = max_tokens
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
                    code = code_retry or code

        return code

    def transcribe_image_via_gigachat(self, contents: bytes, file_kind: str) -> str:
        """
        Превращает изображение в текст через GigaChat vision (по примеру из ai.md):
          1) загрузка изображения в /files (purpose="general")
          2) вызов /chat/completions с attachments=[file_id] и function_call="auto"
        """

        auth_key = (os.getenv("GIGACHAT_AUTHORIZATION_KEY") or "").strip()
        if not auth_key:
            raise ValueError("For gigachat image transcription set GIGACHAT_AUTHORIZATION_KEY.")

        base_url = (os.getenv("GIGACHAT_BASE_URL") or "https://gigachat.devices.sberbank.ru/api/v1").strip().rstrip("/")
        model = (os.getenv("GIGACHAT_MODEL") or "").strip() or "GigaChat-2-Max"

        verify_tls_env = (os.getenv("GIGACHAT_VERIFY_TLS") or "false").strip().lower()
        verify_tls = verify_tls_env in {"1", "true", "yes", "y", "on"}

        token, _expires_at = self._get_gigachat_access_token(auth_key=auth_key, verify_tls=verify_tls)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }

        mime_name = {
            "png": ("image/png", "upload.png"),
            "jpg": ("image/jpeg", "upload.jpg"),
            "tiff": ("image/tiff", "upload.tiff"),
            "jpeg": ("image/jpeg", "upload.jpeg"),
        }.get(file_kind, ("image/png", "upload.png"))
        mime, filename = mime_name

        vision_prompt = (
            "Распознай весь видимый текст на изображении. Сохрани переносы строк. "
            "Если это таблица или выгрузка, разделяй колонки точкой с запятой (;), как в CSV. "
            "Выведи только текст, без markdown и пояснений."
        )

        upload_url = f"{base_url}/files"
        timeout_upload = int((os.getenv("GIGACHAT_FILE_UPLOAD_TIMEOUT_SECONDS") or "120").strip() or "120")
        try:
            up = requests.post(
                upload_url,
                headers=headers,
                files={"file": (filename, contents, mime)},
                data={"purpose": "general"},
                timeout=timeout_upload,
                verify=verify_tls,
            )
        except Exception:
            return ""

        if up.status_code != 200:
            return ""

        try:
            up_body = up.json()
        except Exception:
            return ""

        file_id = up_body.get("id") if isinstance(up_body, dict) else None
        if not file_id:
            return ""

        chat_url = f"{base_url}/chat/completions"
        timeout_chat = int((os.getenv("GIGACHAT_TIMEOUT_SECONDS") or "120").strip() or "120")

        payload: Dict[str, Any] = {
            "model": model,
            "function_call": "auto",
            "messages": [
                {
                    "role": "user",
                    "content": vision_prompt,
                    "attachments": [str(file_id)],
                }
            ],
            "stream": False,
            "temperature": 0,
            "n": 1,
            "repetition_penalty": 1,
            "update_interval": 0,
        }

        raw_max = (os.getenv("GIGACHAT_IMAGE_TRANSCRIPTION_MAX_TOKENS") or "").strip()
        if raw_max.isdigit() and int(raw_max) > 0:
            payload["max_tokens"] = int(raw_max)

        content_out = ""
        try:
            resp = requests.post(
                chat_url,
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=timeout_chat,
                verify=verify_tls,
            )
            if resp.status_code != 200:
                return ""

            data = resp.json()
            if isinstance(data, dict):
                choices = data.get("choices") or []
                if choices and isinstance(choices, list):
                    first = choices[0] or {}
                    message = first.get("message") or {}
                    content_out = (message.get("content") or "").strip()
        finally:
            try:
                del_url = f"{base_url}/files/{file_id}/delete"
                requests.post(del_url, headers=headers, timeout=30, verify=verify_tls)
            except Exception:
                pass

        return content_out

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

