import asyncio
import io
import unittest
from unittest import mock

from starlette.datastructures import UploadFile

from app.services.file_parser import ParseFileError, detect_file_kind, extract_extracted_input
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

    def test_extract_txt_decodes_and_truncates(self) -> None:
        payload = "Привет\r\nмир".encode("utf-8")
        upload = UploadFile(filename="hello.txt", file=io.BytesIO(payload), headers={"content-type": "text/plain"})
        kind, parsed = asyncio.run(extract_extracted_input(upload, max_text_chars=8))
        self.assertEqual(kind, "txt")
        self.assertNotIn("\r", parsed["text"])
        self.assertTrue(parsed["text"].endswith("…"))

    def test_extract_md_as_text(self) -> None:
        payload = b"# Title\r\n- item"
        upload = UploadFile(filename="doc.md", file=io.BytesIO(payload), headers={"content-type": "text/markdown"})
        kind, parsed = asyncio.run(extract_extracted_input(upload))
        self.assertEqual(kind, "md")
        self.assertIn("# Title", parsed["text"])

    def test_extract_xml_as_text(self) -> None:
        payload = b"<root><title>Hello</title><p>World</p></root>"
        upload = UploadFile(filename="a.xml", file=io.BytesIO(payload), headers={"content-type": "application/xml"})
        kind, parsed = asyncio.run(extract_extracted_input(upload))
        self.assertEqual(kind, "xml")
        self.assertIn("Hello", parsed["text"])
        self.assertIn("World", parsed["text"])

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
        with mock.patch("app.services.image_transcription.transcribe_image_with_gigachat", return_value=""):
            with self.assertRaises(ParseFileError) as ctx:
                asyncio.run(extract_extracted_input(upload))
        self.assertEqual(ctx.exception.code, "OCR_NO_TEXT")


if __name__ == "__main__":
    unittest.main()
