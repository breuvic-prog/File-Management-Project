from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit


@dataclass(frozen=True)
class DownloadRequest:
    """Settings for one URL; a playlist is limited to one item unless enabled."""

    url: str
    destination: Path | str = Path("downloads")
    mode: Literal["video", "audio"] = "video"
    audio_format: Literal["original", "mp3"] = "original"
    max_height: int | None = None
    playlist: bool = False
    embed_metadata: bool = True
    ffmpeg_location: Path | str | None = None

    def __post_init__(self) -> None:
        url = self.url.strip()
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("url must be an HTTP or HTTPS URL")
        if self.mode not in ("video", "audio"):
            raise ValueError("mode must be 'video' or 'audio'")
        if self.audio_format not in ("original", "mp3"):
            raise ValueError("audio_format must be 'original' or 'mp3'")
        if self.mode == "video" and self.audio_format != "original":
            raise ValueError("MP3 conversion requires audio mode")
        if self.max_height is not None:
            if type(self.max_height) is not int or self.max_height <= 0:
                raise ValueError("max_height must be a positive integer")
            if self.mode != "video":
                raise ValueError("max_height applies only to video downloads")
        object.__setattr__(self, "url", url)
        object.__setattr__(self, "destination", Path(self.destination).expanduser().resolve())
        if self.ffmpeg_location is not None:
            object.__setattr__(self, "ffmpeg_location", Path(self.ffmpeg_location).expanduser().resolve())
