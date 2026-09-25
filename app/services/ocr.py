import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings


settings = get_settings()

IMAGE_MIME_TYPES = {"image/tiff", "image/png", "image/jpeg"}
PDF_MIME_TYPE = "application/pdf"
EXTRACTABLE_MIME_TYPES = IMAGE_MIME_TYPES | {PDF_MIME_TYPE}

_OCR_SLOTS = threading.BoundedSemaphore(settings.OCR_MAX_CONCURRENT_DOCUMENTS)


class OcrUnavailableError(RuntimeError):
    pass


class DocumentExtractionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExtractionResult:
    text: str | None
    method: str | None
    status: str | None
    page_count: int | None
    truncated: bool


def extract_document_text(path: Path, mime_type: str) -> ExtractionResult:
    if mime_type not in EXTRACTABLE_MIME_TYPES:
        return ExtractionResult(None, "none", "not_required", None, False)
    if not settings.OCR_REQUIRED:
        return ExtractionResult(None, None, "unavailable", None, False)
    with _OCR_SLOTS:
        if mime_type == PDF_MIME_TYPE:
            return _extract_pdf(path)
        page_count = 1 if mime_type != "image/tiff" else None
        text = _run_tesseract(path)
        return _result(text, "ocr", page_count, False)


def _extract_pdf(path: Path) -> ExtractionResult:
    pdfinfo = _require_command("pdfinfo")
    pdftotext = _require_command("pdftotext")
    pdftoppm = _require_command("pdftoppm")
    page_count = _pdf_page_count(pdfinfo, path)
    native_text = _run_command(
        [pdftotext, "-layout", "-enc", "UTF-8", str(path), "-"],
        "PDF text extraction failed",
    ).stdout
    if _text_character_count(native_text) >= 20:
        return _result(native_text, "pdf_text", page_count, False)

    page_limit = min(page_count, settings.OCR_MAX_PAGES)
    with tempfile.TemporaryDirectory(prefix=".ocr-", dir=path.parent.parent) as temp_dir:
        prefix = Path(temp_dir) / "page"
        _run_command(
            [
                pdftoppm,
                "-png",
                "-r",
                str(settings.OCR_RENDER_DPI),
                "-f",
                "1",
                "-l",
                str(page_limit),
                str(path),
                str(prefix),
            ],
            "PDF rendering failed",
        )
        pages = sorted(Path(temp_dir).glob("page-*.png"), key=_page_sort_key)
        if not pages:
            raise DocumentExtractionError("PDF rendering produced no pages")
        text = "\n\n".join(filter(None, (_run_tesseract(page) for page in pages)))
        return _result(text, "ocr", page_count, page_count > page_limit)


def _run_tesseract(path: Path) -> str:
    tesseract = _require_command("tesseract")
    return _run_command(
        [tesseract, str(path), "stdout", "-l", "eng", "--psm", "3", "--oem", "1"],
        "OCR failed",
    ).stdout


def _require_command(command: str) -> str:
    executable = shutil.which(command)
    if executable is None:
        raise OcrUnavailableError(f"Required offline extraction command is unavailable: {command}")
    return executable


def _run_command(arguments: list[str], failure_message: str) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            arguments,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings.OCR_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise DocumentExtractionError(f"{failure_message}: timed out") from exc
    if result.returncode != 0:
        raise DocumentExtractionError(failure_message)
    return result


def _pdf_page_count(pdfinfo: str, path: Path) -> int:
    output = _run_command([pdfinfo, str(path)], "PDF metadata extraction failed").stdout
    match = re.search(r"^Pages:\s+(\d+)\s*$", output, re.MULTILINE)
    if match is None:
        raise DocumentExtractionError("PDF page count unavailable")
    return int(match.group(1))


def _result(text: str, method: str, page_count: int | None, truncated: bool) -> ExtractionResult:
    normalized = text.strip()
    output_truncated = len(normalized) > settings.OCR_MAX_TEXT_CHARS
    if output_truncated:
        normalized = normalized[: settings.OCR_MAX_TEXT_CHARS]
    return ExtractionResult(
        normalized or None,
        method,
        "completed" if normalized else "no_text",
        page_count,
        truncated or output_truncated,
    )


def _text_character_count(text: str) -> int:
    return sum(character.isalnum() for character in text)


def _page_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"-(\d+)\.png$", path.name)
    return (int(match.group(1)) if match else 0, path.name)
