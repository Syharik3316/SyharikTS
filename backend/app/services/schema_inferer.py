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

    # Fallback to example date.
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

    # Date-like keys always return ISO string.
    if _DATE_KEY_RE.search(key):
        if _looks_like_date_string(s):
            return _normalize_date_string(s)
        return "2026-01-01"

    # Boolean
    sl = s.lower()
    if sl in {"true", "false"}:
        return False
    if sl in {"yes", "no", "y", "n"}:
        return False
    if sl in {"1", "0"}:
        # Ambiguous; use number placeholder.
        return 0

    # Number (int/float)
    if _INT_RE.match(s):
        return 0

    if _FLOAT_RE.match(s) and any(ch in s for ch in [".", ","]):
        return 0.0

    # Default placeholder: schema example, not real content.
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

        # Pick the most meaningful record instead of blindly taking the first one.
        # This avoids noisy one-column pseudo-rows from complex DOCX tables.
        def _is_meaningful_key(k: str) -> bool:
            ks = str(k or "").strip()
            if not ks:
                return False
            # Penalize very long "header-like" keys.
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
            # Strongly penalize single-key noisy rows.
            if len(keys) == 1 and len(str(keys[0])) > 40:
                score -= 25
            if score > best_score:
                best_score = score
                best = rec

        first = best if isinstance(best, dict) else extracted_records[0]
        if not isinstance(first, dict) or not first:
            return {"value": "string"}

        schema: Dict[str, Any] = {}
        for k, v in first.items():
            schema[str(k)] = _normalize_primitive_value(v, str(k))
        return schema

    # Unknown
    return {"value": "string"}

