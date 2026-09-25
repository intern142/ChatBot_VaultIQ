import zipfile
from email import policy
from email.parser import BytesParser
from typing import BinaryIO

import olefile


OLE_HEADER = bytes.fromhex("d0cf11e0a1b11ae1")
ZIP_HEADER = b"PK\x03\x04"

OLE_MIME_TYPES = {
    "word": "application/msword",
    "excel": "application/vnd.ms-excel",
    "powerpoint": "application/vnd.ms-powerpoint",
    "message": "application/vnd.ms-outlook",
}

OOXML_MIME_TYPES = {
    "word/document.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xl/workbook.xml": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt/presentation.xml": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

ODF_MIME_TYPES = {
    "application/vnd.oasis.opendocument.text": "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet": "application/vnd.oasis.opendocument.spreadsheet",
}


def detect_document_mime(file: BinaryIO, detected_mime: str) -> str:
    file.seek(0)
    header = file.read(8)
    file.seek(0)

    if header.startswith(b"{\\rt"):
        return "application/rtf"
    if header.startswith(OLE_HEADER):
        return _detect_ole_mime(file)
    if header.startswith(ZIP_HEADER):
        return _detect_zip_mime(file)
    if detected_mime == "text/plain":
        file.seek(0)
        content = file.read(64 * 1024)
        file.seek(0)
        if b"\x00" in content:
            return "application/octet-stream"
        return _detect_eml_mime(content, detected_mime)
    if detected_mime == "text/rtf":
        return "application/rtf"
    return detected_mime


def _detect_ole_mime(file: BinaryIO) -> str:
    file.seek(0)
    try:
        ole = olefile.OleFileIO(file)
    except (OSError, ValueError):
        return "application/x-ole-storage"

    try:
        streams = {"/".join(parts) for parts in ole.listdir(streams=True, storages=False)}
    finally:
        ole.close()
        file.seek(0)

    if "WordDocument" in streams and ({"0Table", "1Table", "Table"} & streams):
        return OLE_MIME_TYPES["word"]
    if "Workbook" in streams or "Book" in streams:
        return OLE_MIME_TYPES["excel"]
    if "PowerPoint Document" in streams:
        return OLE_MIME_TYPES["powerpoint"]
    if any(name.startswith("__substg1.0_") for name in streams) and any(
        name.startswith("__properties_version") or name.startswith("__nameid_version")
        for name in streams
    ):
        return OLE_MIME_TYPES["message"]
    return "application/x-ole-storage"


def _detect_zip_mime(file: BinaryIO) -> str:
    file.seek(0)
    try:
        with zipfile.ZipFile(file) as archive:
            names = set(archive.namelist())
            for entry, mime_type in OOXML_MIME_TYPES.items():
                if entry in names:
                    return mime_type
            if "mimetype" in names:
                declared = archive.read("mimetype").decode("ascii", errors="ignore").strip()
                if declared == "application/epub+zip" and "META-INF/container.xml" in names:
                    return declared
                if declared in ODF_MIME_TYPES:
                    return ODF_MIME_TYPES[declared]
    except (OSError, ValueError, UnicodeError, zipfile.BadZipFile):
        return "application/zip"
    finally:
        file.seek(0)
    return "application/zip"


def _detect_eml_mime(content: bytes, fallback: str) -> str:
    try:
        message = BytesParser(policy=policy.default).parsebytes(content)
    except (OSError, ValueError):
        return fallback
    if message.get("From") and message.get("Date") and message.get("MIME-Version"):
        return "message/rfc822"
    return fallback
