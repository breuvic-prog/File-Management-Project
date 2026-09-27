import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


class ConversionError(RuntimeError):
    """FFmpeg could not produce a completed output file."""


class FileConversionManager:
    """Convert local media files using FFmpeg without deleting the source."""

    def __init__(self, ffmpeg_location: str | Path | None = None):
        """Accept an FFmpeg executable, its directory, or None to search PATH."""
        self._ffmpeg_location = ffmpeg_location

    def _get_ffmpeg(self) -> str:
        if self._ffmpeg_location is None:
            executable = "ffmpeg"
        else:
            location = Path(self._ffmpeg_location).expanduser().resolve()
            executable = str(location / "ffmpeg" if location.is_dir() else location)
        resolved = shutil.which(executable)
        if resolved is None:
            raise ConversionError(
                "FFmpeg was not found. Install it and add it to PATH, or pass "
                "ffmpeg_location to FileConversionManager."
            )
        return resolved

    def mp4_to_mp3(
        self,
        source_path: str | Path,
        destination_path: str | Path | None = None,
        *,
        quality: int = 2,
        overwrite: bool = False,
    ) -> Path:
        """Convert the first audio stream to MP3 and return its absolute path.

        The default output is beside the source with an .mp3 extension. Quality
        is a variable-bitrate setting from 0 (highest) to 9 (lowest). Common text
        tags are copied; video, artwork, and additional audio streams are omitted.
        Existing outputs require overwrite=True and survive a failed conversion.
        FFmpeg failures raise ConversionError; invalid paths/options raise the
        corresponding ValueError or OSError. Ctrl+C cancels and cleans up staging.
        """
        source = Path(source_path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(f"Source file does not exist: {source}")
        if not source.is_file():
            raise IsADirectoryError(f"Source must be a file: {source}")
        if source.suffix.lower() != ".mp4":
            raise ValueError("source_path must have an .mp4 extension")
        if type(quality) is not int or not 0 <= quality <= 9:
            raise ValueError("quality must be an integer between 0 and 9")

        destination = (
            Path(destination_path).expanduser().resolve()
            if destination_path is not None else source.with_suffix(".mp3")
        )
        if destination == source or (destination.exists() and destination.samefile(source)):
            raise ValueError("Source and destination must be different files")
        if destination.suffix.lower() != ".mp3":
            raise ValueError("destination_path must have an .mp3 extension")
        if destination.is_dir():
            raise IsADirectoryError(f"Destination must be a file: {destination}")
        if destination.exists() and not overwrite:
            raise FileExistsError(f"Destination already exists: {destination}")

        ffmpeg = self._get_ffmpeg()
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Stage on the destination filesystem so publication is atomic.
        with TemporaryDirectory(prefix=".mp3-conversion-", dir=destination.parent) as directory:
            temporary = Path(directory) / "output.mp3"
            command = [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                "-i", str(source), "-map", "0:a:0", "-vn",
                "-map_metadata", "0", "-map_chapters", "-1",
                "-c:a", "libmp3lame", "-q:a", str(quality), str(temporary),
            ]
            try:
                completed = subprocess.run(
                    command, check=False, capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            except OSError as error:
                raise ConversionError(f"Could not run FFmpeg: {error}") from error
            if completed.returncode != 0:
                detail = completed.stderr.strip() or f"exit code {completed.returncode}"
                raise ConversionError(f"MP4 to MP3 conversion failed: {detail}")
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise ConversionError("FFmpeg finished without producing a nonempty MP3 file")

            if overwrite:
                temporary.replace(destination)
            elif os.name == "nt":
                # Windows rename refuses to replace a destination created mid-conversion.
                temporary.rename(destination)
            else:
                # POSIX rename overwrites; creating a hard link refuses existing files.
                os.link(temporary, destination)
        return destination
