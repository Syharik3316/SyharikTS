"""
Built-in header aliases for generated TypeScript pick()/pickFromRow(), plus helpers
to attach aliases for nested schema keys (e.g. input[0].organizationName).

Optional schema meta key `_headerAliases`: { "fieldKey": ["Header 1", ...] } merged into
the alias map (user strings first, then built-in).
"""

from __future__ import annotations

import re
from typing import Any

from app.utils.helpers import ensure_json_object

HEADER_ALIASES_META_KEY = "_headerAliases"

CRM_HEADER_ALIASES: dict[str, list[str]] = {
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


def _norm_header(s: str) -> str:
    """Match TS norm(): lowercase, strip non-alphanumeric (keep Cyrillic letters)."""
    return re.sub(r"[^a-z0-9а-яё]+", "", str(s).lower(), flags=re.IGNORECASE)


def strip_schema_meta_for_output(schema: dict[str, Any]) -> dict[str, Any]:
    """Copy of schema without generation-only meta keys (for prompts / embedded TS)."""
    out = dict(schema)
    out.pop(HEADER_ALIASES_META_KEY, None)
    return out


def parse_user_header_aliases(schema: dict[str, Any]) -> dict[str, list[str]]:
    raw = schema.get(HEADER_ALIASES_META_KEY)
    if not isinstance(raw, dict):
        return {}
    result: dict[str, list[str]] = {}
    for k, v in raw.items():
        sk = str(k)
        if isinstance(v, str) and v.strip():
            result[sk] = [v.strip()]
        elif isinstance(v, list):
            lst = [str(x).strip() for x in v if x is not None and str(x).strip()]
            if lst:
                result[sk] = lst
        elif v is not None and str(v).strip():
            result[sk] = [str(v).strip()]
    return result


def collect_schema_field_keys(schema_obj: Any) -> set[str]:
    """
    All dict keys appearing anywhere in the schema example (objects + first element of arrays).
    Skips `_headerAliases` subtree (those keys are not output fields).
    """
    keys: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k == HEADER_ALIASES_META_KEY:
                    continue
                keys.add(str(k))
                walk(v)
        elif isinstance(node, list) and node:
            walk(node[0])

    walk(ensure_json_object(schema_obj))
    return keys


def _collect_header_candidates(extracted: Any) -> list[str]:
    """Unique header-like strings from records[0] keys and tables[].raw[*][0]."""
    seen: list[str] = []
    seen_set: set[str] = set()

    def add(s: str) -> None:
        t = str(s).strip()
        if len(t) < 2 or t in seen_set:
            return
        seen_set.add(t)
        seen.append(t)

    if not isinstance(extracted, dict):
        return seen
    recs = extracted.get("records")
    if isinstance(recs, list) and recs and isinstance(recs[0], dict):
        for rk in recs[0].keys():
            add(str(rk))
    tables = extracted.get("tables")
    if isinstance(tables, list):
        for tbl in tables:
            if not isinstance(tbl, dict):
                continue
            raw = tbl.get("raw")
            if isinstance(raw, list):
                for row in raw:
                    if isinstance(row, list) and row:
                        cell0 = row[0]
                        if isinstance(cell0, str):
                            add(cell0)
    return seen


def infer_header_aliases_from_extracted(
    schema: dict[str, Any],
    extracted: Any | None,
    existing: dict[str, list[str]],
) -> dict[str, list[str]]:
    """
    For schema fields still without aliases, link document headers that normalize equally
    or mutually contain (when both norms length > 8), mirroring generated TS pick() rules.
    Each normalized header is assigned to at most one field (first match wins).
    """
    if extracted is None:
        return {}
    field_keys = collect_schema_field_keys(schema)
    candidates = _collect_header_candidates(extracted)
    inferred: dict[str, list[str]] = {}
    used_norms: set[str] = set()

    for fk in sorted(field_keys):
        if existing.get(fk):
            continue
        nk = _norm_header(fk)
        if len(nk) < 2:
            continue
        for h in candidates:
            nh = _norm_header(h)
            if len(nh) < 2 or nh in used_norms:
                continue
            match = nh == nk
            if not match and len(nk) > 8 and len(nh) > 8 and (nh in nk or nk in nh):
                match = True
            if match:
                inferred[fk] = [h]
                used_norms.add(nh)
                break
    return inferred


def build_aliases_for_schema(
    schema: dict[str, Any],
    *,
    extracted: Any | None = None,
) -> dict[str, list[str]]:
    schema = ensure_json_object(schema)
    aliases: dict[str, list[str]] = {}
    for key in collect_schema_field_keys(schema):
        vals = CRM_HEADER_ALIASES.get(key, [])
        if vals:
            aliases[key] = list(vals)

    user = parse_user_header_aliases(schema)
    for k, lst in user.items():
        if not lst:
            continue
        if k in aliases:
            merged: list[str] = []
            for x in lst + aliases[k]:
                if x not in merged:
                    merged.append(x)
            aliases[k] = merged
        else:
            aliases[k] = list(lst)

    inferred = infer_header_aliases_from_extracted(schema, extracted, aliases)
    for k, lst in inferred.items():
        if not lst:
            continue
        cur = aliases.setdefault(k, [])
        for x in lst:
            if x not in cur:
                cur.append(x)
    return aliases
