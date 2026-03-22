"""Tests for schema alias building (nested input[], user meta, extraction hints)."""

from app.services.schema_aliases import (
    build_aliases_for_schema,
    collect_schema_field_keys,
    strip_schema_meta_for_output,
)


def test_nested_input_gets_fatca_builtin_aliases() -> None:
    schema = {
        "input": [
            {
                "organizationName": "",
                "innOrKio": "",
                "isResidentRF": "",
            }
        ]
    }
    aliases = build_aliases_for_schema(schema)
    assert "organizationName" in aliases
    assert "Наименование организации" in aliases["organizationName"]
    assert "innOrKio" in aliases
    assert "ИНН/КИО" in aliases["innOrKio"]


def test_collect_schema_field_keys_includes_nested_skips_meta_block() -> None:
    schema = {
        "input": [{"a": 1, "b": {"c": ""}}],
        "_headerAliases": {"a": ["x"], "ghost": ["y"]},
    }
    keys = collect_schema_field_keys(schema)
    assert "input" in keys
    assert "a" in keys
    assert "b" in keys
    assert "c" in keys
    assert "ghost" not in keys
    assert "_headerAliases" not in keys


def test_user_header_aliases_merge_before_builtin() -> None:
    schema = {
        "input": [{"organizationName": ""}],
        "_headerAliases": {"organizationName": ["Юр. лицо"]},
    }
    aliases = build_aliases_for_schema(schema)
    assert aliases["organizationName"][0] == "Юр. лицо"
    assert "Наименование организации" in aliases["organizationName"]


def test_strip_schema_meta_for_output() -> None:
    schema = {"input": [], "_headerAliases": {"x": ["y"]}}
    stripped = strip_schema_meta_for_output(schema)
    assert "_headerAliases" not in stripped
    assert "_headerAliases" in schema


def test_infer_exact_header_from_extracted() -> None:
    schema = {"input": [{"ПолеДокумента": ""}]}
    extracted = {"records": [{"ПолеДокумента": "значение"}]}
    aliases = build_aliases_for_schema(schema, extracted=extracted)
    assert aliases.get("ПолеДокумента") == ["ПолеДокумента"]
