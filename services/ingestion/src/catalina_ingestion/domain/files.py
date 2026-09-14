from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FileInspection:
    mime_type: str
    encoding: str | None = None
    page_count: int | None = None


@dataclass(frozen=True, slots=True)
class ValidatedFile:
    original_name: str
    safe_name: str
    extension: str
    mime_type: str
    client_mime_type: str | None
    encoding: str | None
    size_bytes: int
    sha256: str
    staging_path: Path
    page_count: int | None
