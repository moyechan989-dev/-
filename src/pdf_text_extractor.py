from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfValidationError(ValueError):
    """사용자에게 보여줄 PDF 검증 오류입니다."""


@dataclass(frozen=True)
class PdfTextResult:
    filename: str
    size_bytes: int
    page_count: int
    text: str


def extract_pdf_text(filename: str, content: bytes) -> PdfTextResult:
    if Path(filename).suffix.lower() != ".pdf":
        raise PdfValidationError("PDF 파일만 업로드할 수 있습니다.")
    if not content:
        raise PdfValidationError("비어 있는 파일은 업로드할 수 없습니다.")
    try:
        reader = PdfReader(BytesIO(content))
        pages = list(reader.pages)
        text = "\n\n".join((page.extract_text() or "").strip() for page in pages).strip()
    except (PdfReadError, ValueError, OSError) as error:
        raise PdfValidationError("유효한 PDF 파일이 아닙니다.") from error
    return PdfTextResult(filename=filename, size_bytes=len(content), page_count=len(pages), text=text)
