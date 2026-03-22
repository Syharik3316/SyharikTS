import os
import json
import time
import threading
import uuid
import re
from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

from app.services.langfuse_client import LangfuseTrace, build_safe_prompt_preview
from app.services.schema_aliases import (
    CRM_HEADER_ALIASES,
    build_aliases_for_schema,
    collect_schema_field_keys,
    strip_schema_meta_for_output,
)
from app.utils.helpers import (
    extract_typescript_code,
    looks_like_incomplete_typescript,
    ensure_json_object,
)


class LLMClient:
    _gigachat_token_cache_lock = threading.Lock()

    def __init__(self) -> None:
        self.provider = (os.getenv("LLM_PROVIDER", "stub") or "stub").strip().lower()
        self._active_trace: LangfuseTrace | None = None
        self.last_usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def generate_ts_code(
        self,
        *,
        prompt: str,
        extracted_input_json: Any,
        schema_obj: Any,
        interface_ts: str,
        file_kind: str,
    ) -> str:
        trace = self._active_trace
        self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        def finalize_or_reject(code: str) -> str:
            if self._is_bad_generated_code(code, file_kind=file_kind, schema_obj=schema_obj):
                if self.provider == "stub":
                    return self._generate_stub_code(
                        extracted_input_json=extracted_input_json,
                        schema_obj=schema_obj,
                        interface_ts=interface_ts,
                        file_kind=file_kind,
                    )
                raise ValueError("LLM output rejected by shape guard; stub fallback is disabled for non-stub providers")
            return code

        if self.provider == "stub":
            return self._generate_stub_code(
                extracted_input_json=extracted_input_json,
                schema_obj=schema_obj,
                interface_ts=interface_ts,
                file_kind=file_kind,
            )

        if self.provider == "openai_compatible":
            return finalize_or_reject(self._generate_via_openai_compatible(prompt))

        if self.provider == "gigachat":
            return finalize_or_reject(self._generate_via_gigachat(prompt, file_kind=file_kind, schema_obj=schema_obj))

        raise ValueError(f"Unsupported LLM_PROVIDER: {self.provider}")

    def _coerce_value(self, value: Any, example: Any) -> Any:
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

        if isinstance(example, str):
            return str(value)

        return value

    def _is_bad_generated_code(self, code: str, *, file_kind: str, schema_obj: Any | None = None) -> bool:
        if not code or "export default function" not in code:
            return True
        if looks_like_incomplete_typescript(code):
            return True

        low = code.lower()
        document_kinds = {"pdf", "docx", "txt", "md", "rtf", "odt", "xml", "epub", "fb2", "doc"}

        if "json.parse(base64file)" in low:
            return True

        if "void base64file;" in low:
            return True

        if " as any" in low:
            return True
        if "\\p{l}" in low or "\\p{n}" in low:
            return True

        has_decode = "decodebase64" in low or "buffer.from(base64file" in low or "atob(" in low
        has_parse = "parsecsv" in low or "split(';')" in low or "separator" in low
        has_typed_return = "dealdata[]" in code
        if file_kind in {"csv", "xls", "xlsx"}:
            if not (has_decode and has_parse and has_typed_return):
                return True

        if file_kind in document_kinds:
            if "parsecsv" in low or "split(';')" in low or "separator" in low:
                return True
            if "const csv = decodebase64(base64file)" in low:
                return True
            if "const result: record<string, unknown> = {}" in low and "return [result as dealdata]" in low:
                return True

        schema = ensure_json_object(schema_obj) if schema_obj is not None else {}
        schema_has_nested = any(isinstance(v, (list, dict)) for v in schema.values())
        if schema_has_nested:
            if 'return string(value ?? "")' in low or "return string(value ?? '')" in low:
                return True
            if '"input": any[]' in low and '{ "input": "" }' in low:
                return True
            if '{"value":""}' in low or '{ "value": "" }' in low:
                return True

        if isinstance(schema.get("input"), list):
            if "input:" not in low and '"input"' not in low:
                return True

        if schema:
            schema_keys = collect_schema_field_keys(schema_obj)
            known_keys = set(CRM_HEADER_ALIASES.keys())
            forbidden_keys = known_keys - schema_keys
            for key in forbidden_keys:
                if f'"{key}"' in code or f"'{key}'" in code:
                    return True

        return False

    def _generate_stub_code(
        self, *, extracted_input_json: Any, schema_obj: Any, interface_ts: str, file_kind: str
    ) -> str:
        schema = ensure_json_object(schema_obj)
        schema_compact = json.dumps(strip_schema_meta_for_output(schema), ensure_ascii=False, separators=(",", ":"))
        extracted_obj = ensure_json_object(extracted_input_json) if isinstance(extracted_input_json, dict) else {}
        aliases_compact = json.dumps(
            build_aliases_for_schema(schema, extracted=extracted_obj),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        extracted_compact = json.dumps(extracted_obj, ensure_ascii=False, separators=(",", ":"))

        if file_kind not in {"csv", "xls", "xlsx"}:
            return (
                f"{interface_ts}\n\n"
                "export default function (base64file: string): DealData[] {\n"
                "  if (base64file == null || !String(base64file).trim()) return [];\n"
                f"  const schema: Record<string, unknown> = {schema_compact};\n"
                f"  const aliases: Record<string, string[]> = {aliases_compact};\n"
                f"  const extracted = {extracted_compact} as Record<string, unknown>;\n"
                "  const records = Array.isArray(extracted.records) ? extracted.records : [];\n"
                "  const text = String(extracted.text ?? \"\");\n"
                "  const norm = (s: unknown): string => String(s ?? \"\").toLowerCase().replace(/[^a-z0-9а-яё]+/gi, \"\");\n"
                "  const pick = (row: Record<string, unknown>, key: string): unknown => {\n"
                "    const candidates = [key, ...(aliases[key] ?? [])];\n"
                "    for (const c of candidates) {\n"
                "      const want = norm(c);\n"
                "      const shortKey = want.length <= 8;\n"
                "      for (const [rk, rv] of Object.entries(row || {})) {\n"
                "        const got = norm(rk);\n"
                "        if (got === want) return rv;\n"
                "        if (!shortKey && (got.includes(want) || want.includes(got))) return rv;\n"
                "      }\n"
                "    }\n"
                "    return row[key];\n"
                "  };\n"
                "  const toNum = (v: unknown): number => {\n"
                "    const n = Number(String(v ?? \"\").trim().replace(/\\s+/g, \"\").replace(\",\", \".\"));\n"
                "    return Number.isFinite(n) ? n : 0;\n"
                "  };\n"
                "  const toBool = (v: unknown): boolean => [\"1\",\"true\",\"yes\",\"y\",\"да\"].includes(String(v ?? \"\").trim().toLowerCase());\n"
                "  const dflt = (ex: unknown): unknown => {\n"
                "    if (Array.isArray(ex)) return [];\n"
                "    if (ex === null) return null;\n"
                "    if (typeof ex === \"number\") return 0;\n"
                "    if (typeof ex === \"boolean\") return false;\n"
                "    if (typeof ex === \"string\") return \"\";\n"
                "    if (ex && typeof ex === \"object\") {\n"
                "      const o: Record<string, unknown> = {};\n"
                "      for (const [k, v] of Object.entries(ex as Record<string, unknown>)) o[k] = dflt(v);\n"
                "      return o;\n"
                "    }\n"
                "    return \"\";\n"
                "  };\n"
                "  const cast = (v: unknown, ex: unknown): unknown => {\n"
                "    if (Array.isArray(ex)) {\n"
                "      const itemEx = ex.length ? ex[0] : \"\";\n"
                "      return Array.isArray(v) ? v.map((x) => cast(x, itemEx)) : [];\n"
                "    }\n"
                "    if (ex === null) { const t = String(v ?? \"\").trim(); return t ? String(v) : null; }\n"
                "    if (typeof ex === \"number\") return toNum(v);\n"
                "    if (typeof ex === \"boolean\") return toBool(v);\n"
                "    if (typeof ex === \"string\") return String(v ?? \"\");\n"
                "    if (ex && typeof ex === \"object\") {\n"
                "      const src = (v && typeof v === \"object\") ? (v as Record<string, unknown>) : {};\n"
                "      const o: Record<string, unknown> = {};\n"
                "      for (const [k, sub] of Object.entries(ex as Record<string, unknown>)) o[k] = cast(src[k], sub);\n"
                "      return o;\n"
                "    }\n"
                "    return v;\n"
                "  };\n"
                "  if (Array.isArray((schema as Record<string, unknown>).input)) {\n"
                "    const itemEx = (((schema as Record<string, unknown>).input as unknown[]) || [])[0] ?? {};\n"
                "    const mapped = records.map((r) => {\n"
                "      const src = (r && typeof r === \"object\") ? (r as Record<string, unknown>) : {};\n"
                "      const aligned: Record<string, unknown> = {};\n"
                "      for (const k of Object.keys((itemEx && typeof itemEx === \"object\") ? (itemEx as Record<string, unknown>) : {})) {\n"
                "        aligned[k] = pick(src, k);\n"
                "      }\n"
                "      return cast(aligned, itemEx);\n"
                "    });\n"
                "    const out = (dflt(schema) as Record<string, unknown>);\n"
                "    out.input = mapped;\n"
                "    return [out as DealData];\n"
                "  }\n"
                "  const out = (dflt(schema) as Record<string, unknown>);\n"
                "  const row0 = records[0] ?? {};\n"
                "  const alignedRow0: Record<string, unknown> = {};\n"
                "  for (const k of Object.keys(schema)) alignedRow0[k] = pick((row0 && typeof row0 === \"object\") ? (row0 as Record<string, unknown>) : {}, k);\n"
                "  const mapped = cast(alignedRow0, schema) as Record<string, unknown>;\n"
                "  for (const [k, v] of Object.entries(mapped)) out[k] = v;\n"
                "  if (!records.length && text) {\n"
                "    for (const key of Object.keys(out)) {\n"
                "      if (typeof out[key] === \"string\" && !String(out[key] || \"\").trim()) {\n"
                "        const r = new RegExp(`${key}\\\\s*[:\\\\-]\\\\s*([^\\\\n;]+)`, \"i\");\n"
                "        const m = text.match(r);\n"
                "        if (m) out[key] = m[1].trim();\n"
                "      }\n"
                "    }\n"
                "  }\n"
                "  return [out as DealData];\n"
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
        trace = self._active_trace
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage

        base_url = os.getenv("OPENAI_COMPAT_BASE_URL", "").strip()
        api_key = os.getenv("OPENAI_COMPAT_API_KEY", "").strip()
        model = os.getenv("OPENAI_COMPAT_MODEL", "").strip()

        if not base_url or not model:
            raise ValueError(
                "For openai_compatible set OPENAI_COMPAT_BASE_URL and OPENAI_COMPAT_MODEL (and optionally OPENAI_COMPAT_API_KEY)."
            )

        raw_max_out = (os.getenv("OPENAI_COMPAT_MAX_TOKENS") or "").strip()
        max_out = int(raw_max_out) if raw_max_out.isdigit() and int(raw_max_out) > 0 else 8192

        llm = ChatOpenAI(
            base_url=base_url,
            api_key=api_key or None,
            model=model,
            temperature=0,
            max_tokens=max_out,
        )
        with (trace.span("llm.openai_compatible", metadata={"provider": "openai_compatible", "model": model})
              if trace else _noop_context()):
            msg = llm.invoke([HumanMessage(content=prompt)])
        self.last_usage = self._extract_usage_from_langchain_message(msg)
        return extract_typescript_code(msg.content or "")

    def _generate_via_gigachat(self, prompt: str, *, file_kind: str, schema_obj: Any) -> str:
        trace = self._active_trace

        base_url = (os.getenv("GIGACHAT_BASE_URL") or "https://gigachat.devices.sberbank.ru/api/v1").strip().rstrip("/")
        model = (os.getenv("GIGACHAT_MODEL") or "").strip() or "GigaChat-2-Max"

        verify_tls_env = (os.getenv("GIGACHAT_VERIFY_TLS") or "false").strip().lower()
        verify_tls = verify_tls_env in {"1", "true", "yes", "y", "on"}
        self._maybe_disable_insecure_tls_warning(verify_tls)

        auth_header = self._resolve_gigachat_authorization_header(verify_tls=verify_tls)

        chat_url = f"{base_url}/chat/completions"
        raw_max_tokens = (os.getenv("GIGACHAT_MAX_TOKENS") or "").strip()
        max_tokens = int(raw_max_tokens) if raw_max_tokens else None
        # Large JSON schemas → large prompts; default 90s caused ReadTimeout then 500s behind proxies.
        timeout_sec = int((os.getenv("GIGACHAT_TIMEOUT_SECONDS") or "600").strip() or "600")

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
            "Authorization": auth_header,
        }

        if trace:
            with trace.span(
                "llm.gigachat.primary_call",
                input_data=build_safe_prompt_preview(prompt),
                metadata={"provider": "gigachat", "model": model, "file_kind": file_kind},
            ):
                resp = requests.post(chat_url, headers=headers, json=payload, timeout=timeout_sec, verify=verify_tls)
        else:
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
        self.last_usage = self._extract_usage_from_payload(data)
        content = ""
        if isinstance(data, dict):
            choices = data.get("choices") or []
            if choices and isinstance(choices, list):
                first = choices[0] or {}
                message = first.get("message") or {}
                content = message.get("content") or ""

        if not content:
            raise RuntimeError("GigaChat returned empty content")

        if int(self.last_usage.get("total_tokens") or 0) <= 0:
            prompt_tokens = self._count_tokens_via_gigachat_api(prompt, model=model, auth_header=auth_header, verify_tls=verify_tls)
            completion_tokens = self._count_tokens_via_gigachat_api(
                content, model=model, auth_header=auth_header, verify_tls=verify_tls
            )
            self.last_usage = {
                "prompt_tokens": int(prompt_tokens or 0),
                "completion_tokens": int(completion_tokens or 0),
                "total_tokens": int((prompt_tokens or 0) + (completion_tokens or 0)),
            }
        code = extract_typescript_code(content)

        # Retry several times with escalating instructions when output is truncated or invalid.
        retry_attempts = int((os.getenv("GIGACHAT_RETRY_ATTEMPTS") or "3").strip() or "3")
        attempt = 0
        while attempt < retry_attempts and (
            looks_like_incomplete_typescript(code)
            or self._is_bad_generated_code(code, file_kind=file_kind, schema_obj=schema_obj)
        ):
            attempt += 1
            if attempt == 1:
                correction = (
                    "Previous output invalid. Keep function signature; regenerate full deterministic TypeScript."
                )
            elif attempt == 2:
                correction = (
                    "Previous output still invalid. Preserve schema shape exactly (especially nested arrays/objects). Never flatten to scalars."
                )
            else:
                correction = (
                    "Previous output rejected again. Return FULL TypeScript with strict schema-shape preservation. No markdown/explanations/placeholders."
                )
            retry_payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            (
                                f"{correction} "
                                "If this is a document format (pdf/docx/txt/rtf/etc), do NOT generate CSV parser logic "
                                "(no parseCsv/split(';')/separator parser).\n"
                            )
                            + prompt
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
            if trace:
                with trace.span(
                    "llm.gigachat.retry_call",
                    metadata={"attempt": attempt, "provider": "gigachat", "model": model},
                ):
                    retry_resp = requests.post(
                        chat_url,
                        headers=headers,
                        json=retry_payload,
                        timeout=max(timeout_sec, 120),
                        verify=verify_tls,
                    )
            else:
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
                    if code_retry and not looks_like_incomplete_typescript(code_retry) and not self._is_bad_generated_code(
                        code_retry, file_kind=file_kind, schema_obj=schema_obj
                    ):
                        return code_retry
                    code = code_retry or code

        return code

    def transcribe_image_via_gigachat(self, contents: bytes, file_kind: str) -> str:
        """
        Превращает изображение в текст через GigaChat vision (по примеру из ai.md):
          1) загрузка изображения в /files (purpose="general")
          2) вызов /chat/completions с attachments=[file_id] и function_call="auto"
        """

        base_url = (os.getenv("GIGACHAT_BASE_URL") or "https://gigachat.devices.sberbank.ru/api/v1").strip().rstrip("/")
        model = (os.getenv("GIGACHAT_MODEL") or "").strip() or "GigaChat-2-Max"

        verify_tls_env = (os.getenv("GIGACHAT_VERIFY_TLS") or "false").strip().lower()
        verify_tls = verify_tls_env in {"1", "true", "yes", "y", "on"}
        self._maybe_disable_insecure_tls_warning(verify_tls)

        auth_header = self._resolve_gigachat_authorization_header(verify_tls=verify_tls)
        headers = {
            "Accept": "application/json",
            "Authorization": auth_header,
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
        timeout_chat = int((os.getenv("GIGACHAT_TIMEOUT_SECONDS") or "600").strip() or "600")

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

    def _maybe_disable_insecure_tls_warning(self, verify_tls: bool) -> None:
        if not verify_tls:
            urllib3.disable_warnings(InsecureRequestWarning)

    def _resolve_gigachat_authorization_header(self, *, verify_tls: bool) -> str:
        api_key = (os.getenv("GIGACHAT_API_KEY") or "").strip()
        if api_key:
            token = api_key[7:].strip() if api_key.lower().startswith("bearer ") else api_key
            return f"Bearer {token}"

        auth_key = (os.getenv("GIGACHAT_AUTHORIZATION_KEY") or "").strip()
        if auth_key.lower().startswith("bearer "):
            token = auth_key[7:].strip()
            return f"Bearer {token}"

        if not auth_key:
            raise ValueError(
                "For gigachat set either GIGACHAT_API_KEY, "
                "GIGACHAT_AUTHORIZATION_KEY='Bearer <token>' or OAuth key in GIGACHAT_AUTHORIZATION_KEY."
            )

        token, _expires_at = self._get_gigachat_access_token(auth_key=auth_key, verify_tls=verify_tls)
        return f"Bearer {token}"

    def _get_gigachat_access_token(self, *, auth_key: str, verify_tls: bool) -> Tuple[str, float]:
        """
        Возвращает (access_token, expires_at_unix_seconds) и кеширует токен в памяти.
        """
        with self.__class__._gigachat_token_cache_lock:
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
            for candidate in ["GIGACHAT_API_PERS", "GIGACHAT_API_B2B", "GIGACHAT_API_CORP"]:
                if candidate not in scope_candidates:
                    scope_candidates.append(candidate)

            last_error: str = ""
            resp = None
            oauth_retry_attempts = int((os.getenv("GIGACHAT_OAUTH_RETRY_ATTEMPTS") or "3").strip() or "3")
            oauth_retry_delay_ms = int((os.getenv("GIGACHAT_OAUTH_RETRY_DELAY_MS") or "1200").strip() or "1200")
            for scope in scope_candidates:
                attempt = 0
                while True:
                    resp = requests.post(
                        oauth_url,
                        headers=headers,
                        data={"scope": scope},
                        timeout=60,
                        verify=verify_tls,
                    )
                    if resp.status_code == 200:
                        break
                    if resp.status_code == 429 and attempt < max(0, oauth_retry_attempts - 1):
                        attempt += 1
                        time.sleep((oauth_retry_delay_ms * attempt) / 1000.0)
                        continue
                    break
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

                if resp.status_code == 429:
                    raise RuntimeError(f"GIGACHAT_RATE_LIMIT: GigaChat OAuth error 429: {details}")

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

    def _count_tokens_via_gigachat_api(
        self,
        text: str,
        *,
        model: str,
        auth_header: str,
        verify_tls: bool,
    ) -> int:
        base_url = (os.getenv("GIGACHAT_BASE_URL") or "https://gigachat.devices.sberbank.ru/api/v1").strip().rstrip("/")
        url = f"{base_url}/tokens/count"
        payload = {"model": model, "input": [text]}
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": auth_header,
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60, verify=verify_tls)
            if resp.status_code != 200:
                return 0
            data = resp.json()
            return self._extract_tokens_count_value(data)
        except Exception:
            return 0

    def _extract_tokens_count_value(self, data: Any) -> int:
        if isinstance(data, dict):
            for key in ("tokens", "total_tokens", "count"):
                val = data.get(key)
                if isinstance(val, int):
                    return max(0, val)
            maybe_tokens = data.get("tokens")
            if isinstance(maybe_tokens, list) and maybe_tokens:
                first = maybe_tokens[0]
                if isinstance(first, dict):
                    for key in ("tokens", "count", "total_tokens"):
                        v = first.get(key)
                        if isinstance(v, int):
                            return max(0, v)
            dumped = json.dumps(data, ensure_ascii=False)
            m = re.search(r'"tokens"\s*:\s*(\d+)', dumped)
            if m:
                return int(m.group(1))
            return 0
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                val = first.get("tokens")
                if isinstance(val, int):
                    return max(0, val)
        return 0

    def _extract_usage_from_payload(self, payload: Any) -> Dict[str, int]:
        if not isinstance(payload, dict):
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        usage = payload.get("usage") or {}
        if not isinstance(usage, dict):
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        total = int(usage.get("total_tokens") or (prompt + completion))
        return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total}

    def _extract_usage_from_langchain_message(self, message: Any) -> Dict[str, int]:
        meta = getattr(message, "response_metadata", {}) or {}
        usage = meta.get("token_usage") or meta.get("usage") or {}
        if not isinstance(usage, dict):
            usage = {}
        prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        total = int(usage.get("total_tokens") or (prompt + completion))
        return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total}


class _noop_context:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False

