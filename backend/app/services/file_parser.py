import io
import os
import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from fastapi import UploadFile

SUPPORTED_FILE_KINDS: tuple[str, ...] = (
    "csv",
    "xls",
    "xlsx",
    "pdf",
    "docx",
    "png",
    "jpg",
    "tiff",
    "txt",
    "md",
    "rtf",
    "odt",
    "xml",
    "epub",
    "fb2",
    "doc",
)


class ParseFileError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_detail(self) -> Dict[str, str]:
        return {"code": self.code, "message": self.message}


def detect_file_kind(filename: Optional[str], content_type: Optional[str]) -> str:
    name = (filename or "").lower()
    ctype = (content_type or "").lower()

    # Prefer extension.
    if name.endswith(".csv") or "text/csv" in ctype:
        return "csv"
    if name.endswith(".xls") or "application/vnd.ms-excel" in ctype:
        return "xls"
    if name.endswith(".xlsx") or "excel" in ctype and "spreadsheetml" in ctype:
        return "xlsx"
    if name.endswith(".pdf") or "application/pdf" in ctype:
        return "pdf"
    if name.endswith(".docx") or "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in ctype:
        return "docx"
    if name.endswith(".png") or "image/png" in ctype:
        return "png"
    if name.endswith(".jpg") or name.endswith(".jpeg") or "image/jpeg" in ctype:
        return "jpg"
    if name.endswith(".tif") or name.endswith(".tiff") or "image/tiff" in ctype:
        return "tiff"
    if name.endswith(".txt") or "text/plain" in ctype:
        return "txt"
    if name.endswith(".md") or "text/markdown" in ctype or "text/x-markdown" in ctype:
        return "md"
    if name.endswith(".rtf") or "application/rtf" in ctype or "text/rtf" in ctype:
        return "rtf"
    if name.endswith(".odt") or "application/vnd.oasis.opendocument.text" in ctype:
        return "odt"
    if name.endswith(".xml") or "application/xml" in ctype or "text/xml" in ctype:
        return "xml"
    if name.endswith(".epub") or "application/epub+zip" in ctype:
        return "epub"
    if name.endswith(".fb2") or "application/x-fictionbook+xml" in ctype:
        return "fb2"
    if name.endswith(".doc") or "application/msword" in ctype:
        return "doc"

    return "unknown"


def _limit_records(records: List[Dict[str, Any]], max_rows: int) -> List[Dict[str, Any]]:
    if len(records) <= max_rows:
        return records
    return records[:max_rows]


def _to_records_dataframe(df: pd.DataFrame, max_rows: Optional[int]) -> List[Dict[str, Any]]:
    if max_rows is not None:
        df = df.head(max_rows)
    df = df.fillna("")
    records = df.to_dict(orient="records")
    # Ensure all values are strings for compact prompt.
    for r in records:
        for k, v in list(r.items()):
            if v is None:
                r[k] = ""
            elif isinstance(v, (int, float, bool)):
                r[k] = str(v)
            else:
                r[k] = str(v)
    return records


def _detect_csv_delimiter(text_sample: str) -> str:
    """
    Detect delimiter from sample text, fallback to semicolon for CRM-style exports.
    """
    sample = (text_sample or "").strip()
    if not sample:
        return ";"
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        if getattr(dialect, "delimiter", None):
            return dialect.delimiter
    except Exception:
        pass
    return ";" if sample.count(";") >= sample.count(",") else ","


def _read_csv_dataframe(contents: bytes, *, max_rows: Optional[int]) -> pd.DataFrame:
    """
    Read CSV with delimiter/encoding tolerance.
    """
    # Try UTF encodings first (common for modern exports), then cp1251 fallback.
    decoded_text = ""
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            decoded_text = contents.decode(enc)
            break
        except Exception:
            continue

    if not decoded_text:
        decoded_text = contents.decode("utf-8", errors="replace")

    delimiter = _detect_csv_delimiter(decoded_text[:8000])
    return pd.read_csv(
        io.StringIO(decoded_text),
        sep=delimiter,
        nrows=max_rows,
        dtype=str,
        keep_default_na=False,
        engine="python",
    )


def _decode_text_contents(contents: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return contents.decode(enc)
        except Exception:
            continue
    return contents.decode("utf-8", errors="replace")


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _truncate_text(text: str, max_text_chars: Optional[int]) -> str:
    if max_text_chars is not None and max_text_chars > 0 and len(text) > max_text_chars:
        return text[: max_text_chars - 1] + "…"
    return text


def _join_non_empty_lines(lines: List[str]) -> str:
    return "\n".join([ln.strip() for ln in lines if ln and ln.strip()])


def _extract_rtf_text(contents: bytes) -> str:
    from striprtf.striprtf import rtf_to_text

    raw = _decode_text_contents(contents)
    return rtf_to_text(raw) or ""


def _extract_odt_text(contents: bytes) -> str:
    from odf import text as odf_text
    from odf.opendocument import load
    from odf.teletype import extractText

    doc = load(io.BytesIO(contents))
    lines: List[str] = []
    for elem in doc.getElementsByType(odf_text.P):
        val = extractText(elem)
        if val:
            lines.append(val)
    for elem in doc.getElementsByType(odf_text.H):
        val = extractText(elem)
        if val:
            lines.append(val)
    return _join_non_empty_lines(lines)


def _extract_xml_text(contents: bytes) -> str:
    xml_text = _decode_text_contents(contents)
    root = ET.fromstring(xml_text)
    pieces = [t.strip() for t in root.itertext() if t and t.strip()]
    return _join_non_empty_lines(pieces)


def _extract_epub_text(contents: bytes) -> str:
    from bs4 import BeautifulSoup
    from ebooklib import ITEM_DOCUMENT, epub

    with zipfile.ZipFile(io.BytesIO(contents), "r") as zf:
        with zf.open("META-INF/container.xml") as f:
            container_xml = f.read().decode("utf-8", errors="replace")
    container_root = ET.fromstring(container_xml)
    rootfile_path = ""
    for elem in container_root.iter():
        if elem.tag.lower().endswith("rootfile"):
            rootfile_path = (elem.attrib.get("full-path") or "").strip()
            break
    if not rootfile_path:
        raise ParseFileError(code="TEXT_DECODE_FAILED", message="EPUB container.xml has no rootfile path.")

    book = epub.read_epub(io.BytesIO(contents), options={"ignore_ncx": True})
    lines: List[str] = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        html = item.get_content().decode("utf-8", errors="replace")
        text = BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True)
        if text:
            lines.append(text)
    return _join_non_empty_lines(lines)


def _extract_doc_text(contents: bytes) -> str:
    # Legacy .doc is binary; use best-effort extraction without external system tools.
    utf16 = contents.decode("utf-16le", errors="ignore")
    cp = contents.decode("cp1251", errors="ignore")
    mix = f"{utf16}\n{cp}"
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9 .,;:!?()\"'/-]{2,}", mix)
    return _join_non_empty_lines(words[:2000])


def _normalize_broken_semicolon_rows(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    If parser produced one-column rows like {"a;b;c":"1;2;3"}, expand them.
    """
    if not records:
        return records

    normalized: List[Dict[str, Any]] = []
    for row in records:
        if not isinstance(row, dict) or len(row) != 1:
            normalized.append(row)
            continue

        only_key = next(iter(row.keys()), "")
        only_val = str(next(iter(row.values()), ""))
        if ";" not in str(only_key):
            normalized.append(row)
            continue

        headers = [h.strip() for h in str(only_key).split(";")]
        values = [v.strip() for v in only_val.split(";")]
        expanded: Dict[str, Any] = {}
        for i, h in enumerate(headers):
            if not h:
                continue
            expanded[h] = values[i] if i < len(values) else ""
        normalized.append(expanded if expanded else row)

    return normalized


async def extract_extracted_input(
    file: UploadFile,
    *,
    max_rows: Optional[int] = None,
    max_text_chars: Optional[int] = None,
) -> Tuple[str, Any]:
    """
    Returns:
      (file_kind, extractedInputJson)
    extractedInputJson:
      - csv/xls/xlsx: list[dict]
      - pdf/docx: { "text": string, "tables": ... }
      - image: { "text": string }
    """
    contents = await file.read()
    filename = file.filename
    file_kind = detect_file_kind(filename, file.content_type)

    if file_kind in {"csv", "xls", "xlsx"}:
        if file_kind == "csv":
            df = _read_csv_dataframe(contents, max_rows=max_rows)
        elif file_kind in {"xls", "xlsx"}:
            bytes_buf = io.BytesIO(contents)
            # sheet_name=0 for MVP
            df = pd.read_excel(bytes_buf, nrows=max_rows, dtype=str, sheet_name=0, engine=None)
        else:
            raise ValueError("Unsupported spreadsheet kind")

        records = _to_records_dataframe(df, max_rows=max_rows)
        records = _normalize_broken_semicolon_rows(records)
        return file_kind, records

    if file_kind in {"txt", "md"}:
        text = _normalize_newlines(_decode_text_contents(contents))
        text = _truncate_text(text, max_text_chars)
        return file_kind, {"text": text}

    if file_kind == "rtf":
        text = _normalize_newlines(_extract_rtf_text(contents))
        text = _truncate_text(text, max_text_chars)
        if not text.strip():
            raise ParseFileError(code="TEXT_DECODE_FAILED", message="Failed to extract text from RTF file.")
        return file_kind, {"text": text}

    if file_kind == "odt":
        text = _normalize_newlines(_extract_odt_text(contents))
        text = _truncate_text(text, max_text_chars)
        if not text.strip():
            raise ParseFileError(code="TEXT_DECODE_FAILED", message="Failed to extract text from ODT file.")
        return file_kind, {"text": text}

    if file_kind in {"xml", "fb2"}:
        text = _normalize_newlines(_extract_xml_text(contents))
        text = _truncate_text(text, max_text_chars)
        if not text.strip():
            raise ParseFileError(code="TEXT_DECODE_FAILED", message=f"Failed to extract text from {file_kind.upper()} file.")
        return file_kind, {"text": text}

    if file_kind == "epub":
        text = _normalize_newlines(_extract_epub_text(contents))
        text = _truncate_text(text, max_text_chars)
        if not text.strip():
            raise ParseFileError(code="TEXT_DECODE_FAILED", message="Failed to extract text from EPUB file.")
        return file_kind, {"text": text}

    if file_kind == "doc":
        text = _normalize_newlines(_extract_doc_text(contents))
        text = _truncate_text(text, max_text_chars)
        if not text.strip():
            raise ParseFileError(code="TEXT_DECODE_FAILED", message="Failed to extract text from DOC file.")
        return file_kind, {"text": text}

    if file_kind == "pdf":
        from PyPDF2 import PdfReader

        bytes_buf = io.BytesIO(contents)
        reader = PdfReader(bytes_buf)
        texts: List[str] = []
        pages = reader.pages if max_rows is None else reader.pages[: max(1, max_rows)]
        for page in pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                # Best-effort extraction
                texts.append("")
        text = _truncate_text(_normalize_newlines("\n".join(texts).strip()), max_text_chars)
        return file_kind, {"text": text}

    if file_kind == "docx":
        from docx import Document

        bytes_buf = io.BytesIO(contents)
        doc = Document(bytes_buf)
        paragraphs: List[str] = []
        for p in doc.paragraphs:
            if p.text:
                paragraphs.append(p.text)
        # Tables: best-effort, but compact.
        tables: List[List[List[str]]] = []
        tables_iter = doc.tables if max_rows is None else doc.tables[: max(1, max_rows)]
        for t in tables_iter:
            table_data: List[List[str]] = []
            for row in t.rows:
                row_data: List[str] = []
                for cell in row.cells:
                    row_data.append((cell.text or "").strip())
                table_data.append(row_data)
            tables.append(table_data)

        text = _truncate_text(_normalize_newlines("\n".join(paragraphs).strip()), max_text_chars)
        return file_kind, {"text": text, "tables": tables}

    if file_kind in {"png", "jpg", "tiff"}:
        from PIL import Image
        from PIL import ImageOps
        import pytesseract

        image = Image.open(io.BytesIO(contents))
        ocr_lang = (os.getenv("OCR_LANG") or "eng").strip() or "eng"
        ocr_psm = (os.getenv("OCR_PSM") or "6").strip() or "6"
        ocr_fallback_psm = (os.getenv("OCR_FALLBACK_PSM") or "11").strip() or "11"

        if image.mode not in {"L", "RGB"}:
            image = image.convert("RGB")

        enhanced = ImageOps.autocontrast(image.convert("L"))
        text = (pytesseract.image_to_string(enhanced, lang=ocr_lang, config=f"--psm {ocr_psm}") or "").strip()
        if len(text) < 6:
            second_pass = (
                pytesseract.image_to_string(enhanced, lang=ocr_lang, config=f"--psm {ocr_fallback_psm}") or ""
            ).strip()
            if len(second_pass) > len(text):
                text = second_pass

        if not text:
            raise ParseFileError(
                code="OCR_NO_TEXT",
                message="Image OCR failed to extract readable text. Try higher quality or clearer image.",
            )

        text = _truncate_text(_normalize_newlines(text), max_text_chars)
        return file_kind, {"text": text}

    raise ParseFileError(
        code="UNSUPPORTED_FILE_TYPE",
        message=f"Unsupported file type. Supported: {', '.join(SUPPORTED_FILE_KINDS)}",
    )

