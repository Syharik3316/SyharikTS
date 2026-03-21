import json
from typing import Any

from app.services.image_transcription import transcript_utf8_base64_for_prompt
from app.utils.helpers import ensure_json_object


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


def _build_aliases_for_schema(schema: dict[str, Any]) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    for key in schema.keys():
        vals = _CRM_HEADER_ALIASES.get(key, [])
        if vals:
            aliases[key] = vals
    return aliases


def _infer_ts_type(value: Any) -> str:
    if value is None:
        return "string | null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "any[]"
    if isinstance(value, dict):
        return "any"
    return "any"


def build_interface_ts(schema_obj: Any, *, interface_name: str = "DealData") -> str:
    """
    Build a compact TS interface from the user JSON example.
    """
    obj = ensure_json_object(schema_obj)
    fields = []
    # Keep order stable by insertion order in dict (Python 3.7+).
    for k, v in obj.items():
        ts_t = _infer_ts_type(v)
        # Always use quoted property names to keep TS valid for keys
        # with spaces, punctuation or non-latin characters.
        key_ts = json.dumps(str(k), ensure_ascii=False)
        fields.append(f"{key_ts}: {ts_t};")
    body = "\n  ".join(fields)
    return f"interface {interface_name} {{\n  {body}\n}}"


def build_generation_prompt(
    extracted_input_json: Any,
    schema_obj: Any,
    *,
    interface_ts: str,
    file_kind: str,
) -> str:
    schema = ensure_json_object(schema_obj)
    schema_compact = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    schema_keys = list(schema.keys())
    aliases_compact = json.dumps(_build_aliases_for_schema(schema), ensure_ascii=False, separators=(",", ":"))
    schema_keys_compact = json.dumps(schema_keys, ensure_ascii=False, separators=(",", ":"))

    if file_kind in {"png", "jpg", "tiff"}:
        obj = ensure_json_object(extracted_input_json)
        transcript = str(obj.get("text") or "")
        transcript_b64 = transcript_utf8_base64_for_prompt(transcript)
        excerpt = transcript[:6000] + ("…" if len(transcript) > 6000 else "")
        return (
            "Return ONLY TypeScript code. No markdown. No comments. No explanation.\n"
            "Generate fully working deterministic code.\n"
            "Context: the user uploaded an image. The text was transcribed on the server. "
            "You must embed the exact TRANSCRIPT_UTF8_B64 string below as a TypeScript string literal "
            "TRANSCRIPT_B64 and decode it with decodeBase64 — do NOT OCR base64file in TypeScript.\n"
            "Hard requirements:\n"
            "1) Keep the provided interface and function signature exactly.\n"
            "2) If base64file is null/undefined/empty after trim, return [].\n"
            "3) const csv = decodeBase64(TRANSCRIPT_B64) where TRANSCRIPT_B64 is the literal below.\n"
            "4) CSV separator is ';', support quoted values and newlines inside quotes.\n"
            "5) Build a header map from CSV columns to schema keys by normalized names.\n"
            "6) Convert values by schema example type:\n"
            "   - number: parse decimal, comma as decimal separator supported\n"
            "   - boolean: true for [1,true,yes,y,да], false otherwise\n"
            "   - string: string value\n"
            "   - null in schema means string | null (empty -> null)\n"
            "7) Do not use `as any` for result or return value.\n"
            "8) Ignore unknown CSV columns.\n"
            "9) Return DealData[] built from real CSV rows in the transcript.\n"
            "10) Use regex normalization without unicode property escapes (NO \\p{...}).\n"
            "11) If key is dealStageFinal, derive it from stage text: true for 'закрыта'/'отклонена', else false.\n"
            f"TRANSCRIPT_UTF8_B64 (copy verbatim into const TRANSCRIPT_B64 = \"...\"):\n{transcript_b64}\n"
            "Decoded transcript preview (reference only):\n"
            f"{excerpt}\n\n"
            "Schema object:\n"
            f"{schema_compact}\n"
            "Schema keys:\n"
            f"{schema_keys_compact}\n"
            "Header aliases map (schemaKey -> candidate CSV headers):\n"
            f"{aliases_compact}\n"
            f"{interface_ts}\n"
            "export default function (base64file: string): DealData[] {\n"
            f'  const TRANSCRIPT_B64 = "{transcript_b64}";\n'
            "  if (base64file == null || !String(base64file).trim()) return [];\n"
            "  const schema = SCHEMA_PLACEHOLDER;\n"
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
            "        if (inQuotes && text[i + 1] === '\"') { cell += '\"'; i++; }\n"
            "        else { inQuotes = !inQuotes; }\n"
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
            "    if (example === null) { const t = String(value || \"\").trim(); return t === \"\" ? null : t; }\n"
            "    return String(value ?? \"\");\n"
            "  };\n"
            "  const csv = decodeBase64(TRANSCRIPT_B64);\n"
            "  const rows = parseCsv(csv);\n"
            "  if (!rows.length) return [];\n"
            "  const aliases: Record<string, string[]> = ALIASES_PLACEHOLDER;\n"
            "  const headers = rows[0].map((h) => String(h ?? \"\").trim());\n"
            "  const headerIndex = new Map<string, number>();\n"
            "  headers.forEach((h, i) => headerIndex.set(norm(h), i));\n"
            "  const keys = Object.keys(schema);\n"
            "  const out: DealData[] = [];\n"
            "  for (let r = 1; r < rows.length; r++) {\n"
            "    const line = rows[r];\n"
            "    const obj: Record<string, unknown> = {};\n"
            "    for (const key of keys) {\n"
            "      const candidates = [key, ...(aliases[key] ?? [])];\n"
            "      let idx: number | undefined = undefined;\n"
            "      for (const name of candidates) {\n"
            "        const found = headerIndex.get(norm(name));\n"
            "        if (found !== undefined) { idx = found; break; }\n"
            "      }\n"
            "      const raw = idx === undefined ? \"\" : String(line[idx] ?? \"\");\n"
            "      if (key === \"dealStageFinal\") {\n"
            "        const stageIdx = headerIndex.get(norm(\"Стадия (Сделка)\"));\n"
            "        const stageRaw = stageIdx === undefined ? \"\" : String(line[stageIdx] ?? \"\");\n"
            "        const st = stageRaw.trim().toLowerCase();\n"
            "        obj[key] = st === \"закрыта\" || st === \"отклонена\";\n"
            "      } else {\n"
            "        obj[key] = cast(raw, (schema as Record<string, unknown>)[key]);\n"
            "      }\n"
            "    }\n"
            "    out.push(obj as DealData);\n"
            "  }\n"
            "  return out;\n"
            "}\n"
        ).replace("SCHEMA_PLACEHOLDER", schema_compact).replace("ALIASES_PLACEHOLDER", aliases_compact)

    return (
        "Return ONLY TypeScript code. No markdown. No comments. No explanation.\n"
        "Generate fully working deterministic code.\n"
        "Hard requirements:\n"
        "1) Keep the provided interface and function signature exactly.\n"
        "2) base64file is CSV in base64 (not JSON). Decode and parse it at runtime.\n"
        "3) CSV separator is ';', support quoted values and newlines inside quotes.\n"
        "4) Build a header map from CSV columns to schema keys by normalized names.\n"
        "5) Convert values by schema example type:\n"
        "   - number: parse decimal, comma as decimal separator supported\n"
        "   - boolean: true for [1,true,yes,y,да], false otherwise\n"
        "   - string: string value\n"
        "   - null in schema means string | null (empty -> null)\n"
        "6) Do not use `as any` for result or return value.\n"
        "7) Ignore unknown CSV columns.\n"
        "8) Return DealData[] built from real CSV rows.\n"
        "9) Use regex normalization without unicode property escapes (NO \\p{...}).\n"
        "10) If key is dealStageFinal, derive it from stage text: true for 'закрыта'/'отклонена', else false.\n"
        "Schema object:\n"
        f"{schema_compact}\n"
        "Schema keys:\n"
        f"{schema_keys_compact}\n"
        "Header aliases map (schemaKey -> candidate CSV headers):\n"
        f"{aliases_compact}\n"
        f"{interface_ts}\n"
        "export default function (base64file: string): DealData[] {\n"
        "  const schema = SCHEMA_PLACEHOLDER;\n"
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
        "        if (inQuotes && text[i + 1] === '\"') { cell += '\"'; i++; }\n"
        "        else { inQuotes = !inQuotes; }\n"
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
        "    if (example === null) { const t = String(value || \"\").trim(); return t === \"\" ? null : t; }\n"
        "    return String(value ?? \"\");\n"
        "  };\n"
        "  const csv = decodeBase64(base64file);\n"
        "  const rows = parseCsv(csv);\n"
        "  if (!rows.length) return [];\n"
        "  const aliases: Record<string, string[]> = ALIASES_PLACEHOLDER;\n"
        "  const headers = rows[0].map((h) => String(h ?? \"\").trim());\n"
        "  const headerIndex = new Map<string, number>();\n"
        "  headers.forEach((h, i) => headerIndex.set(norm(h), i));\n"
        "  const keys = Object.keys(schema);\n"
        "  const out: DealData[] = [];\n"
        "  for (let r = 1; r < rows.length; r++) {\n"
        "    const line = rows[r];\n"
        "    const obj: Record<string, unknown> = {};\n"
        "    for (const key of keys) {\n"
        "      const candidates = [key, ...(aliases[key] ?? [])];\n"
        "      let idx: number | undefined = undefined;\n"
        "      for (const name of candidates) {\n"
        "        const found = headerIndex.get(norm(name));\n"
        "        if (found !== undefined) { idx = found; break; }\n"
        "      }\n"
        "      const raw = idx === undefined ? \"\" : String(line[idx] ?? \"\");\n"
        "      if (key === \"dealStageFinal\") {\n"
        "        const stageIdx = headerIndex.get(norm(\"Стадия (Сделка)\"));\n"
        "        const stageRaw = stageIdx === undefined ? \"\" : String(line[stageIdx] ?? \"\");\n"
        "        const st = stageRaw.trim().toLowerCase();\n"
        "        obj[key] = st === \"закрыта\" || st === \"отклонена\";\n"
        "      } else {\n"
        "        obj[key] = cast(raw, (schema as Record<string, unknown>)[key]);\n"
        "      }\n"
        "    }\n"
        "    out.push(obj as DealData);\n"
        "  }\n"
        "  return out;\n"
        "}\n"
    ).replace("SCHEMA_PLACEHOLDER", schema_compact).replace("ALIASES_PLACEHOLDER", aliases_compact)

