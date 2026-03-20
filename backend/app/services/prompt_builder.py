import json
from typing import Any

from app.utils.helpers import ensure_json_object


def _infer_ts_type(value: Any) -> str:
    if value is None:
        return "any"
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
) -> str:
    extracted_compact = json.dumps(extracted_input_json, ensure_ascii=False, separators=(",", ":"))
    schema = ensure_json_object(schema_obj)
    schema_keys = list(schema.keys())
    schema_keys_compact = json.dumps(schema_keys, ensure_ascii=False, separators=(",", ":"))

    # Token-minimal: provide a full compilable template with deterministic mapping.
    # The model only needs to return code (we still call it, but the logic is already explicit).
    out_lines = []
    for k in schema_keys:
        key_json = json.dumps(k, ensure_ascii=False)
        out_lines.append(f"      out[{key_json}]=get(row,{key_json});")
    out_body = "\n".join(out_lines)

    return (
        "Return ONLY TypeScript code. No markdown. No comments. No explanation.\n"
        "Keep output short and deterministic.\n"
        "Rules:\n"
        "1) Use the provided interface and export default function signature exactly.\n"
        "2) Build rows ONLY from schema keys (ignore unknown columns).\n"
        "3) If an input row has a single key that contains ';', treat it as a broken CSV row:\n"
        "   - split that key by ';' to get header columns;\n"
        "   - split the single value by ';' to get values;\n"
        "   - map by index header[i] -> value[i].\n"
        "4) Do not inline huge constants; use compact logic.\n"
        "Schema keys:\n"
        f"{schema_keys_compact}\n"
        "Extracted input JSON:\n"
        f"{extracted_compact}\n"
        f"{interface_ts}\n"
        "export default function (base64file: string): DealData[] {\n"
        "  void base64file;\n"
        "  const extracted = [] as any;\n"
        "  const result: DealData[] = [];\n"
        "  const norm=(s:any)=>String(s??'').toLowerCase().replace(/[^a-z0-9]/g,'');\n"
        "  const get=(row:any, key:string)=>{\n"
        "    const keys=Object.keys(row||{});\n"
        "    const k=keys.find(x=>norm(x)===norm(key));\n"
        "    return k ? row[k] : '';\n"
        "  };\n"
        "  if(Array.isArray(extracted)){\n"
        "    for(const row of extracted){\n"
        "      if(!row||typeof row!=='object') continue;\n"
        "      const out:any={};\n"
        f"{out_body}\n"
        "      result.push(out as DealData);\n"
        "    }\n"
        "  }\n"
        "  return result;\n"
        "}\n"
    )

