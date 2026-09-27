"""Imports"""
import os
import stat
from datetime import datetime, timezone
import ntsecuritycon
import pywintypes
import win32con
import win32file


class FileMetadata:
    def __init__(self, path: str):
        self._path = path

    """Getters"""
    @property
    def path(self) -> str:
        return self._path

    @property
    def name(self) -> str:
        """Return the filename, including its extension."""
        return os.path.basename(self._path)

    @property
    def extension(self) -> str:
        """Return the final extension with its dot, or an empty string."""
        return os.path.splitext(self.name)[1]

    @property
    def size(self) -> int:
        """Return the current file size in bytes."""
        return os.path.getsize(self._path)

    @property
    def is_read_only(self) -> bool:
        """Return whether the Windows read-only file attribute is set."""
        return bool(os.stat(self._path).st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)

    @property
    def permissions(self) -> int:
        """Return basic mode bits (e.g. 0o666), excluding Windows ACL permissions."""
        return stat.S_IMODE(os.stat(self._path).st_mode)

    @property
    def created_at(self) -> datetime:
        timestamp = os.stat(self._path).st_birthtime
        return datetime.fromtimestamp(timestamp)

    @property
    def last_modified(self) -> datetime:
        timestamp = os.path.getmtime(self._path)
        return datetime.fromtimestamp(timestamp)

    @property
    def last_accessed(self) -> datetime:
        timestamp = os.path.getatime(self._path)
        return datetime.fromtimestamp(timestamp)

    """Setters"""
    @name.setter
    def name(self, name: str) -> None:
        """Rename within the current directory and update the stored path on success."""
        if (not name or name in (".", "..")
                or os.path.basename(name) != name or os.path.isreserved(name)):
            raise ValueError("name must be a valid filename without a directory")

        new_path = os.path.join(os.path.dirname(self._path), name)
        os.rename(self._path, new_path)
        self._path = new_path

    @extension.setter
    def extension(self, extension: str) -> None:
        """Replace the final suffix; accept a leading dot or an empty string to remove it."""
        if extension:
            extension = extension if extension.startswith(".") else "." + extension
            if extension == "." or "." in extension[1:]:
                raise ValueError("extension must contain a single suffix")
        self.name = os.path.splitext(self.name)[0] + extension

    @is_read_only.setter
    def is_read_only(self, is_read_only: bool) -> None:
        """Set or clear the Windows read-only attribute."""
        permissions = self.permissions
        if is_read_only:
            permissions &= ~stat.S_IWRITE
        else:
            permissions |= stat.S_IWRITE
        os.chmod(self._path, permissions)

    @permissions.setter
    def permissions(self, permissions: int) -> None:
        """Set mode bits; Windows uses only the write bit to change the read-only flag."""
        os.chmod(self._path, permissions)

    @created_at.setter
    def created_at(self, created_at: datetime):
        handle = win32file.CreateFile(
            self._path,
            ntsecuritycon.FILE_WRITE_ATTRIBUTES,
            win32con.FILE_SHARE_READ |
            win32con.FILE_SHARE_WRITE |
            win32con.FILE_SHARE_DELETE,
            None,
            win32con.OPEN_EXISTING,
            win32con.FILE_ATTRIBUTE_NORMAL,
            None
        )

        try:
            win32file.SetFileTime(
                int(handle),
                pywintypes.TimeType.fromtimestamp(created_at.timestamp(), timezone.utc),
                None,
                None
            )
        finally:
            handle.Close()

    @last_modified.setter
    def last_modified(self, last_modified: datetime):
        os.utime(self._path,
                 times = (os.path.getatime(self._path),
                          last_modified.timestamp()))

    @last_accessed.setter
    def last_accessed(self, last_accessed: datetime):
        os.utime(self._path,
                 times = (last_accessed.timestamp(),
                          os.path.getmtime(self._path)))
