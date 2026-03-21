import asyncio
import importlib.util
import io
import unittest
from types import SimpleNamespace
from unittest import mock

from starlette.datastructures import UploadFile

from app.services.file_parser import ParseFileError, extract_extracted_input
from app.services.llm_client import LLMClient
from app.services.prompt_builder import build_generation_prompt, build_interface_ts


class PromptAndGuardTests(unittest.TestCase):
    def test_universal_prompt_has_strict_schema_rules(self) -> None:
        schema = {"input": [{"organizationName": "string", "innOrKio": "string"}]}
        prompt = build_generation_prompt(
            {"kind": "pdf", "text": "organizationName: ООО Рога\ninnOrKio: 1234567890", "tables": [], "records": []},
            schema,
            interface_ts=build_interface_ts(schema),
            file_kind="pdf",
        )
        self.assertIn("single universal strategy", prompt)
        self.assertIn("Preserve top-level schema shape exactly", prompt)
        self.assertIn("schema contains input[] -> output item MUST include input array", prompt)
        self.assertIn("Extracted input payload", prompt)
        self.assertIn("STRICT KEYS MODE", prompt)
        self.assertIn("short keys/aliases (<= 8 chars", prompt)

    def test_universal_prompt_for_csv_uses_extracted_payload(self) -> None:
        schema = {"dealName": "string"}
        prompt = build_generation_prompt(
            {"kind": "csv", "records": [{"dealName": "A"}], "text": "", "tables": [], "metadata": {"kind": "csv"}},
            schema,
            interface_ts=build_interface_ts(schema),
            file_kind="csv",
        )
        self.assertIn("Extracted input payload", prompt)
        self.assertIn("\"records\":[{\"dealName\":\"A\"}]", prompt)

    def test_llm_guard_rejects_csv_template_for_document_kind(self) -> None:
        code = (
            "interface DealData { \"input\": any[]; }\n"
            "export default function (base64file: string): DealData[] {\n"
            "  const csv = decodeBase64(base64file);\n"
            "  const rows = parseCsv(csv);\n"
            "  return [];\n"
            "}\n"
        )
        self.assertTrue(LLMClient()._is_bad_generated_code(code, file_kind="pdf"))

    def test_llm_guard_rejects_nested_schema_flattening(self) -> None:
        code = (
            "export default function (base64file: string): DealData[] {\n"
            "  const cast = (value: string, example: unknown): unknown => {\n"
            "    return String(value ?? \"\");\n"
            "  };\n"
            "  return [];\n"
            "}\n"
        )
        schema = {"input": [{"organizationName": "x"}]}
        self.assertTrue(LLMClient()._is_bad_generated_code(code, file_kind="docx", schema_obj=schema))

    def test_llm_guard_allows_result_array_pattern_for_documents(self) -> None:
        code = (
            "export default function (base64file: string): DealData[] {\n"
            "  const result: DealData[] = [{ input: [] } as DealData];\n"
            "  return result;\n"
            "}\n"
        )
        self.assertFalse(LLMClient()._is_bad_generated_code(code, file_kind="pdf", schema_obj={"input": []}))

    def test_llm_guard_rejects_value_empty_for_input_wrapper_schema(self) -> None:
        code = (
            "export default function (base64file: string): DealData[] {\n"
            "  const out = {\"value\":\"\"};\n"
            "  return [out as DealData];\n"
            "}\n"
        )
        self.assertTrue(LLMClient()._is_bad_generated_code(code, file_kind="docx", schema_obj={"input": []}))

    def test_llm_guard_rejects_hardcoded_crm_keys_outside_schema(self) -> None:
        schema = {"dealName": "x", "dealSource": "x"}
        code = (
            "export default function (base64file: string): DealData[] {\n"
            "  const out = { \"dealName\": \"A\", \"dealSource\": \"B\", \"dealStage\": \"Закрыта\" };\n"
            "  return [out as DealData];\n"
            "}\n"
        )
        self.assertTrue(LLMClient()._is_bad_generated_code(code, file_kind="docx", schema_obj=schema))

class ParserRegressionTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("PyPDF2") is not None, "PyPDF2 not installed")
    def test_pdf_empty_text_raises_controlled_error(self) -> None:
        upload = UploadFile(filename="f.pdf", file=io.BytesIO(b"dummy"), headers={"content-type": "application/pdf"})
        fake_page = SimpleNamespace(extract_text=lambda: "")
        fake_reader = SimpleNamespace(pages=[fake_page])
        with mock.patch("PyPDF2.PdfReader", return_value=fake_reader):
            with self.assertRaises(ParseFileError) as ctx:
                asyncio.run(extract_extracted_input(upload))
        self.assertEqual(ctx.exception.code, "TEXT_DECODE_FAILED")

    @unittest.skipUnless(importlib.util.find_spec("docx") is not None, "python-docx not installed")
    def test_docx_tables_are_normalized(self) -> None:
        upload = UploadFile(
            filename="fatca.docx",
            file=io.BytesIO(b"dummy"),
            headers={"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        )
        fake_doc = SimpleNamespace(
            paragraphs=[SimpleNamespace(text="FATCA FORM")],
            tables=[
                SimpleNamespace(
                    rows=[
                        SimpleNamespace(cells=[SimpleNamespace(text="organizationName"), SimpleNamespace(text="innOrKio")]),
                        SimpleNamespace(cells=[SimpleNamespace(text='ООО "Рога и копыта"'), SimpleNamespace(text="1234567890")]),
                    ]
                )
            ],
        )
        with mock.patch("docx.Document", return_value=fake_doc):
            kind, parsed = asyncio.run(extract_extracted_input(upload))
        self.assertEqual(kind, "docx")
        self.assertTrue(parsed["tables"])
        self.assertIn("headers", parsed["tables"][0])
        self.assertIn("rows", parsed["tables"][0])
        self.assertEqual(parsed["tables"][0]["rows"][0]["organizationName"], 'ООО "Рога и копыта"')
        self.assertEqual(parsed["kind"], "docx")
        self.assertIn("metadata", parsed)
        self.assertTrue(parsed["records"])


if __name__ == "__main__":
    unittest.main()
