import difflib
import json
import os
import re
from typing import Any

from app.utils.helpers import ensure_json_object
from app.services.schema_aliases import (
    build_aliases_for_schema,
    build_spreadsheet_aliases_for_llm_prompt,
    strip_schema_meta_for_output,
)

_SPREADSHEET_FILE_KINDS = frozenset({"csv", "xls", "xlsx"})


def _spreadsheet_csv_delimiter(payload_obj: dict[str, Any]) -> str:
    meta = payload_obj.get("metadata") if isinstance(payload_obj.get("metadata"), dict) else {}
    raw = meta.get("csv_delimiter", ";")
    if not isinstance(raw, str) or len(raw) != 1:
        return ";"
    if raw in {",", ";", "\t", "|"}:
        return raw
    return ";"


def _read_positive_int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        val = int(raw)
        return val if val > 0 else default
    except ValueError:
        return default


def _prompt_max_schema_json_chars() -> int:
    return _read_positive_int_env("PROMPT_MAX_SCHEMA_JSON_CHARS", 400_000)


def _prompt_schema_example_string_max_chars() -> int:
    return _read_positive_int_env("PROMPT_SCHEMA_EXAMPLE_STRING_MAX_CHARS", 512)


def _prompt_max_schema_field_names() -> int:
    return _read_positive_int_env("PROMPT_MAX_SCHEMA_FIELD_NAMES", 800)


def _prompt_max_interface_top_level_keys() -> int:
    """Limit DealData interface size in LLM prompt (full shape also appears in the JSON example block)."""
    return _read_positive_int_env("PROMPT_MAX_INTERFACE_TOP_LEVEL_KEYS", 200)


def _prompt_max_extracted_json_chars() -> int:
    return _read_positive_int_env("PROMPT_MAX_EXTRACTED_JSON_CHARS", 120_000)


def _prompt_max_extracted_record_rows() -> int:
    return _read_positive_int_env("PROMPT_MAX_EXTRACTED_RECORD_ROWS", 800)


def _prompt_max_spreadsheet_aliases_json_chars() -> int:
    return _read_positive_int_env("PROMPT_MAX_SPREADSHEET_ALIASES_JSON_CHARS", 12_000)


def _prompt_max_schema_example_pretty_chars() -> int:
    return _read_positive_int_env("PROMPT_MAX_SCHEMA_EXAMPLE_PRETTY_CHARS", 16_000)


def _schema_example_json_for_prompt(schema: dict[str, Any]) -> str:
    """
    Human-readable JSON example for the LLM (not an embedded TS literal).
    Falls back to compact JSON if pretty-print exceeds the char budget.
    """
    base = strip_schema_meta_for_output(dict(schema))
    max_pretty = _prompt_max_schema_example_pretty_chars()
    slim = _truncate_schema_example_strings(
        base, max_len=_prompt_schema_example_string_max_chars()
    )
    pretty = json.dumps(slim, ensure_ascii=False, indent=2)
    if len(pretty) <= max_pretty:
        return pretty
    return _schema_compact_for_prompt(base)


def _truncate_schema_example_strings(obj: Any, *, max_len: int, max_list_items: int = 200) -> Any:
    if isinstance(obj, dict):
        return {k: _truncate_schema_example_strings(v, max_len=max_len, max_list_items=max_list_items) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_truncate_schema_example_strings(v, max_len=max_len, max_list_items=max_list_items) for v in obj[:max_list_items]]
    if isinstance(obj, str) and len(obj) > max_len:
        return obj[:max_len] + "…"
    return obj


def _schema_compact_for_prompt(schema: dict[str, Any]) -> str:
    max_chars = _prompt_max_schema_json_chars()
    base_str_limit = _prompt_schema_example_string_max_chars()
    keys = list(schema.keys())
    str_limit = base_str_limit
    while keys:
        subset = {k: schema[k] for k in keys}
        slim = _truncate_schema_example_strings(subset, max_len=str_limit)
        compact = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))
        if len(compact) <= max_chars:
            return compact
        if str_limit > 64:
            str_limit = max(64, str_limit // 2)
            continue
        if len(keys) > 1:
            keys = keys[:-1]
            str_limit = base_str_limit
            continue
        return compact
    return "{}"


def _normalize_key_for_similarity(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.lower(), flags=re.UNICODE)


def _field_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(None, left, right).ratio()


def _build_column_mapping_hints(schema: dict[str, Any], source_keys: list[str]) -> str:
    normalized_sources = [(h, _normalize_key_for_similarity(h)) for h in source_keys if str(h).strip()]
    target_keys: list[str] = []
    if isinstance(schema.get("input"), list) and schema["input"] and isinstance(schema["input"][0], dict):
        target_keys = [str(k) for k in schema["input"][0].keys()]
    else:
        target_keys = [str(k) for k in schema.keys()]

    hints: list[dict[str, str]] = []
    for field in target_keys:
        fn = _normalize_key_for_similarity(field)
        if not fn:
            continue
        best_h = ""
        best_sc = 0.0
        for header, hn in normalized_sources:
            if not hn:
                continue
            sc = _field_similarity(fn, hn)
            if len(fn) >= 4 and len(hn) >= 4 and (fn in hn or hn in fn):
                sc = max(sc, 0.88)
            if sc > best_sc:
                best_sc = sc
                best_h = header
        if best_h and best_sc >= 0.62:
            hints.append({"target": field, "source": best_h})
    compact = json.dumps(hints[:80], ensure_ascii=False, separators=(",", ":"))
    return compact


def _union_record_keys(records: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for rec in records:
        if not isinstance(rec, dict):
            continue
        for k in rec.keys():
            sk = str(k)
            if sk not in seen:
                seen.add(sk)
                out.append(sk)
    return out


def _extracted_preview_for_prompt(payload_obj: dict[str, Any]) -> str:
    """
    Compact JSON of parsed file content so the LLM can fill `aliases` and preserve all columns.
    Size-capped via PROMPT_MAX_EXTRACTED_JSON_CHARS / PROMPT_MAX_EXTRACTED_RECORD_ROWS.
    """
    max_chars = _prompt_max_extracted_json_chars()
    max_rows = _prompt_max_extracted_record_rows()
    base_str_limit = min(_prompt_schema_example_string_max_chars(), 1024)

    raw_records = payload_obj.get("records") if isinstance(payload_obj.get("records"), list) else []
    records_slice = raw_records[:max_rows] if max_rows > 0 else raw_records

    tables_in = payload_obj.get("tables") if isinstance(payload_obj.get("tables"), list) else []
    tables_out: list[dict[str, Any]] = []
    for t in tables_in[:5]:
        if not isinstance(t, dict):
            continue
        headers = t.get("headers")
        rows = t.get("rows") if isinstance(t.get("rows"), list) else []
        raw = t.get("raw") if isinstance(t.get("raw"), list) else []
        tables_out.append(
            {
                "headers": headers if isinstance(headers, list) else [],
                "row_count": len(rows),
                "raw_row_count": len(raw),
            }
        )

    text_in = str(payload_obj.get("text") or "")
    meta_in = payload_obj.get("metadata") if isinstance(payload_obj.get("metadata"), dict) else {}

    # Match _unified_extracted_payload keys so embedded reference TS (`extracted.text`) is populated for LLM prompts.
    preview: dict[str, Any] = {
        "kind": payload_obj.get("kind"),
        "records": records_slice,
        "tables": tables_out,
        "text": text_in,
        "metadata": meta_in,
    }

    str_limit = base_str_limit
    while str_limit >= 64:
        slim = dict(preview)
        slim["records"] = _truncate_schema_example_strings(records_slice, max_len=str_limit, max_list_items=80)
        slim["text"] = text_in[: str_limit * 4] + ("…" if len(text_in) > str_limit * 4 else "")
        slim["metadata"] = _truncate_schema_example_strings(meta_in, max_len=min(str_limit, 256), max_list_items=50)
        compact = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))
        if len(compact) <= max_chars:
            return compact
        str_limit = max(64, str_limit // 2)

    slim = {
        "kind": preview.get("kind"),
        "records": _truncate_schema_example_strings(records_slice, max_len=64, max_list_items=20),
        "tables": tables_out,
        "text": text_in[:512] + ("…" if len(text_in) > 512 else ""),
        "metadata": {k: meta_in[k] for k in list(meta_in.keys())[:20]},
    }
    return json.dumps(slim, ensure_ascii=False, separators=(",", ":"))


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


def _infer_ts_type(value: Any, *, depth: int = 0) -> str:
    if depth > 14:
        return "unknown"
    if value is None:
        return "string | null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        if not value:
            return "unknown[]"
        inner = _infer_ts_type(value[0], depth=depth + 1)
        return f"Array<{inner}>"
    if isinstance(value, dict):
        if not value:
            return "Record<string, unknown>"
        ind = "  " * (depth + 1)
        base = "  " * depth
        lines = [f"{ind}{json.dumps(str(k), ensure_ascii=False)}: {_infer_ts_type(v, depth=depth + 1)};" for k, v in value.items()]
        return "{\n" + "\n".join(lines) + f"\n{base}}}"
    return "unknown"


def build_interface_ts(schema_obj: Any, *, interface_name: str = "DealData") -> str:
    """
    Build a compact TS interface from the user JSON example.
    """
    obj = ensure_json_object(schema_obj)
    fields = []
    for k, v in obj.items():
        ts_t = _infer_ts_type(v)
        key_ts = json.dumps(str(k), ensure_ascii=False)
        fields.append(f"{key_ts}: {ts_t};")
    body = "\n  ".join(fields)
    return f"interface {interface_name} {{\n  {body}\n}}"


def build_interface_ts_for_llm_prompt(schema_obj: Any, *, interface_name: str = "DealData") -> str:
    """
    Interface block for the LLM prompt only. Large schemas duplicate keys in `interface` + `const schema`;
    trimming top-level keys here keeps prompts small (timeouts / context limits) while `_schema_compact_for_prompt`
    still carries the full example shape as JSON.
    """
    obj = ensure_json_object(schema_obj)
    max_keys = _prompt_max_interface_top_level_keys()
    keys = list(obj.keys())
    if len(keys) <= max_keys:
        return build_interface_ts(schema_obj, interface_name=interface_name)
    slim = {k: obj[k] for k in keys[:max_keys]}
    note = (
        f"// Prompt interface: first {max_keys} of {len(keys)} top-level fields. "
        "Full shape is in the OUTPUT_SHAPE_EXAMPLE JSON block in the user message.\n"
    )
    return note + build_interface_ts(slim, interface_name=interface_name)


def build_generation_prompt(
    extracted_input_json: Any,
    schema_obj: Any,
    *,
    interface_ts: str,
    file_kind: str,
) -> str:
    schema = ensure_json_object(schema_obj)
    example_json = _schema_example_json_for_prompt(schema)

    # Extract field names from schema
    def get_fields(obj, prefix=""):
        fields = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                fields.append(prefix + k)
                if isinstance(v, dict):
                    fields.extend(get_fields(v, prefix + k + "."))
                elif isinstance(v, list) and v and isinstance(v[0], dict):
                    fields.extend(get_fields(v[0], prefix + k + "."))
        return fields
    all_schema_fields = get_fields(schema)
    max_field_names = _prompt_max_schema_field_names()
    if len(all_schema_fields) > max_field_names:
        schema_fields = all_schema_fields[:max_field_names] + [
            f"… (+{len(all_schema_fields) - max_field_names} more)"
        ]
    else:
        schema_fields = all_schema_fields

    payload_obj = (
        ensure_json_object(extracted_input_json)
        if isinstance(extracted_input_json, dict)
        else {
            "kind": file_kind,
            "records": extracted_input_json if isinstance(extracted_input_json, list) else [],
            "text": "",
            "tables": [],
            "metadata": {"kind": file_kind},
        }
    )

    union_record_keys = _union_record_keys(payload_obj.get("records") if isinstance(payload_obj.get("records"), list) else [])
    table_header_keys: list[str] = []
    seen_hdr: set[str] = set()
    for tbl in payload_obj.get("tables") or []:
        if not isinstance(tbl, dict):
            continue
        hdrs = tbl.get("headers")
        if not isinstance(hdrs, list):
            continue
        for h in hdrs:
            sh = str(h).strip()
            if sh and sh not in seen_hdr:
                seen_hdr.add(sh)
                table_header_keys.append(sh)

    all_source_keys: list[str] = []
    seen_all: set[str] = set()
    for k in union_record_keys + table_header_keys:
        if k not in seen_all:
            seen_all.add(k)
            all_source_keys.append(k)

    if len(all_source_keys) > max_field_names:
        extracted_keys_lines = ", ".join(all_source_keys[:max_field_names]) + (
            f", … (+{len(all_source_keys) - max_field_names} more)"
        )
    else:
        extracted_keys_lines = ", ".join(all_source_keys)

    extracted_preview_str = _extracted_preview_for_prompt(payload_obj)
    mapping_hints_json = _build_column_mapping_hints(schema, all_source_keys)

    if file_kind not in _SPREADSHEET_FILE_KINDS:
        aliases_compact_doc = json.dumps(
            build_aliases_for_schema(schema, extracted=payload_obj),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return (
            "=== TASK ===\n"
            "Write a complete TypeScript module with a single `export default function (base64file: string): DealData[]`.\n"
            "The JSON under OUTPUT_SHAPE_EXAMPLE is only a sample of the desired result shape (not runtime data). "
            "Design helpers, decoding, and mapping yourself; the example is guidance, not code to paste.\n\n"
            "=== OUTPUT_SHAPE_EXAMPLE (JSON) ===\n"
            f"{example_json}\n\n"
            "=== DealData (TypeScript interface derived from the same schema) ===\n"
            f"{interface_ts}\n\n"
            f"=== FILE_KIND ===\n{file_kind}\n\n"
            f"TargetToSourceHints:{mapping_hints_json}\n\n"
            "=== SUGGESTED_HEADER_ALIASES (JSON; optional to embed or extend) ===\n"
            f"{aliases_compact_doc}\n\n"
            "=== PARSED_FILE_PREVIEW (JSON for this upload; common pattern: `const extracted = {...}` inside your function) ===\n"
            f"{extracted_preview_str}\n\n"
            "=== SCHEMA_FIELD_PATHS (for orientation) ===\n"
            f"{', '.join(schema_fields)}\n\n"
            "Requirements:\n"
            "- Output ONLY TypeScript source. Do not wrap the whole answer in markdown code fences. No npm imports.\n"
            "- NEVER JSON.parse(base64file) or JSON.parse(atob(base64file)): base64file is a binary file (xlsx/pdf/…), not JSON text. "
            "Embed PARSED_FILE_PREVIEW as `const extracted = {...}` or decode the file format properly.\n"
            "- Document / OCR: do not use parseCSV or delimiter-split as the main path unless the file is plain CSV text.\n"
            "- Map from preview.records first, then preview.text for gaps. Copy real values; never fabricate business data.\n"
            "- Flat example shape → one DealData per record row; `input` as array in the example → one DealData aggregating rows as that shape implies.\n"
            "- Use explicit types; do not use `any`.\n"
        )

    csv_delim = _spreadsheet_csv_delimiter(payload_obj)
    aliases_compact = json.dumps(
        build_spreadsheet_aliases_for_llm_prompt(
            schema,
            payload_obj,
            source_keys=all_source_keys,
            max_json_chars=_prompt_max_spreadsheet_aliases_json_chars(),
        ),
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return (
        "=== TASK ===\n"
        "Write a complete TypeScript module with a single `export default function (base64file: string): DealData[]`.\n"
        "Decode base64 to text, parse the spreadsheet/CSV table, and return DealData[].\n"
        "The JSON under OUTPUT_SHAPE_EXAMPLE is only the target shape; you implement parsing and column mapping.\n\n"
        "=== OUTPUT_SHAPE_EXAMPLE (JSON) ===\n"
        f"{example_json}\n\n"
        "=== DealData (TypeScript interface) ===\n"
        f"{interface_ts}\n\n"
        f"=== FILE_KIND ===\n{file_kind}\n\n"
        f"=== CSV_DELIMITER_HINT (from parsed metadata, single character) ===\n{json.dumps(csv_delim)}\n\n"
        "=== COLUMN_AND_HEADER_KEYS (from backend extract) ===\n"
        f"{extracted_keys_lines}\n\n"
        f"TargetToSourceHints:{mapping_hints_json}\n\n"
        "=== SUGGESTED_HEADER_ALIASES (JSON; optional) ===\n"
        f"{aliases_compact}\n\n"
        "=== PARSED_FILE_PREVIEW (JSON) ===\n"
        f"{extracted_preview_str}\n\n"
        "=== SCHEMA_FIELD_PATHS ===\n"
        f"{', '.join(schema_fields)}\n\n"
        "Requirements:\n"
        "- Output ONLY TypeScript source. No markdown fences around the full answer. No npm imports.\n"
        "- NEVER JSON.parse(base64file) or JSON.parse(atob(base64file)): the upload is a real file, not a JSON string.\n"
        "- Use the delimiter hint when splitting; handle quoted fields if you implement CSV parsing.\n"
        "- Map file headers to DealData; do not invent cell values.\n"
        "- If the interface includes `unmappedColumns`, put every non-mapped column there (header text → cell string).\n"
        "- Explicit types; no `any`.\n"
    )
