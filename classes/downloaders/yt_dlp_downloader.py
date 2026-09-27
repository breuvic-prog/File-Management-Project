from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from yt_dlp import YoutubeDL
from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.utils import DownloadError as YtDlpError, PostProcessingError

from classes.object_relation_models.download_request import DownloadRequest
from classes.object_relation_models.download_result import (
    DownloadedFile, DownloadError, DownloadProgress, ProgressCallback,
)

if TYPE_CHECKING:
    from yt_dlp import _Params


class _Logger:
    """Keep library output out of the UI; warnings remain visible through logging."""

    def __init__(self, ydl: YoutubeDL | None = None):
        self.downloader = ydl
        self._logger = logging.getLogger(__name__)
        self._warnings: set[str] = set()

    def debug(self, message: str) -> None:
        self._logger.debug(message)

    def info(self, message: str) -> None:
        self._logger.debug(message)

    def warning(self, message: str, *, once: bool = False, only_once: bool = False) -> None:
        if (once or only_once) and message in self._warnings:
            return
        self._warnings.add(message)
        self._logger.warning(message)

    def error(self, message: str) -> None:
        self._logger.debug(message)

    def stdout(self, message: str) -> None:
        self._logger.debug(message)

    def stderr(self, message: str) -> None:
        self._logger.debug(message)


class FinalFilePP(PostProcessor):
    """Capture the actual path after conversion, metadata embedding, and moving."""

    def __init__(self, downloader, request, on_file, on_progress):
        super().__init__(downloader)
        self.request = request
        self.on_file = on_file
        self.on_progress = on_progress

    def run(self, information: Any) -> tuple[list[str], Any]:
        info = information
        filename = info.get("filepath")
        if not filename or not Path(filename).is_file():
            raise PostProcessingError("The final output file was not created")
        upload_date = None
        if info.get("upload_date"):
            try:
                upload_date = datetime.strptime(info["upload_date"], "%Y%m%d").date()
            except ValueError:
                pass
        result = DownloadedFile(
            path=Path(filename).resolve(),
            source_url=info.get("webpage_url") or info.get("original_url") or self.request.url,
            media_id=str(info.get("id", "")),
            title=info.get("title") or Path(filename).stem,
            uploader=info.get("uploader"), upload_date=upload_date,
            duration=info.get("duration"),
        )
        self.on_file(result)
        self.on_progress(DownloadProgress("saved", title=result.title, message=str(result.path)))
        return [], info


class YtDlpDownloader:
    """Synchronous video-site downloader. Each call has its own yt-dlp instance."""

    @staticmethod
    def _options(request: DownloadRequest, on_progress: ProgressCallback) -> _Params:
        def download_hook(data):
            title = data.get("info_dict", {}).get("title", "")
            if data["status"] == "downloading":
                on_progress(DownloadProgress(
                    "downloading", title=title,
                    downloaded_bytes=data.get("downloaded_bytes"),
                    total_bytes=data.get("total_bytes") or data.get("total_bytes_estimate"),
                    speed=data.get("speed"), eta=data.get("eta"),
                ))
            elif data["status"] == "finished":
                on_progress(DownloadProgress(
                    "processing", title=title, message="Stream downloaded; preparing output",
                ))

        def processing_hook(data):
            if data["status"] == "started" and data.get("postprocessor") != "FinalFile":
                on_progress(DownloadProgress(
                    "processing", title=data.get("info_dict", {}).get("title", ""),
                    message=data.get("postprocessor", "Processing"),
                ))

        if request.mode == "audio":
            selector = "bestaudio/best"
            profile = "mp3" if request.audio_format == "mp3" else "audio"
        else:
            height = f"[height<={request.max_height}]" if request.max_height else ""
            selector = f"bestvideo*{height}+bestaudio/best{height}"
            profile = f"video-{request.max_height or 'best'}"

        postprocessors = []
        if request.mode == "audio":
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3" if request.audio_format == "mp3" else "best",
                "preferredquality": "0", "nopostoverwrites": True,
            })
        if request.embed_metadata:
            postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})

        options: _Params = {
            "format": selector,
            "paths": {"home": str(request.destination)},
            "outtmpl": f"%(title).150B [%(id)s] [{profile}].%(ext)s",
            "windowsfilenames": True,
            "noplaylist": not request.playlist,
            # noplaylist alone doesn't limit URLs that refer only to a playlist.
            "playlist_items": None if request.playlist else "1",
            "continuedl": True, "nopart": False, "overwrites": False,
            "retries": 3, "fragment_retries": 3,
            "skip_unavailable_fragments": False,
            "socket_timeout": 30, "ignoreerrors": False, "updatetime": False,
            "quiet": True, "noprogress": True, "logger": _Logger(),
            "progress_hooks": [download_hook],
            "postprocessor_hooks": [processing_hook],
            "postprocessors": postprocessors,
            "js_runtimes": {"deno": {}, "node": {}},
        }
        if request.ffmpeg_location is not None:
            options["ffmpeg_location"] = str(request.ffmpeg_location)
        if request.mode == "audio" and request.audio_format == "mp3":
            options["final_ext"] = "mp3"
        return options

    @staticmethod
    def _check_dependencies(request: DownloadRequest) -> None:
        location = Path(request.ffmpeg_location) if request.ffmpeg_location else None
        if location is not None and location.is_file():
            location = location.parent
        for program in ("ffmpeg", "ffprobe"):
            executable = str(location / program) if location is not None else program
            if shutil.which(executable) is None:
                raise DownloadError(
                    f"{program} was not found. Install FFmpeg and ffprobe and put them on PATH, "
                    "or pass --ffmpeg-location with the directory containing them."
                )

    def download(self, request: DownloadRequest, on_progress: ProgressCallback,
                 on_file: Callable[[DownloadedFile], None]) -> None:
        try:
            self._check_dependencies(request)
            with YoutubeDL(self._options(request, on_progress)) as downloader:
                downloader.add_post_processor(
                    FinalFilePP(downloader, request, on_file, on_progress), when="after_move",
                )
                downloader.extract_info(request.url, download=True)
        except (YtDlpError, PostProcessingError, OSError) as error:
            raise DownloadError(str(error)) from error
