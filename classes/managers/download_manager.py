from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from classes.downloaders.yt_dlp_downloader import YtDlpDownloader
from classes.object_relation_models.download_request import DownloadRequest
from classes.object_relation_models.download_result import (
    DownloadError, DownloadProgress, DownloadResult, DownloadedFile, ProgressCallback,
)


class DownloadManager:
    """Coordinate one synchronous request, which may contain several playlist items."""

    def __init__(self, downloader: YtDlpDownloader | None = None):
        self._downloader = downloader if downloader is not None else YtDlpDownloader()

    def download(self, request: DownloadRequest,
                 on_progress: ProgressCallback | None = None) -> DownloadResult:
        started_at = datetime.now(timezone.utc)
        files: list[DownloadedFile] = []

        def emit(progress: DownloadProgress) -> None:
            if on_progress is not None:
                on_progress(progress)

        def result(status: Literal["completed", "failed"] = "completed") -> DownloadResult:
            return DownloadResult(
                request.url, tuple(files), started_at, datetime.now(timezone.utc), status,
            )

        try:
            Path(request.destination).mkdir(parents=True, exist_ok=True)
            emit(DownloadProgress("inspecting", message=request.url))
            self._downloader.download(request, emit, files.append)
            if not files:
                raise DownloadError("No media files were produced for this URL")
        except (DownloadError, OSError) as error:
            emit(DownloadProgress("failed", message=str(error)))
            raise DownloadError(str(error), result("failed")) from error

        emit(DownloadProgress("completed", message=f"{len(files)} file(s) ready"))
        return result()

    @staticmethod
    def metadata_for(file: DownloadedFile):
        """Create the existing live metadata wrapper for a completed file."""
        from classes.object_relation_models.file_metadata_class import FileMetadata
        from classes.object_relation_models.mp3_metadata_class import MP3Metadata

        metadata_type = MP3Metadata if file.path.suffix.lower() == ".mp3" else FileMetadata
        return metadata_type(str(file.path))
