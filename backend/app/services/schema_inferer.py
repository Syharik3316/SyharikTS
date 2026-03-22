import re
from typing import Any, Dict


_DATE_KEY_RE = re.compile(r"(date|дата|создан|обнов|last|update)", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T\s].*)?$")
_DMY_DATE_RE = re.compile(r"^(\d{2})[./-](\d{2})[./-](\d{4})$")
_YMD_DATE_RE = re.compile(r"^(\d{4})[./-](\d{2})[./-](\d{2})$")
_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+([.,]\d+)?$")


def _looks_like_date_string(s: str) -> bool:
    return bool(_ISO_DATE_RE.match(s) or _DMY_DATE_RE.match(s) or _YMD_DATE_RE.match(s))


def _normalize_date_string(s: str) -> str:
    s = (s or "").strip()
    if _ISO_DATE_RE.match(s):
        return s[:10]

    m = _DMY_DATE_RE.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}"

    m = _YMD_DATE_RE.match(s)
    if m:
        yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}"

    return "2026-01-01"


def _normalize_primitive_value(value: Any, key: str) -> Any:
    """
    Convert extracted string value to an example primitive type for schema inference.
    """
    if value is None:
        return "string"

    if isinstance(value, (int, float, bool)):
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return 0
        return 0.0

    s = str(value).strip()
    if not s:
        return "string"

    if _DATE_KEY_RE.search(key):
        if _looks_like_date_string(s):
            return _normalize_date_string(s)
        return "2026-01-01"

    sl = s.lower()
    if sl in {"true", "false"}:
        return False
    if sl in {"yes", "no", "y", "n"}:
        return False
    if sl in {"1", "0"}:
        return 0

    if _INT_RE.match(s):
        return 0

    if _FLOAT_RE.match(s) and any(ch in s for ch in [".", ","]):
        return 0.0

    return "string"


def infer_schema_from_extracted(file_kind: str, extracted_input_json: Any) -> Dict[str, Any]:
    """
    Deterministic schema inference for MVP with minimal/no LLM tokens.
    """
    if isinstance(extracted_input_json, dict):
        if "records" in extracted_input_json and isinstance(extracted_input_json.get("records"), list):
            extracted_records = extracted_input_json.get("records") or []
        else:
            extracted_records = []
        extracted_text = str(extracted_input_json.get("text") or "")
    else:
        extracted_records = extracted_input_json if isinstance(extracted_input_json, list) else []
        extracted_text = ""

    if file_kind in {"csv", "xls", "xlsx", "pdf", "docx", "png", "jpg", "tiff", "txt", "md", "rtf", "odt", "xml", "epub", "fb2", "doc"}:
        if not extracted_records:
            if extracted_text:
                return {"text": "string", "value": "string"}
            return {"value": "string"}

        def _is_meaningful_key(k: str) -> bool:
            ks = str(k or "").strip()
            if not ks:
                return False
            if len(ks) > 100:
                return False
            return True

        best: Dict[str, Any] | None = None
        best_score = -1
        for rec in extracted_records:
            if not isinstance(rec, dict) or not rec:
                continue
            keys = [str(k) for k in rec.keys()]
            meaningful_keys = [k for k in keys if _is_meaningful_key(k)]
            score = len(meaningful_keys) * 10 + len(keys)
            if len(keys) == 1 and len(str(keys[0])) > 40:
                score -= 25
            if score > best_score:
                best_score = score
                best = rec

        first = best if isinstance(best, dict) else (extracted_records[0] if extracted_records else None)
        if not isinstance(first, dict) or not first:
            return {"value": "string"}

        # Union of keys across all parsed rows so sparse/wide CSV rows do not drop columns
        # that appear only in some lines (schema must cover the full extracted structure).
        ordered_keys: list[str] = []
        seen: set[str] = set()
        for rec in extracted_records:
            if not isinstance(rec, dict):
                continue
            for k in rec.keys():
                sk = str(k).strip()
                if not sk:
                    continue
                if sk not in seen:
                    seen.add(sk)
                    ordered_keys.append(sk)

        def _sample_value_for_key(key: str) -> Any:
            for rec in extracted_records:
                if not isinstance(rec, dict) or key not in rec:
                    continue
                v = rec[key]
                if v is None:
                    continue
                if isinstance(v, str) and not str(v).strip():
                    continue
                return v
            return first.get(key, "")

        schema: Dict[str, Any] = {}
        for k in ordered_keys:
            v = _sample_value_for_key(k)
            schema[k] = _normalize_primitive_value(v, k)
        return schema

    return {"value": "string"}

