import json
import re
from typing import Any, Dict, Iterable, List, Optional


def truncate_string(s: str, max_len: int) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def to_compact_json(obj: Any, *, ensure_ascii: bool = False) -> str:
    return json.dumps(obj, ensure_ascii=ensure_ascii, separators=(",", ":"))


def extract_typescript_code(text: str) -> str:
    """
    Extract only the TypeScript code from an LLM response.

    The model may return fenced code blocks or plain text. We prefer the first code fence.
    """
    if not text:
        return ""

    fence_match = re.search(
        r"```(?:[a-zA-Z0-9_-]+)?\s*([\s\S]*?)\s*```",
        text,
        flags=re.IGNORECASE,
    )
    if fence_match:
        code = fence_match.group(1).strip()
        return code

    export_default = re.search(
        r"(export\s+default\s+function[\s\S]*$)", text, flags=re.IGNORECASE
    )
    if export_default:
        return export_default.group(1).strip()

    return text.strip()


def code_parses_base64_upload_as_json(code: str) -> bool:
    """
    Detect JSON.parse(atob(base64file)) and similar anti-patterns.
    `base64file` is an encoded spreadsheet/document, not a JSON string.
    """
    if not code:
        return False
    low = code.lower()
    if "json.parse(base64file)" in low:
        return True
    if re.search(r"json\.parse\s*\(\s*atob\s*\(", low):
        return True
    if re.search(r"json\.parse\s*\(\s*buffer\.from\s*\(\s*[^)]*base64file", low):
        return True
    if re.search(r"json\.parse\s*\([^)]*\bbase64file\b", low):
        return True
    return False


def looks_like_incomplete_typescript(code: str) -> bool:
    """
    Heuristic check for truncated model output.
    We keep it intentionally simple and fast.
    """
    if not code or "export default function" not in code:
        return True

    stripped = code.strip()
    if stripped.endswith(",") or stripped.endswith(":") or stripped.endswith("="):
        return True

    if 'get(row, "' in stripped and not stripped.endswith("}"):
        return True

    if code.count("{") != code.count("}"):
        return True
    if code.count("(") != code.count(")"):
        return True
    if code.count("[") != code.count("]"):
        return True

    return False


_NON_ALNUM_RE = re.compile(r"[^a-zA-Z0-9]+")


def normalize_key(key: str) -> str:
    key = key or ""
    key = key.strip().lower()
    key = _NON_ALNUM_RE.sub("", key)
    return key


def best_match_key(target_key: str, candidates: Iterable[str]) -> Optional[str]:
    """
    Pick the "closest" candidate key based on normalized string similarity.
    For MVP we keep it intentionally simple (O(n)).
    """
    target = normalize_key(target_key)
    if not target:
        return None

    best = None
    best_score = -1
    for c in candidates:
        nc = normalize_key(c)
        if not nc:
            continue
        if nc == target:
            return c

        score = 0
        if target in nc or nc in target:
            score += 2
        if nc.startswith(target[: max(3, len(target) // 2)]) or target.startswith(nc[: max(3, len(nc) // 2)]):
            score += 1

        if score > best_score:
            best_score = score
            best = c

    return best


def ensure_json_object(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return obj[0]
    raise ValueError("schema must be a JSON object or an array with at least one object")

