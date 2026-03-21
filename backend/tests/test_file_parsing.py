import asyncio
import importlib.util
import io
import unittest
from unittest import mock

from starlette.datastructures import UploadFile

import app.services.image_transcription as image_transcription
from app.services.file_parser import (
    ParseFileError,
    _records_from_doc_tables,
    detect_file_kind,
    extract_extracted_input,
)
from app.services.schema_inferer import infer_schema_from_extracted


class FileParsingTests(unittest.TestCase):
    def test_detect_txt_md_and_uppercase(self) -> None:
        self.assertEqual(detect_file_kind("notes.TXT", "application/octet-stream"), "txt")
        self.assertEqual(detect_file_kind("README.MD", ""), "md")
        self.assertEqual(detect_file_kind("a.bin", "text/markdown"), "md")
        self.assertEqual(detect_file_kind("book.fb2", "application/octet-stream"), "fb2")
        self.assertEqual(detect_file_kind("scan.tiff", "image/tiff"), "tiff")

    def test_infer_schema_supports_text_kinds(self) -> None:
        schema = infer_schema_from_extracted("txt", {"text": "hello"})
        self.assertEqual(schema, {"text": "string", "value": "string"})

    def test_infer_schema_skips_noisy_single_long_key_record(self) -> None:
        extracted = {
            "kind": "docx",
            "records": [
                {"СВЕДЕНИЯ О ВЫГОДОПРИОБРЕТАТЕЛЕ - ЮРИДИЧЕСКОМ ЛИЦЕ И ИНОСТРАННОЙ СТРУКТУРЕ": "ООО Ромашка"},
                {"Наименование организации": "ООО Ромашка", "ИНН/КИО": "1234567890"},
            ],
            "text": "",
            "tables": [],
        }
        schema = infer_schema_from_extracted("docx", extracted)
        self.assertIn("Наименование организации", schema)
        self.assertIn("ИНН/КИО", schema)

    def test_extract_txt_decodes_and_truncates(self) -> None:
        payload = "Привет\r\nмир".encode("utf-8")
        upload = UploadFile(filename="hello.txt", file=io.BytesIO(payload), headers={"content-type": "text/plain"})
        kind, parsed = asyncio.run(extract_extracted_input(upload, max_text_chars=8))
        self.assertEqual(kind, "txt")
        self.assertEqual(parsed["kind"], "txt")
        self.assertNotIn("\r", parsed["text"])
        self.assertTrue(parsed["text"].endswith("…"))
        self.assertIn("metadata", parsed)

    def test_extract_md_as_text(self) -> None:
        payload = b"# Title\r\n- item"
        upload = UploadFile(filename="doc.md", file=io.BytesIO(payload), headers={"content-type": "text/markdown"})
        kind, parsed = asyncio.run(extract_extracted_input(upload))
        self.assertEqual(kind, "md")
        self.assertIn("# Title", parsed["text"])
        self.assertIn("records", parsed)

    def test_extract_xml_as_text(self) -> None:
        payload = b"<root><title>Hello</title><p>World</p></root>"
        upload = UploadFile(filename="a.xml", file=io.BytesIO(payload), headers={"content-type": "application/xml"})
        kind, parsed = asyncio.run(extract_extracted_input(upload))
        self.assertEqual(kind, "xml")
        self.assertIn("Hello", parsed["text"])
        self.assertIn("World", parsed["text"])

    @unittest.skipUnless(importlib.util.find_spec("PyPDF2") is not None, "PyPDF2 not installed")
    def test_pdf_key_value_text_builds_records(self) -> None:
        payload = b"Organization Name: ACME LLC\nTIN: 123456789\n"
        upload = UploadFile(filename="f.pdf", file=io.BytesIO(payload), headers={"content-type": "application/pdf"})
        fake_page = mock.Mock()
        fake_page.extract_text.return_value = "Organization Name: ACME LLC\nTIN: 123456789\n"
        fake_reader = mock.Mock()
        fake_reader.pages = [fake_page]
        with mock.patch("PyPDF2.PdfReader", return_value=fake_reader):
            kind, parsed = asyncio.run(extract_extracted_input(upload))
        self.assertEqual(kind, "pdf")
        self.assertTrue(parsed["records"])
        self.assertEqual(parsed["records"][0]["Organization Name"], "ACME LLC")

    def test_extract_csv_has_unified_contract(self) -> None:
        payload = "a;b\n1;2\n".encode("utf-8")
        upload = UploadFile(filename="a.csv", file=io.BytesIO(payload), headers={"content-type": "text/csv"})
        kind, parsed = asyncio.run(extract_extracted_input(upload))
        self.assertEqual(kind, "csv")
        self.assertEqual(parsed["kind"], "csv")
        self.assertIn("records", parsed)
        self.assertEqual(parsed["records"][0]["a"], "1")
        self.assertEqual(parsed["records"][0]["b"], "2")

    def test_doc_tables_build_kv_with_continuation_rows(self) -> None:
        tables = [
            {
                "rows": [],
                "raw": [
                    ["Наименование организации", "ООО Ромашка"],
                    ["ИНН/КИО", "1234567890"],
                    ["Вопрос FATCA", "X Иностранный финансовый институт"],
                    ["", "Более 10% акций принадлежат налогоплательщикам США"],
                ],
            }
        ]
        records = _records_from_doc_tables(tables, max_rows=None)
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["Наименование организации"], "ООО Ромашка")
        self.assertEqual(rec["ИНН/КИО"], "1234567890")
        self.assertIn("Иностранный финансовый институт", rec["Вопрос FATCA"])
        self.assertIn("Более 10% акций", rec["Вопрос FATCA"])

    def test_doc_tables_skip_single_header_noise_rows(self) -> None:
        tables = [
            {
                "rows": [
                    {"Длинный заголовок формы": "ООО Ромашка"},
                    {"Длинный заголовок формы": "1234567890"},
                ],
                "raw": [],
            }
        ]
        records = _records_from_doc_tables(tables, max_rows=None)
        self.assertEqual(records, [])

    def test_extract_rtf_as_text(self) -> None:
        payload = br"{\rtf1\ansi This is \b test\b0 text.}"
        upload = UploadFile(filename="a.rtf", file=io.BytesIO(payload), headers={"content-type": "application/rtf"})
        kind, parsed = asyncio.run(extract_extracted_input(upload))
        self.assertEqual(kind, "rtf")
        self.assertIn("test", parsed["text"].lower())

    def test_unsupported_file_type_has_stable_code(self) -> None:
        upload = UploadFile(filename="bad.exe", file=io.BytesIO(b"abc"), headers={"content-type": "application/octet-stream"})
        with self.assertRaises(ParseFileError) as ctx:
            asyncio.run(extract_extracted_input(upload))
        self.assertEqual(ctx.exception.code, "UNSUPPORTED_FILE_TYPE")

    def test_ocr_empty_result_raises_controlled_error(self) -> None:
        upload = UploadFile(filename="img.png", file=io.BytesIO(b"x"), headers={"content-type": "image/png"})
        with mock.patch.object(image_transcription, "transcribe_image_with_ocr", return_value=""):
            with self.assertRaises(ParseFileError) as ctx:
                asyncio.run(extract_extracted_input(upload))
        self.assertEqual(ctx.exception.code, "OCR_NO_TEXT")

    def test_ocr_failure_raises_controlled_error(self) -> None:
        upload = UploadFile(filename="img.png", file=io.BytesIO(b"x"), headers={"content-type": "image/png"})
        with mock.patch.object(image_transcription, "transcribe_image_with_ocr", side_effect=RuntimeError("boom")):
            with self.assertRaises(ParseFileError) as ctx:
                asyncio.run(extract_extracted_input(upload))
        self.assertEqual(ctx.exception.code, "OCR_FAILED")

    def test_ocr_image_builds_records_from_question_options(self) -> None:
        payload = (
            "1. Какименно считать dealStageFinal в генерации?\n"
            "A Считать true для стадий Закрыта и Отклонена\n"
            "B Задать свой список финальных стадий\n"
        )
        upload = UploadFile(filename="img.png", file=io.BytesIO(b"x"), headers={"content-type": "image/png"})
        with mock.patch.object(image_transcription, "transcribe_image_with_ocr", return_value=payload):
            kind, parsed = asyncio.run(extract_extracted_input(upload))
        self.assertEqual(kind, "png")
        self.assertIn("records", parsed)
        self.assertTrue(parsed["records"])
        self.assertIn("question", parsed["records"][0])


if __name__ == "__main__":
    unittest.main()
