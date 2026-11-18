"""File-backed HTTP media responses; never load an entire video into RAM."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaResponse:
    path: Path
    delete_after: bool = False
    download_name: str | None = None


def byte_range(header, size):
    if not header:
        return 0, max(0, size - 1), False
    if not header.startswith("bytes=") or "," in header:
        raise ValueError("Unsupported byte range")
    start, end = header[6:].split("-", 1)
    if not start:
        count = int(end)
        if count <= 0:
            raise ValueError("Invalid suffix range")
        start, end = max(0, size - count), size - 1
    else:
        start, end = int(start), min(size - 1, int(end)) if end else size - 1
    if start < 0 or start >= size or end < start:
        raise ValueError("Invalid byte range")
    return start, end, True
