from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.pdf_text_extractor import PdfTextResult, PdfValidationError, extract_pdf_text


@dataclass(frozen=True)
class PdfProcessingResult:
    filename: str
    status: str
    result: PdfTextResult | None = None
    error_message: str = ""

    @property
    def text(self) -> str:
        return self.result.text if self.result else ""

    @property
    def preview_text(self) -> str:
        return self.text[:2000]

    @property
    def has_more_text(self) -> bool:
        return len(self.text) > 2000


def process_pdf_files(files: Iterable[tuple[str, bytes]]) -> list[PdfProcessingResult]:
    """PDF를 저장하지 않고, 업로드된 순서대로 각각 처리합니다."""
    processed: list[PdfProcessingResult] = []
    for filename, content in files:
        try:
            result = extract_pdf_text(filename, content)
        except PdfValidationError as error:
            processed.append(PdfProcessingResult(filename=filename, status="파일 오류", error_message=str(error)))
        except Exception:
            processed.append(
                PdfProcessingResult(
                    filename=filename,
                    status="파일 오류",
                    error_message="파일 처리 중 오류가 발생했습니다.",
                )
            )
        else:
            status = "텍스트 추출 완료" if result.text else "텍스트 없음"
            processed.append(PdfProcessingResult(filename=filename, status=status, result=result))
    return processed


def processing_counts(results: Iterable[PdfProcessingResult]) -> dict[str, int]:
    counts = {"선택한 PDF": 0, "텍스트 추출 성공": 0, "텍스트 없음": 0, "오류": 0}
    for item in results:
        counts["선택한 PDF"] += 1
        if item.status == "텍스트 추출 완료":
            counts["텍스트 추출 성공"] += 1
        elif item.status == "텍스트 없음":
            counts["텍스트 없음"] += 1
        else:
            counts["오류"] += 1
    return counts
