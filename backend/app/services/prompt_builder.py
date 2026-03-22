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
    aliases_compact = json.dumps(_build_aliases_for_schema(schema), ensure_ascii=False, separators=(",", ":"))
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

    # Prompt with explicit function signature stub
    return (
        "Return ONLY TypeScript code. No markdown, no comments, no explanations.\n"
        "Generate a deterministic TypeScript parser that converts extracted data into the given schema.\n\n"
        f"// Target interface (must be included in output)\n{interface_ts}\n\n"
        "// Required function signature (must be exactly as shown)\n"
        "export default function (base64file: string): DealData[] {\n"
        "    const result: DealData[] = [];\n"
        "    // parsing logic here\n"
        "    // ...\n"
        "    return result;\n"
        "}\n\n"
        "// Data and configuration for the parser:\n"
        f"const schema = {schema_compact};\n"
        f"const aliases: Record<string, string[]> = {aliases_compact};\n"
        f"const extracted = {payload_compact};\n\n"
        "// Requirements for the parsing logic:\n"
        "1. Return [] if base64file is empty after trim.\n"
        "2. Data priority: extracted.records (array) > extracted.tables[].rows > extracted.text (regex fallback).\n"
        "3. Field mapping: use aliases for each target key. Normalize strings (lowercase, remove non-alphanumeric, keep Cyrillic).\n"
        "   - If normalized key/alias length <= 8, require exact normalized match.\n"
        "   - Otherwise allow substring (normalized source contains normalized target or vice versa).\n"
        "4. Checkbox values: strings containing [X,x,☑,☒,✓] → boolean true.\n"
        "5. Type casting: follow the type of the example in schema (string, number, boolean, null, object, array).\n"
        "   - Use safe conversion: Number() with comma decimal, boolean from truthy strings, etc.\n"
        "   - For arrays: use first element of schema array as example.\n"
        "   - For objects: recursively cast each property.\n"
        "6. Strict keys: output must have exactly the keys present in schema. For missing data, use defaults ('' for string, 0 for number, false for boolean, null for null, [] for array, {} for object).\n"
        "7. If Array.isArray(schema.input):\n"
        "   - Output a single object { input: [...] } where each element matches schema.input[0] shape.\n"
        "   - Populate from each data row (records or table rows).\n"
        "8. Else: output a single object (still wrapped in an array) using the first row of data (or text fallback).\n"
        "9. Do not use `as any`. Use proper TypeScript types.\n\n"
        "Write the complete TypeScript code including the interface and the function, with the function body implementing all requirements."
    )


#PotJoke wuz here