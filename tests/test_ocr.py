from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import ocr


def test_disabled_ocr_reports_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr.settings, "OCR_REQUIRED", False)
    result = ocr.extract_document_text(tmp_path / "scan.png", "image/png")
    assert result == ocr.ExtractionResult(None, None, "unavailable", None, False)


def test_image_ocr_is_completed(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr.settings, "OCR_REQUIRED", True)
    monkeypatch.setattr(ocr, "_require_command", lambda command: command)
    monkeypatch.setattr(
        ocr,
        "_run_command",
        lambda arguments, message: SimpleNamespace(stdout="Extracted text"),
    )
    result = ocr.extract_document_text(tmp_path / "scan.png", "image/png")
    assert result == ocr.ExtractionResult("Extracted text", "ocr", "completed", 1, False)


def test_native_pdf_text_avoids_ocr(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr.settings, "OCR_REQUIRED", True)
    monkeypatch.setattr(ocr, "_require_command", lambda command: command)
    monkeypatch.setattr(ocr, "_pdf_page_count", lambda command, path: 2)
    monkeypatch.setattr(
        ocr,
        "_run_command",
        lambda arguments, message: SimpleNamespace(stdout="Native PDF text with enough content"),
    )
    monkeypatch.setattr(
        ocr,
        "_run_tesseract",
        lambda path: pytest.fail("OCR must not run for native PDF text"),
    )
    result = ocr.extract_document_text(tmp_path / "document.pdf", "application/pdf")
    assert result.text == "Native PDF text with enough content"
    assert result.method == "pdf_text"
    assert result.page_count == 2


def test_scanned_pdf_renders_and_ocrs_pages(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr.settings, "OCR_REQUIRED", True)
    monkeypatch.setattr(ocr.settings, "OCR_MAX_PAGES", 1)
    monkeypatch.setattr(ocr, "_require_command", lambda command: command)
    monkeypatch.setattr(ocr, "_pdf_page_count", lambda command, path: 2)

    def run_command(arguments, message):
        if arguments[0] == "pdftotext":
            return SimpleNamespace(stdout="")
        Path(arguments[-1] + "-1.png").write_bytes(b"image")
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(ocr, "_run_command", run_command)
    monkeypatch.setattr(ocr, "_run_tesseract", lambda path: "scanned page")
    result = ocr.extract_document_text(tmp_path / "scan.pdf", "application/pdf")
    assert result.text == "scanned page"
    assert result.method == "ocr"
    assert result.page_count == 2
    assert result.truncated is True


def test_missing_required_runtime_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr.settings, "OCR_REQUIRED", True)
    monkeypatch.setattr(ocr, "_require_command", lambda command: (_ for _ in ()).throw(ocr.OcrUnavailableError()))
    with pytest.raises(ocr.OcrUnavailableError):
        ocr.extract_document_text(tmp_path / "scan.png", "image/png")
