from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Literal


@dataclass(frozen=True)
class DownloadedFile:
    """A finished media file and its source metadata, separate from filesystem dates."""

    path: Path
    source_url: str
    media_id: str
    title: str
    uploader: str | None = None
    upload_date: date | None = None
    duration: float | None = None


@dataclass(frozen=True)
class DownloadResult:
    request_url: str
    files: tuple[DownloadedFile, ...]
    started_at: datetime
    finished_at: datetime
    status: Literal["completed", "failed"] = "completed"


@dataclass(frozen=True)
class DownloadProgress:
    """Progress for the current stream; totals may be unknown or estimated."""

    stage: Literal["inspecting", "downloading", "processing", "saved", "completed", "failed"]
    title: str = ""
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed: float | None = None
    eta: float | None = None
    message: str = ""


ProgressCallback = Callable[[DownloadProgress], None]


class DownloadError(RuntimeError):
    """Download failure; result includes files completed before the failure."""

    def __init__(self, message: str, result: DownloadResult | None = None):
        super().__init__(message)
        self.result = result
