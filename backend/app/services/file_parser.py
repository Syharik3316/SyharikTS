import io
import os
import csv
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from fastapi import UploadFile


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

    return "unknown"


def _limit_records(records: List[Dict[str, Any]], max_rows: int) -> List[Dict[str, Any]]:
    if len(records) <= max_rows:
        return records
    return records[:max_rows]


def _to_records_dataframe(df: pd.DataFrame, max_rows: int) -> List[Dict[str, Any]]:
    df = df.head(max_rows).fillna("")
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


def _read_csv_dataframe(contents: bytes, *, max_rows: int) -> pd.DataFrame:
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
    max_rows: int = 20,
    max_text_chars: int = 8000,
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

    if file_kind == "pdf":
        from PyPDF2 import PdfReader

        bytes_buf = io.BytesIO(contents)
        reader = PdfReader(bytes_buf)
        texts: List[str] = []
        for page in reader.pages[:8]:  # limit pages for MVP
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                # Best-effort extraction
                texts.append("")
        text = "\n".join(texts).strip()
        if len(text) > max_text_chars:
            text = text[: max_text_chars - 1] + "…"
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
        for t in doc.tables[:3]:  # limit number of tables for MVP
            table_data: List[List[str]] = []
            for row in t.rows:
                row_data: List[str] = []
                for cell in row.cells:
                    row_data.append((cell.text or "").strip())
                table_data.append(row_data)
            tables.append(table_data)

        text = "\n".join(paragraphs).strip()
        if len(text) > max_text_chars:
            text = text[: max_text_chars - 1] + "…"
        return file_kind, {"text": text, "tables": tables}

    if file_kind in {"png", "jpg"}:
        from PIL import Image
        import pytesseract

        image = Image.open(io.BytesIO(contents))
        # OCR may be slow; keep it simple for MVP.
        text = pytesseract.image_to_string(image) or ""
        text = text.strip()
        if len(text) > max_text_chars:
            text = text[: max_text_chars - 1] + "…"
        return file_kind, {"text": text}

    raise ValueError("Unsupported file type")

