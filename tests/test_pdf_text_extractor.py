from io import BytesIO

import pytest
from pypdf import PdfWriter

from src.pdf_text_extractor import PdfValidationError, extract_pdf_text


def text_pdf_bytes(text: str = "Hello PDF") -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 5 0 R >> >> /MediaBox [0 0 612 792] /Contents 4 0 R >>",
        f"<< /Length {len(f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode('ascii'))} >>\nstream\nBT /F1 12 Tf 72 720 Td ({text}) Tj ET\nendstream".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode("ascii"))
        content.extend(obj)
        content.extend(b"\nendobj\n")
    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    content.extend(b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:]))
    content.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("ascii"))
    return bytes(content)


def blank_pdf_bytes() -> bytes:
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(buffer)
    return buffer.getvalue()


def empty_pdf_bytes() -> bytes:
    buffer = BytesIO()
    PdfWriter().write(buffer)
    return buffer.getvalue()


def test_extracts_text_from_text_selectable_pdf():
    result = extract_pdf_text("출장결과보고서.pdf", text_pdf_bytes())
    assert result.filename == "출장결과보고서.pdf"
    assert result.page_count == 1
    assert result.size_bytes > 0
    assert "Hello PDF" in result.text


def test_textless_pdf_returns_empty_preview_text():
    result = extract_pdf_text("스캔문서.pdf", blank_pdf_bytes())
    assert result.page_count == 1
    assert result.text == ""


def test_empty_pdf_returns_zero_pages_and_empty_text():
    result = extract_pdf_text("빈문서.pdf", empty_pdf_bytes())
    assert result.page_count == 0
    assert result.text == ""


def test_rejects_invalid_or_non_pdf_files():
    with pytest.raises(PdfValidationError, match="PDF 파일만"):
        extract_pdf_text("문서.txt", b"not a pdf")
    with pytest.raises(PdfValidationError, match="유효한 PDF"):
        extract_pdf_text("손상.pdf", b"not a pdf")
