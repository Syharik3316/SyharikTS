import json
import os
from typing import Any

from app.utils.helpers import ensure_json_object


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
    """Limit DealData interface size in LLM prompt (full schema stays in embedded `const schema` JSON)."""
    return _read_positive_int_env("PROMPT_MAX_INTERFACE_TOP_LEVEL_KEYS", 200)


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
    str_limit = _prompt_schema_example_string_max_chars()
    keys = list(schema.keys())
    while keys:
        subset = {k: schema[k] for k in keys}
        slim = _truncate_schema_example_strings(subset, max_len=str_limit)
        compact = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))
        if len(compact) <= max_chars:
            return compact
        keys = keys[:-1]
    return "{}"


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
        "Full example shape is in `const schema` below.\n"
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
    schema_compact = _schema_compact_for_prompt(schema)

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

    # Sample keys from extracted to help LLM
    sample_keys = []
    if payload_obj.get("records") and len(payload_obj["records"]) > 0:
        record = payload_obj["records"][0]
        if isinstance(record, dict):
            sample_keys = list(record.keys())[:10]
    elif payload_obj.get("tables") and len(payload_obj["tables"]) > 0:
        table = payload_obj["tables"][0]
        if isinstance(table, dict) and "headers" in table:
            sample_keys = table["headers"][:10]

    return (
        "Return ONLY TypeScript code. No markdown, no comments, no explanations.\n"
        "Generate a deterministic TypeScript parser that converts a base64‑encoded CSV (semicolon separated) into an array of DealData.\n\n"
        f"{interface_ts}\n\n"
        "export default function (base64file: string): DealData[] {\n"
        "    if (!base64file.trim()) return [];\n"
        "    const decode = (s: string): string => { const r=s.trim(), p=r.includes('base64,')?r.slice(r.indexOf('base64,')+7):r, c=p.replace(/\\s/g,'').replace(/-/g,'+').replace(/_/g,'/').replace(/[^A-Za-z0-9+/=]/g,''); const pad=c.length%4; const cl=pad?c+'='.repeat(4-pad):c; try { return typeof Buffer!=='undefined'?Buffer.from(cl,'base64').toString('utf-8'):( ()=>{ const b=atob(cl), u=Uint8Array.from(b,ch=>ch.charCodeAt(0)); return new TextDecoder('utf-8').decode(u); } )(); } catch(e){ return ''; } };\n"
        "    const parseCSV = (t: string): string[][] => { const r=[]; let row=[], cell='', q=false; for(let i=0;i<t.length;i++){ const ch=t[i]; if(ch=='\"'){ if(q&&t[i+1]=='\"'){cell+='\"';i++;}else q=!q; }else if(ch==';'&&!q){ row.push(cell); cell=''; }else if((ch=='\\n'||ch=='\\r')&&!q){ if(ch=='\\r'&&t[i+1]=='\\n')i++; row.push(cell); cell=''; if(row.some(x=>x!=='')) r.push(row); row=[]; }else cell+=ch; } row.push(cell); if(row.some(x=>x!=='')) r.push(row); return r; };\n"
        "    const norm = (x: unknown): string => String(x??'').toLowerCase().replace(/[^a-z0-9а-яё]/gi,'');\n"
        "    const toNum = (x: unknown): number => { const n=Number(String(x??'').trim().replace(/\\s/g,'').replace(',','.')); return isFinite(n)?n:0; };\n"
        "    const toBool = (x: unknown): boolean => ['1','true','yes','y','да'].includes(String(x??'').trim().toLowerCase());\n"
        "    const dflt = (ex: unknown): unknown => Array.isArray(ex)?[]:ex===null?null:typeof ex==='number'?0:typeof ex==='boolean'?false:typeof ex==='string'?'':ex&&typeof ex==='object'?Object.fromEntries(Object.entries(ex).map(([k,v])=>[k,dflt(v)])):'';\n"
        "    const cast = (v: unknown, ex: unknown): unknown => { if(Array.isArray(ex)){ const ie=ex[0]; return Array.isArray(v)?v.map(x=>cast(x,ie)):[]; } if(ex===null){ const t=String(v??'').trim(); return t?String(v):null; } if(typeof ex==='number') return toNum(v); if(typeof ex==='boolean') return toBool(v); if(typeof ex==='string') return String(v??''); if(ex&&typeof ex==='object'){ const src=v&&typeof v==='object'?v as Record<string,unknown>:{}; const o: Record<string,unknown>={}; for(const [k,sub] of Object.entries(ex)) o[k]=cast(src[k],sub); return o; } return v; };\n"
        "    const schema = " + schema_compact + ";\n"
        "    // === FILL aliases using sample keys below ===\n"
        f"    // Sample keys from extracted: {sample_keys}\n"
        f"    // Schema fields: {', '.join(schema_fields)}\n"
        "    const aliases: Record<string, string[]> = {\n"
        "        // Example: organizationName: [\"Наименование организации\", \"organizationName\"],\n"
        "        // ...\n"
        "    };\n"
        "    const pick = (row: Record<string,unknown>, key: string): unknown => { const cand=[key,...(aliases[key]??[])]; for(const c of cand){ const w=norm(c), short=w.length<=8; for(const [rk,rv] of Object.entries(row||{})){ const g=norm(rk); if(g===w) return rv; if(!short&&(g.includes(w)||w.includes(g))) return rv; } } return row[key]; };\n"
        "    const csv = decode(base64file);\n"
        "    const table = parseCSV(csv);\n"
        "    if(table.length===0) return [];\n"
        "    const headers = table[0].map(h=>String(h??'').trim());\n"
        "    const idx = new Map<string,number>();\n"
        "    headers.forEach((h,i)=>idx.set(norm(h),i));\n"
        "    const keys = Object.keys(schema);\n"
        "    const isInputArr = Array.isArray(schema.input);\n"
        "    const itemEx = isInputArr ? ((schema.input as unknown[])[0]??{}) : schema;\n"
        "    const res: DealData[] = [];\n"
        "    for(let r=1; r<table.length; r++){\n"
        "        const line = table[r];\n"
        "        const obj: Record<string,unknown> = {};\n"
        "        for(const k of Object.keys(itemEx)){\n"
        "            const names = [k, ...(aliases[k]??[])];\n"
        "            let col: number|undefined;\n"
        "            for(const nm of names){ const found=idx.get(norm(nm)); if(found!==undefined){ col=found; break; } }\n"
        "            const raw = col===undefined ? '' : String(line[col]??'');\n"
        "            obj[k] = cast(raw, (itemEx as any)[k]);\n"
        "        }\n"
        "        if(isInputArr) res.push({ input: [obj] } as DealData);\n"
        "        else res.push(obj as DealData);\n"
        "    }\n"
        "    return res;\n"
        "}\n"
    )


#PotJoke wuz here