"""
Spreadsheet (csv/xls/xlsx) output shape: ensure a sink object for columns that are not in the user schema example.
"""

from __future__ import annotations

from typing import Any

UNMAPPED_COLUMNS_KEY = "unmappedColumns"


def _merge_unmapped_into_row_shape(obj: dict[str, Any]) -> dict[str, Any]:
    out = dict(obj)
    inp = out.get("input")
    if isinstance(inp, list) and inp and isinstance(inp[0], dict):
        new_inp = list(inp)
        item0 = dict(inp[0])
        if UNMAPPED_COLUMNS_KEY not in item0:
            item0[UNMAPPED_COLUMNS_KEY] = {}
        new_inp[0] = item0
        out["input"] = new_inp
        return out
    if UNMAPPED_COLUMNS_KEY not in out:
        out[UNMAPPED_COLUMNS_KEY] = {}
    return out


def apply_spreadsheet_unmapped_columns_sink(schema_obj: Any) -> Any:
    """
    Mutate a copy of the user schema so each output row includes `unmappedColumns: {}`
    (flat DealData or first element of `input` when schema uses input[]).
    """
    if isinstance(schema_obj, list):
        if not schema_obj or not isinstance(schema_obj[0], dict):
            return schema_obj
        return [_merge_unmapped_into_row_shape(dict(schema_obj[0])), *schema_obj[1:]]
    if isinstance(schema_obj, dict):
        return _merge_unmapped_into_row_shape(dict(schema_obj))
    return schema_obj
