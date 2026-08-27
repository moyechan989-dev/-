from tests.test_pdf_text_extractor import blank_pdf_bytes, text_pdf_bytes

from src.pdf_batch_processor import process_pdf_files, processing_counts


def test_processes_one_pdf_in_memory():
    results = process_pdf_files([("A업체_출장결과.pdf", text_pdf_bytes("normal text"))])

    assert len(results) == 1
    assert results[0].status == "텍스트 추출 완료"
    assert "normal text" in results[0].text


def test_preserves_upload_order_for_multiple_pdfs():
    results = process_pdf_files([
        ("A.pdf", text_pdf_bytes("first")),
        ("B.pdf", blank_pdf_bytes()),
        ("C.pdf", text_pdf_bytes("third")),
    ])

    assert [item.filename for item in results] == ["A.pdf", "B.pdf", "C.pdf"]
    assert [item.status for item in results] == ["텍스트 추출 완료", "텍스트 없음", "텍스트 추출 완료"]
    assert processing_counts(results) == {
        "선택한 PDF": 3,
        "텍스트 추출 성공": 2,
        "텍스트 없음": 1,
        "오류": 0,
    }


def test_file_error_does_not_stop_other_files():
    results = process_pdf_files([
        ("정상.pdf", text_pdf_bytes("normal")),
        ("손상.pdf", b"not a pdf"),
        ("다음.pdf", text_pdf_bytes("continues")),
    ])

    assert [item.status for item in results] == ["텍스트 추출 완료", "파일 오류", "텍스트 추출 완료"]
    assert "continues" in results[2].text
    assert processing_counts(results)["오류"] == 1


def test_preview_is_limited_and_full_text_remains_available():
    source_text = "A" * 2001
    result = process_pdf_files([("긴문서.pdf", text_pdf_bytes(source_text))])[0]

    assert len(result.preview_text) == 2000
    assert result.has_more_text is True
    assert result.text == source_text
