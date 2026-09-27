"""Command-line entry point. Run with --help for download options."""

import argparse
import logging
import sys
import time
from pathlib import Path

from classes.managers.download_manager import DownloadManager
from classes.object_relation_models.download_request import DownloadRequest
from classes.object_relation_models.download_result import DownloadError, DownloadProgress


class ConsoleProgress:
    def __init__(self):
        self._last_update = 0.0

    def __call__(self, progress: DownloadProgress) -> None:
        if progress.stage == "downloading":
            now = time.monotonic()
            if now - self._last_update < 0.5:
                return
            self._last_update = now
            downloaded = progress.downloaded_bytes or 0
            if progress.total_bytes:
                detail = f"{downloaded / progress.total_bytes:.1%}"
            else:
                detail = f"{downloaded / 1024 / 1024:.1f} MiB"
            if progress.speed is not None:
                detail += f" at {progress.speed / 1024 / 1024:.1f} MiB/s"
            if progress.eta is not None:
                detail += f", ETA {progress.eta:.0f}s"
            print(f"Downloading {progress.title}: {detail}", file=sys.stderr)
        elif progress.stage not in ("saved", "failed"):
            print(f"{progress.stage.capitalize()}: {progress.message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download videos or audio using yt-dlp.")
    parser.add_argument("url", help="Video URL, or playlist URL with --playlist")
    parser.add_argument("-o", "--destination", type=Path, default=Path("downloads"))
    audio = parser.add_mutually_exclusive_group()
    audio.add_argument("--audio", action="store_true", help="Extract audio in its original format")
    audio.add_argument("--mp3", action="store_true", help="Extract and convert audio to MP3")
    parser.add_argument("--max-height", type=int, help="Maximum video height, e.g. 1080")
    parser.add_argument("--playlist", action="store_true", help="Download every playlist item")
    parser.add_argument("--no-embed-metadata", action="store_true", help="Skip embedding source tags")
    parser.add_argument("--ffmpeg-location", type=Path, help="Directory containing ffmpeg and ffprobe")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    try:
        request = DownloadRequest(
            url=args.url, destination=args.destination,
            mode="audio" if args.audio or args.mp3 else "video",
            audio_format="mp3" if args.mp3 else "original",
            max_height=args.max_height, playlist=args.playlist,
            embed_metadata=not args.no_embed_metadata, ffmpeg_location=args.ffmpeg_location,
        )
    except ValueError as error:
        parser.error(str(error))

    try:
        result = DownloadManager().download(request, ConsoleProgress())
    except DownloadError as error:
        print(f"Download failed: {error}", file=sys.stderr)
        if error.result:
            for file in error.result.files:
                print(f"Already completed: {file.path}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled. Run the same command to resume available partial downloads.", file=sys.stderr)
        return 130

    for file in result.files:
        print(file.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
