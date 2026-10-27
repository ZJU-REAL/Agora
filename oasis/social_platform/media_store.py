# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


class MediaValidationError(ValueError):
    """Raised when an imported media file violates sandbox constraints."""


@dataclass(frozen=True)
class MediaLimits:
    max_image_bytes: int = 20 * 1024 * 1024
    max_video_bytes: int = 500 * 1024 * 1024
    max_video_duration_ms: int = 10 * 60 * 1000


@dataclass(frozen=True)
class ImportedMedia:
    asset_id: str
    media_type: str
    object_key: str
    original_filename: str
    mime_type: str
    byte_size: int
    checksum_sha256: str
    width: int | None
    height: int | None
    duration_ms: int | None
    technical_metadata: dict


class LocalMediaStore:
    """Validates and atomically imports media into a sandbox-local store."""

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
    VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}

    def __init__(self, root: str | os.PathLike, limits: MediaLimits | None = None):
        self.root = Path(root).resolve()
        self.limits = limits or MediaLimits()
        self.root.mkdir(parents=True, exist_ok=True)

    def import_file(self, source: str | os.PathLike) -> ImportedMedia:
        source_path = Path(source).resolve(strict=True)
        if not source_path.is_file():
            raise MediaValidationError("Media source must be a regular file.")

        extension = source_path.suffix.lower()
        if extension in self.IMAGE_EXTENSIONS:
            media_type = "image"
            max_bytes = self.limits.max_image_bytes
        elif extension in self.VIDEO_EXTENSIONS:
            media_type = "video"
            max_bytes = self.limits.max_video_bytes
        else:
            raise MediaValidationError(f"Unsupported media extension: {extension}")

        byte_size = source_path.stat().st_size
        if byte_size > max_bytes:
            raise MediaValidationError(
                f"{media_type} exceeds the {max_bytes} byte size limit.")

        if media_type == "image":
            metadata = self._inspect_image(source_path)
        else:
            metadata = self._inspect_video(source_path)
            duration_ms = metadata.get("duration_ms")
            if (duration_ms is not None
                    and duration_ms > self.limits.max_video_duration_ms):
                raise MediaValidationError(
                    "Video exceeds the configured duration limit.")

        asset_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        object_key = Path("originals") / f"{media_type}s" / str(
            now.year) / f"{now.month:02d}" / f"{asset_id}{extension}"
        destination = self._resolve_object_key(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")

        checksum = hashlib.sha256()
        try:
            with source_path.open("rb") as source_file, temporary.open(
                    "xb") as destination_file:
                while chunk := source_file.read(1024 * 1024):
                    checksum.update(chunk)
                    destination_file.write(chunk)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()

        mime_type = metadata.get("mime_type") or mimetypes.guess_type(
            source_path.name)[0] or "application/octet-stream"
        return ImportedMedia(
            asset_id=asset_id,
            media_type=media_type,
            object_key=object_key.as_posix(),
            original_filename=source_path.name,
            mime_type=mime_type,
            byte_size=byte_size,
            checksum_sha256=checksum.hexdigest(),
            width=metadata.get("width"),
            height=metadata.get("height"),
            duration_ms=metadata.get("duration_ms"),
            technical_metadata=metadata,
        )

    def path_for(self, object_key: str) -> Path:
        path = self._resolve_object_key(Path(object_key))
        if not path.is_file():
            raise FileNotFoundError(object_key)
        return path

    def _resolve_object_key(self, object_key: Path) -> Path:
        if object_key.is_absolute():
            raise MediaValidationError("Media object keys must be relative.")
        resolved = (self.root / object_key).resolve()
        if self.root not in resolved.parents:
            raise MediaValidationError("Media object key escapes the store.")
        return resolved

    @staticmethod
    def _inspect_image(path: Path) -> dict:
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image_format = (image.format or "").upper()
                if image_format not in {"JPEG", "PNG", "WEBP"}:
                    raise MediaValidationError(
                        f"Unsupported image format: {image_format}")
                return {
                    "format": image_format,
                    "mime_type": Image.MIME.get(image_format),
                    "width": image.width,
                    "height": image.height,
                }
        except MediaValidationError:
            raise
        except Exception as exc:
            raise MediaValidationError("Invalid or corrupt image.") from exc

    @staticmethod
    def _inspect_video(path: Path) -> dict:
        command = [
            "ffprobe", "-v", "error", "-show_streams", "-show_format",
            "-of", "json", str(path)
        ]
        try:
            completed = subprocess.run(command,
                                       check=True,
                                       capture_output=True,
                                       text=True)
        except FileNotFoundError as exc:
            raise MediaValidationError(
                "ffprobe is required to import videos.") from exc
        except subprocess.CalledProcessError as exc:
            raise MediaValidationError("Invalid or unsupported video.") from exc

        probe = json.loads(completed.stdout)
        video_stream = next((stream for stream in probe.get("streams", [])
                             if stream.get("codec_type") == "video"), None)
        if video_stream is None:
            raise MediaValidationError("File contains no video stream.")
        duration = probe.get("format", {}).get("duration")
        return {
            "format": probe.get("format", {}).get("format_name"),
            "mime_type": mimetypes.guess_type(path.name)[0],
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "duration_ms": round(float(duration) * 1000) if duration else None,
            "video_codec": video_stream.get("codec_name"),
        }


def media_record_values(media: ImportedMedia) -> tuple:
    """Returns values in media_asset insert-column order."""
    return (
        media.asset_id,
        media.media_type,
        media.object_key,
        media.original_filename,
        media.mime_type,
        media.byte_size,
        media.checksum_sha256,
        media.width,
        media.height,
        media.duration_ms,
        json.dumps(media.technical_metadata, ensure_ascii=True),
    )
