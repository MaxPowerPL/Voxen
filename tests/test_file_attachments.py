"""
INTEGRATION TEST - CHAT FILE ATTACHMENTS
"""

import shutil
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from PIL import Image

from database.db import DatabaseManager
from storage.file_manager import FileManager


def test_file_attachments():
    print("=== TEST ZAŁĄCZNIKÓW CZATU ===")
    test_db = "test_file_attachments.db"
    test_storage = Path("test_voxen_attachments")
    source_dir = test_storage / "source"

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            Path(p).unlink()
    if test_storage.exists():
        shutil.rmtree(test_storage)
    source_dir.mkdir(parents=True)

    db = DatabaseManager(db_path=test_db)
    manager = FileManager(storage_dir=test_storage / "stored")

    text_source = source_dir / "notatki.txt"
    text_source.write_text("Voxen attachment test", encoding="utf-8")
    valid, error = manager.validate_file(text_source)
    assert valid and error == ""

    text_metadata = manager.store_file(text_source)
    assert text_metadata["original_name"] == "notatki.txt"
    assert text_metadata["file_type"] == "file"
    assert text_metadata["thumbnail_path"] is None
    assert Path(text_metadata["file_path"]).exists()

    image_source = source_dir / "preview.png"
    Image.new("RGB", (800, 600), color=(88, 101, 242)).save(image_source)
    image_metadata = manager.store_file(image_source)
    assert image_metadata["file_type"] == "image"
    assert image_metadata["thumbnail_path"]
    thumb = Path(image_metadata["thumbnail_path"])
    assert thumb.exists()
    with Image.open(thumb) as image:
        assert image.width <= 320
        assert image.height <= 320

    oversized = source_dir / "oversized.bin"
    oversized.write_bytes(b"x" * (25 * 1024 * 1024 + 1))
    valid, error = manager.validate_file(oversized)
    assert not valid
    assert "25 MB" in error

    message_id = db.save_message(
        sender="Tester",
        target="User",
        content="Załączniki",
        packet_id="attachment-test-message"
    )
    assert message_id > 0

    text_attachment_id = db.save_attachment(
        message_id=message_id,
        filename=text_metadata["filename"],
        original_name=text_metadata["original_name"],
        file_type=text_metadata["file_type"],
        file_size=text_metadata["file_size"],
        mime_type=text_metadata["mime_type"],
        file_path=text_metadata["file_path"],
        thumbnail_path=text_metadata["thumbnail_path"]
    )
    image_attachment_id = db.save_attachment(
        message_id=message_id,
        filename=image_metadata["filename"],
        original_name=image_metadata["original_name"],
        file_type=image_metadata["file_type"],
        file_size=image_metadata["file_size"],
        mime_type=image_metadata["mime_type"],
        file_path=image_metadata["file_path"],
        thumbnail_path=image_metadata["thumbnail_path"]
    )

    attachments = db.get_attachments(message_id)
    assert len(attachments) == 2
    assert db.get_attachment(text_attachment_id)["original_name"] == "notatki.txt"
    assert db.get_message_attachments(message_id) == attachments
    assert db.get_attachment(image_attachment_id)["file_type"] == "image"

    assert db.delete_attachment(text_attachment_id)
    assert len(db.get_attachments(message_id)) == 1

    for p in [test_db, f"{test_db}-wal", f"{test_db}-shm"]:
        if Path(p).exists():
            try:
                Path(p).unlink()
            except PermissionError:
                pass
    if test_storage.exists():
        shutil.rmtree(test_storage)

    print("=== WSZYSTKIE TESTY ZAŁĄCZNIKÓW ZAKOŃCZONE SUKCESSEM! ===")


if __name__ == "__main__":
    test_file_attachments()
