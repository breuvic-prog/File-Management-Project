"""Imports"""
from mutagen.id3 import COMM, Encoding, Frames
from mutagen.mp3 import MP3

from classes.object_relation_models.file_metadata_class import FileMetadata


class MP3Metadata(FileMetadata):
    """Live MP3 metadata; tag setters save immediately and None removes a tag.

    Text getters return the first value when a tag contains multiple values.
    Each access uses the current path, including after an inherited rename.
    Missing, unreadable, or invalid MP3 files raise Mutagen errors.
    """

    def __init__(self, path: str):
        super().__init__(path)

    """Helper Methods"""
    def _get_text(self, frame_id: str) -> str | None:
        audio = MP3(self._path)
        if audio.tags is None:
            return None
        frame = audio.tags.get(frame_id)
        return str(frame.text[0]) if frame is not None and frame.text else None

    def _set_text(self, frame_id: str, value: str | None) -> None:
        audio = MP3(self._path)
        if audio.tags is None:
            if value is None:
                return
            audio.add_tags()
        if value is None:
            audio.tags.delall(frame_id)
        else:
            audio.tags.add(Frames[frame_id](encoding=Encoding.UTF8, text=[value]))
        audio.save()

    """Getters"""
    @property
    def title(self) -> str | None:
        return self._get_text("TIT2")

    @property
    def artist(self) -> str | None:
        return self._get_text("TPE1")

    @property
    def album(self) -> str | None:
        return self._get_text("TALB")

    @property
    def album_artist(self) -> str | None:
        return self._get_text("TPE2")

    @property
    def genre(self) -> str | None:
        return self._get_text("TCON")

    @property
    def composer(self) -> str | None:
        return self._get_text("TCOM")

    @property
    def year(self) -> int | None:
        """Return the year from the recording-date tag."""
        value = self._get_text("TDRC")
        return int(value[:4]) if value else None

    @property
    def track_number(self) -> str | None:
        """Return the track number, optionally including a total (e.g. '3/12')."""
        return self._get_text("TRCK")

    @property
    def disc_number(self) -> str | None:
        """Return the disc number, optionally including a total (e.g. '1/2')."""
        return self._get_text("TPOS")

    @property
    def comment(self) -> str | None:
        """Return the English comment with an empty description."""
        return self._get_text("COMM::eng")

    @property
    def duration(self) -> float:
        """Return the audio duration in seconds."""
        return MP3(self._path).info.length

    @property
    def bitrate(self) -> int:
        """Return the audio bitrate in bits per second."""
        return MP3(self._path).info.bitrate

    @property
    def sample_rate(self) -> int:
        """Return the sample rate in Hz."""
        return MP3(self._path).info.sample_rate

    @property
    def channels(self) -> int:
        """Return the number of audio channels."""
        return MP3(self._path).info.channels

    """Setters"""
    @title.setter
    def title(self, title: str | None) -> None:
        self._set_text("TIT2", title)

    @artist.setter
    def artist(self, artist: str | None) -> None:
        self._set_text("TPE1", artist)

    @album.setter
    def album(self, album: str | None) -> None:
        self._set_text("TALB", album)

    @album_artist.setter
    def album_artist(self, album_artist: str | None) -> None:
        self._set_text("TPE2", album_artist)

    @genre.setter
    def genre(self, genre: str | None) -> None:
        self._set_text("TCON", genre)

    @composer.setter
    def composer(self, composer: str | None) -> None:
        self._set_text("TCOM", composer)

    @year.setter
    def year(self, year: int | None) -> None:
        """Replace the recording-date tag with a year, or remove it with None."""
        if year is not None and (type(year) is not int or not 1 <= year <= 9999):
            raise ValueError("year must be an integer between 1 and 9999, or None")
        self._set_text("TDRC", f"{year:04d}" if year is not None else None)

    @track_number.setter
    def track_number(self, track_number: str | None) -> None:
        self._set_text("TRCK", track_number)

    @disc_number.setter
    def disc_number(self, disc_number: str | None) -> None:
        self._set_text("TPOS", disc_number)

    @comment.setter
    def comment(self, comment: str | None) -> None:
        """Set the English comment with an empty description; preserve other comments."""
        audio = MP3(self._path)
        if audio.tags is None:
            if comment is None:
                return
            audio.add_tags()
        if comment is None:
            audio.tags.delall("COMM::eng")
        else:
            audio.tags.add(COMM(encoding=Encoding.UTF8, lang="eng", desc="", text=[comment]))
        audio.save()
