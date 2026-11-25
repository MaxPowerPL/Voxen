"""
Local file storage for chat attachments.
"""

import mimetypes
import shutil
import uuid
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps


class FileManager:
    MAX_FILE_SIZE = 25 * 1024 * 1024
    THUMBNAIL_SIZE = (320, 320)

    def __init__(self, storage_dir: Optional[str | Path] = None, base_dir: Optional[str | Path] = None):
        directory = storage_dir or base_dir or "voxen_attachments"
        self.storage_dir = Path(directory)
        self.base_dir = self.storage_dir
        self.attachments_dir = self.storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def validate_file(self, file_path: str | Path) -> tuple[bool, str]:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return False, "Plik nie istnieje."
        size = path.stat().st_size
        if size <= 0:
            return False, "Plik jest pusty."
        if size > self.MAX_FILE_SIZE:
            return False, "Plik przekracza maksymalny rozmiar 25 MB."
        return True, ""

    def is_valid_file(self, file_path: str | Path) -> bool:
        return self.validate_file(file_path)[0]

    def generate_thumbnail(self, file_path: str | Path) -> Optional[str]:
        path = Path(file_path)
        try:
            with Image.open(path) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail(self.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

                output_suffix = ".png" if image.mode in ("RGBA", "LA") else ".jpg"
                thumbnail_path = path.with_name(f"{path.stem}_thumb{output_suffix}")

                if output_suffix == ".jpg":
                    if image.mode not in ("RGB", "L"):
                        image = image.convert("RGB")
                    image.save(thumbnail_path, "JPEG", quality=85)
                else:
                    if image.mode not in ("RGBA", "LA"):
                        image = image.convert("RGBA")
                    image.save(thumbnail_path, "PNG")

                return str(thumbnail_path)
        except (OSError, ValueError):
            return None

    def store_file(self, file_path: str | Path) -> dict:
        source = Path(file_path)
        valid, error = self.validate_file(source)
        if not valid:
            raise ValueError(error)

        unique_name = f"{uuid.uuid4().hex}{source.suffix.lower()}"
        destination = self.storage_dir / unique_name
        shutil.copy2(source, destination)

        mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        file_type = "image" if mime_type.startswith("image/") else "file"
        thumbnail_path = None
        if file_type == "image":
            thumbnail_path = self.generate_thumbnail(destination)

        return {
            "filename": unique_name,
            "stored_name": unique_name,
            "original_name": source.name,
            "original_filename": source.name,
            "file_type": file_type,
            "file_size": destination.stat().st_size,
            "size": destination.stat().st_size,
            "mime_type": mime_type,
            "file_path": str(destination),
            "path": str(destination),
            "thumbnail_path": thumbnail_path,
        }

    save_file = store_file
    copy_file = store_file

    def delete_file(self, file_path: str | Path, thumbnail_path: Optional[str | Path] = None) -> bool:
        deleted = False
        path = Path(file_path)
        if path.exists():
            path.unlink()
            deleted = True
        if thumbnail_path:
            thumb = Path(thumbnail_path)
            if thumb.exists():
                thumb.unlink()
        return deleted
