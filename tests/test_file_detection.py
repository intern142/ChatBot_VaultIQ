import io
import zipfile

import pytest

from app.services import file_detection


class FakeOle:
    def __init__(self, streams):
        self.streams = streams

    def listdir(self, streams=True, storages=False):
        return [tuple(stream.split("/")) for stream in self.streams]

    def close(self):
        return None


@pytest.mark.parametrize(
    ("streams", "expected"),
    [
        (["WordDocument", "0Table"], "application/msword"),
        (["Workbook"], "application/vnd.ms-excel"),
        (["PowerPoint Document"], "application/vnd.ms-powerpoint"),
        (
            ["__properties_version1.0", "__substg1.0_0037001F"],
            "application/vnd.ms-outlook",
        ),
    ],
)
def test_detects_real_ole_stream_layouts(monkeypatch, streams, expected):
    monkeypatch.setattr(
        file_detection.olefile,
        "OleFileIO",
        lambda _: FakeOle(streams),
    )
    stream = io.BytesIO(file_detection.OLE_HEADER + b"fixture")
    assert file_detection.detect_document_mime(stream, "application/x-ole-storage") == expected
    assert stream.tell() == 0


def test_rejects_unknown_ole_document():
    stream = io.BytesIO(file_detection.OLE_HEADER + b"fixture")
    assert file_detection.detect_document_mime(stream, "application/x-ole-storage") == "application/x-ole-storage"


def test_detects_rtf_content():
    stream = io.BytesIO(br"{\rtf1\ansi Hello}")
    assert file_detection.detect_document_mime(stream, "text/plain") == "application/rtf"


def test_normalizes_librdf_result():
    stream = io.BytesIO(b"RTF content without the expected header")
    assert file_detection.detect_document_mime(stream, "text/rtf") == "application/rtf"


@pytest.mark.parametrize(
    ("entry", "content", "expected"),
    [
        (
            "word/document.xml",
            b"<w:document/>",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            "mimetype",
            b"application/vnd.oasis.opendocument.text",
            "application/vnd.oasis.opendocument.text",
        ),
    ],
)
def test_detects_zip_container_content(entry, content, expected):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(entry, content)
    buffer.seek(0)
    assert file_detection.detect_document_mime(buffer, "application/zip") == expected


def test_rejects_plain_zip_container():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("payload.txt", b"not an office document")
    buffer.seek(0)
    assert file_detection.detect_document_mime(buffer, "application/zip") == "application/zip"
