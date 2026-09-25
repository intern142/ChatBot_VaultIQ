import io
import uuid

import pytest

from app.services.storage import UploadTooLargeError, save_uploaded_file


def test_bounded_upload_removes_partial_file(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.STORAGE_ROOT", tmp_path)
    tenant_id = uuid.uuid4()
    document_id = uuid.uuid4()
    with pytest.raises(UploadTooLargeError):
        save_uploaded_file(
            io.BytesIO(b"123456789"),
            tenant_id,
            document_id,
            "document.txt",
            max_bytes=8,
        )
    assert not (tmp_path / str(tenant_id)).exists()
