import json
from typing import Any

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
    # FATCA-oriented aliases
    "organizationName": ["Наименование организации", "Организация", "Наименование"],
    "innOrKio": ["ИНН/КИО", "ИНН", "КИО"],
    "isResidentRF": [
        "Является ли выгодоприобретатель налоговым резидентом только в Российской Федерации?",
        "Налоговый резидент РФ",
    ],
    "isTaxResidencyOnlyRF": [
        "Являются ли физические лица прямо или косвенно контролирующие выгодоприобретателя налоговыми резидентами только в Российской Федерации?",
        "Контролирующие лица резиденты только в РФ",
    ],
    "fatcaBeneficiaryOptionList": [
        "Является ли хотя бы одно из следующих утверждений для выгодоприобретателя верным:",
        "FATCA утверждения",
        "FATCA",
    ],
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
    schema_requires_input_wrapper = isinstance(schema.get("input"), list)
    schema_compact = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    schema_keys = list(schema.keys())
    aliases_compact = json.dumps(_build_aliases_for_schema(schema), ensure_ascii=False, separators=(",", ":"))
    schema_keys_compact = json.dumps(schema_keys, ensure_ascii=False, separators=(",", ":"))
    payload_obj = ensure_json_object(extracted_input_json) if isinstance(extracted_input_json, dict) else {
        "kind": file_kind,
        "records": extracted_input_json if isinstance(extracted_input_json, list) else [],
        "text": "",
        "tables": [],
        "metadata": {"kind": file_kind},
    }
    payload_compact = json.dumps(payload_obj, ensure_ascii=False, separators=(",", ":"))
    if len(payload_compact) > 12000:
        payload_compact = payload_compact[:12000] + "…"

    return (
        "Return ONLY TypeScript code. No markdown/comments/explanations.\n"
        "Generate deterministic TypeScript parser for ALL formats using a single universal strategy.\n"
        "Hard requirements:\n"
        "1) Keep interface + function signature exactly.\n"
        "2) If base64file is null/undefined/empty after trim -> return [].\n"
        "3) EXTRACTED_INPUT_JSON is source-of-truth (already extracted server-side).\n"
        "4) Preserve top-level schema shape exactly (incl. nested arrays/objects and input:[]).\n"
        f"4.1) Input-wrapper rule: {'schema contains input[] -> output item MUST include input array populated from extracted data.' if schema_requires_input_wrapper else 'no forced input-wrapper unless schema explicitly requires it.'}\n"
        "5) Never collapse arrays/objects to scalars like {input:''}.\n"
        "6) Recursive cast by schema example types: string/number/boolean/null/object/array.\n"
        "7) Data priority: extracted.records -> extracted.tables rows -> extracted.text hints.\n"
        "7.1) Use Header aliases map for semantic key matching.\n"
        "7.2) Checkbox markers [X, x, ☑, ☒, ✓] mean selected.\n"
        "8) Unknown fields must not break output; fill defaults by schema shape.\n"
        "9) STRICT KEYS MODE: output keys must be ONLY from user schema; never add extra keys.\n"
        "10) If schema came from array example, use ONLY first-object keys; do not invent fields.\n"
        "11) Key matching strictness: for short keys/aliases (<= 8 chars after normalization), ONLY exact normalized match; never substring match.\n"
        "12) No `as any`.\n"
        "Schema object:\n"
        f"{schema_compact}\n"
        "Schema keys:\n"
        f"{schema_keys_compact}\n"
        "Header aliases map:\n"
        f"{aliases_compact}\n"
        "Extracted input payload:\n"
        f"{payload_compact}\n"
        f"{interface_ts}\n"
        "export default function (base64file: string): DealData[] {\n"
        "  if (base64file == null || !String(base64file).trim()) return [];\n"
        "  const schema: Record<string, unknown> = SCHEMA_PLACEHOLDER;\n"
        "  const extracted = EXTRACTED_PLACEHOLDER as Record<string, unknown>;\n"
        "  const aliases: Record<string, string[]> = ALIASES_PLACEHOLDER;\n"
        "  const records = Array.isArray(extracted.records) ? extracted.records : [];\n"
        "  const tables = Array.isArray(extracted.tables) ? extracted.tables : [];\n"
        "  const text = String(extracted.text ?? \"\");\n"
        "  const norm = (s: unknown): string => String(s ?? \"\").toLowerCase().replace(/[^a-z0-9а-яё]+/gi, \"\");\n"
        "  const isMarked = (v: unknown): boolean => /(^|\\s)[xх☑☒✓](\\s|$)/i.test(String(v ?? \"\"));\n"
        "  const pickFromRow = (row: Record<string, unknown>, key: string): unknown => {\n"
        "    const candidates = [key, ...(aliases[key] ?? [])];\n"
        "    const entries = Object.entries(row || {});\n"
        "    for (const c of candidates) {\n"
        "      const want = norm(c);\n"
        "      const shortKey = want.length <= 8;\n"
        "      for (const [rk, rv] of entries) {\n"
        "        const got = norm(rk);\n"
        "        if (got === want) return rv;\n"
        "        if (!shortKey && (got.includes(want) || want.includes(got))) return rv;\n"
        "      }\n"
        "    }\n"
        "    return row[key];\n"
        "  };\n"
        "  const toBool = (v: unknown): boolean => [\"1\",\"true\",\"yes\",\"y\",\"да\"].includes(String(v ?? \"\").trim().toLowerCase());\n"
        "  const toNum = (v: unknown): number => {\n"
        "    const n = Number(String(v ?? \"\").trim().replace(/\\s+/g, \"\").replace(\",\", \".\"));\n"
        "    return Number.isFinite(n) ? n : 0;\n"
        "  };\n"
        "  const defaultFromExample = (ex: unknown): unknown => {\n"
        "    if (Array.isArray(ex)) return [];\n"
        "    if (ex === null) return null;\n"
        "    if (typeof ex === \"number\") return 0;\n"
        "    if (typeof ex === \"boolean\") return false;\n"
        "    if (typeof ex === \"string\") return \"\";\n"
        "    if (ex && typeof ex === \"object\") {\n"
        "      const out: Record<string, unknown> = {};\n"
        "      for (const [k, subEx] of Object.entries(ex as Record<string, unknown>)) out[k] = defaultFromExample(subEx);\n"
        "      return out;\n"
        "    }\n"
        "    return \"\";\n"
        "  };\n"
        "  const castByExample = (val: unknown, ex: unknown): unknown => {\n"
        "    if (Array.isArray(ex)) {\n"
        "      const itemEx = ex.length ? ex[0] : \"\";\n"
        "      if (Array.isArray(val)) return val.map((x) => castByExample(x, itemEx));\n"
        "      return [];\n"
        "    }\n"
        "    if (ex === null) { const t = String(val ?? \"\").trim(); return t ? String(val) : null; }\n"
        "    if (typeof ex === \"number\") return toNum(val);\n"
        "    if (typeof ex === \"boolean\") return toBool(val);\n"
        "    if (typeof ex === \"string\") return String(val ?? \"\");\n"
        "    if (ex && typeof ex === \"object\") {\n"
        "      const src = (val && typeof val === \"object\") ? (val as Record<string, unknown>) : {};\n"
        "      const out: Record<string, unknown> = {};\n"
        "      for (const [k, subEx] of Object.entries(ex as Record<string, unknown>)) out[k] = castByExample(src[k], subEx);\n"
        "      return out;\n"
        "    }\n"
        "    return val;\n"
        "  };\n"
        "  const bestRows = records.length\n"
        "    ? records\n"
        "    : tables.flatMap((t) => Array.isArray((t as Record<string, unknown>).rows) ? ((t as Record<string, unknown>).rows as unknown[]) : []);\n"
        "  if (Array.isArray((schema as Record<string, unknown>).input)) {\n"
        "    const exampleItem = ((schema as Record<string, unknown>).input as unknown[])[0] ?? {};\n"
        "    const mapped = bestRows.map((row) => {\n"
        "      const src = (row && typeof row === \"object\") ? (row as Record<string, unknown>) : {};\n"
        "      const aligned: Record<string, unknown> = {};\n"
        "      for (const k of Object.keys((exampleItem && typeof exampleItem === \"object\") ? (exampleItem as Record<string, unknown>) : {})) {\n"
        "        aligned[k] = pickFromRow(src, k);\n"
        "      }\n"
        "      return castByExample(aligned, exampleItem);\n"
        "    });\n"
        "    const result = { ...(defaultFromExample(schema) as Record<string, unknown>), input: mapped };\n"
        "    return [result as DealData];\n"
        "  }\n"
        "  const base = defaultFromExample(schema) as Record<string, unknown>;\n"
        "  const row0 = bestRows[0] ?? {};\n"
        "  const alignedRow0: Record<string, unknown> = {};\n"
        "  for (const key of Object.keys(schema)) alignedRow0[key] = pickFromRow((row0 && typeof row0 === \"object\") ? (row0 as Record<string, unknown>) : {}, key);\n"
        "  const merged = castByExample(alignedRow0, schema) as Record<string, unknown>;\n"
        "  for (const [k, v] of Object.entries(merged)) base[k] = v;\n"
        "  if (!bestRows.length && text) {\n"
        "    for (const key of Object.keys(base)) {\n"
        "      if (typeof base[key] === \"string\" && !String(base[key] || \"\").trim()) {\n"
        "        const r = new RegExp(`${key}\\\\s*[:\\\\-]\\\\s*([^\\\\n;]+)`, \"i\");\n"
        "        const m = text.match(r);\n"
        "        if (m) base[key] = m[1].trim();\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "  return [base as DealData];\n"
        "}\n"
    ).replace("SCHEMA_PLACEHOLDER", schema_compact).replace("EXTRACTED_PLACEHOLDER", payload_compact).replace("ALIASES_PLACEHOLDER", aliases_compact)

