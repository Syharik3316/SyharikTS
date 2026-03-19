import datetime
import re
from typing import Any, Dict, List, Optional, Tuple

from app.utils.helpers import ensure_json_object


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
        return ""

    if isinstance(value, (int, float, bool)):
        return value

    s = str(value).strip()
    if not s:
        return ""

    # Date-like keys always return ISO string.
    if _DATE_KEY_RE.search(key):
        if _looks_like_date_string(s):
            return _normalize_date_string(s)
        return "2026-01-01"

    # Boolean
    sl = s.lower()
    if sl in {"true", "false"}:
        return sl == "true"
    if sl in {"yes", "no", "y", "n"}:
        return sl in {"yes", "y"}
    if sl in {"1", "0"}:
        # Ambiguous; treat as int for safety.
        return int(sl)

    # Number (int/float)
    if _INT_RE.match(s):
        try:
            return int(s)
        except Exception:
            return s

    if _FLOAT_RE.match(s) and any(ch in s for ch in [".", ","]):
        try:
            return float(s.replace(",", "."))
        except Exception:
            return s

    # Default: string example.
    if len(s) > 120:
        return s[:120] + "…"
    return s


def infer_schema_from_extracted(file_kind: str, extracted_input_json: Any) -> Dict[str, Any]:
    """
    Deterministic schema inference for MVP with minimal/no LLM tokens.
    """
    if file_kind in {"csv", "xls", "xlsx"}:
        if not isinstance(extracted_input_json, list) or not extracted_input_json:
            return {"value": "string"}

        first = extracted_input_json[0]
        if not isinstance(first, dict) or not first:
            return {"value": "string"}

        schema: Dict[str, Any] = {}
        for k, v in first.items():
            schema[str(k)] = _normalize_primitive_value(v, str(k))
        return schema

    if file_kind in {"pdf", "docx", "png", "jpg"}:
        # We don't reliably infer table columns from free text in MVP.
        # Provide a minimal schema that still compiles and is useful for testing.
        if isinstance(extracted_input_json, dict):
            text = extracted_input_json.get("text") or ""
        else:
            text = ""
        text = (text or "").strip()
        if len(text) > 500:
            text = text[:500] + "…"
        return {"text": text, "value": "string"}

    # Unknown
    return {"value": "string"}

