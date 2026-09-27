import os
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mutagen.mp3 import MP3

from classes.managers.file_conversion_manager import ConversionError, FileConversionManager


class FileConversionManagerTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "video with spaces.MP4"
        self.source.write_bytes(b"source data")
        self.manager = FileConversionManager()
        self.ffmpeg = patch.object(FileConversionManager, "_get_ffmpeg", return_value="ffmpeg.exe")
        self.ffmpeg.start()
        self.addCleanup(self.ffmpeg.stop)

    @staticmethod
    def successful_conversion(command, **kwargs):
        Path(command[-1]).write_bytes(b"converted audio")
        return subprocess.CompletedProcess(command, 0, "", "")

    def test_default_destination_and_command(self):
        with patch("classes.managers.file_conversion_manager.subprocess.run",
                   side_effect=self.successful_conversion) as run:
            output = self.manager.mp4_to_mp3(self.source)
        self.assertEqual(output, self.source.with_suffix(".mp3"))
        self.assertEqual(output.read_bytes(), b"converted audio")
        self.assertEqual(self.source.read_bytes(), b"source data")
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("-i") + 1], str(self.source))
        self.assertEqual(command[command.index("-map") + 1], "0:a:0")
        self.assertEqual(command[command.index("-q:a") + 1], "2")
        self.assertIn("libmp3lame", command)
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual(list(self.root.glob(".mp3-conversion-*")), [])

    def test_custom_destination_quality_and_overwrite(self):
        destination = self.root / "nested" / "audio.mp3"
        with patch("classes.managers.file_conversion_manager.subprocess.run",
                   side_effect=self.successful_conversion) as run:
            self.assertEqual(self.manager.mp4_to_mp3(self.source, destination, quality=0), destination)
            destination.write_bytes(b"old audio")
            self.manager.mp4_to_mp3(self.source, destination, overwrite=True)
        self.assertEqual(destination.read_bytes(), b"converted audio")
        command = run.call_args_list[0].args[0]
        self.assertEqual(command[command.index("-q:a") + 1], "0")

    def test_existing_destination_is_protected(self):
        destination = self.source.with_suffix(".mp3")
        destination.write_bytes(b"keep me")
        with patch("classes.managers.file_conversion_manager.subprocess.run") as run:
            with self.assertRaises(FileExistsError):
                self.manager.mp4_to_mp3(self.source)
            run.assert_not_called()
        self.assertEqual(destination.read_bytes(), b"keep me")

    def test_failed_conversion_preserves_existing_output_and_cleans_staging(self):
        destination = self.source.with_suffix(".mp3")
        destination.write_bytes(b"keep me")

        def fail(command, **kwargs):
            Path(command[-1]).write_bytes(b"incomplete")
            return subprocess.CompletedProcess(command, 1, "", "Stream map '0:a:0' matches no streams")

        with patch("classes.managers.file_conversion_manager.subprocess.run", side_effect=fail):
            with self.assertRaisesRegex(ConversionError, "matches no streams"):
                self.manager.mp4_to_mp3(self.source, overwrite=True)
        self.assertEqual(destination.read_bytes(), b"keep me")
        self.assertEqual(self.source.read_bytes(), b"source data")
        self.assertEqual(list(self.root.glob(".mp3-conversion-*")), [])

    def test_missing_or_empty_output_is_not_success(self):
        for create_empty in (False, True):
            def empty(command, **kwargs):
                if create_empty:
                    Path(command[-1]).touch()
                return subprocess.CompletedProcess(command, 0, "", "")

            with self.subTest(create_empty=create_empty), \
                    patch("classes.managers.file_conversion_manager.subprocess.run", side_effect=empty):
                with self.assertRaisesRegex(ConversionError, "nonempty MP3"):
                    self.manager.mp4_to_mp3(self.source)
            self.assertFalse(self.source.with_suffix(".mp3").exists())

    def test_cancellation_cleans_staging(self):
        def cancel(command, **kwargs):
            Path(command[-1]).write_bytes(b"incomplete")
            raise KeyboardInterrupt

        with patch("classes.managers.file_conversion_manager.subprocess.run", side_effect=cancel):
            with self.assertRaises(KeyboardInterrupt):
                self.manager.mp4_to_mp3(self.source)
        self.assertFalse(self.source.with_suffix(".mp3").exists())
        self.assertEqual(list(self.root.glob(".mp3-conversion-*")), [])

    def test_destination_created_during_conversion_is_not_overwritten(self):
        destination = self.source.with_suffix(".mp3")

        def race(command, **kwargs):
            destination.write_bytes(b"another process")
            return self.successful_conversion(command)

        with patch("classes.managers.file_conversion_manager.subprocess.run", side_effect=race):
            with self.assertRaises(FileExistsError):
                self.manager.mp4_to_mp3(self.source)
        self.assertEqual(destination.read_bytes(), b"another process")

    def test_invalid_paths_and_quality(self):
        with self.assertRaises(FileNotFoundError):
            self.manager.mp4_to_mp3(self.root / "missing.mp4")
        with self.assertRaises(IsADirectoryError):
            self.manager.mp4_to_mp3(self.root)
        other = self.root / "other.txt"
        other.touch()
        with self.assertRaises(ValueError):
            self.manager.mp4_to_mp3(other)
        with self.assertRaises(ValueError):
            self.manager.mp4_to_mp3(self.source, self.source)
        with self.assertRaises(ValueError):
            self.manager.mp4_to_mp3(self.source, self.root / "output.wav")
        for quality in (-1, 10, True, 2.5):
            with self.assertRaises(ValueError):
                self.manager.mp4_to_mp3(self.source, quality=quality)

    def test_startup_failure_is_reported(self):
        with patch("classes.managers.file_conversion_manager.subprocess.run", side_effect=OSError("Cannot execute")):
            with self.assertRaisesRegex(ConversionError, "Could not run FFmpeg"):
                self.manager.mp4_to_mp3(self.source)
        self.assertEqual(list(self.root.glob(".mp3-conversion-*")), [])


class FFmpegLookupTests(unittest.TestCase):
    def test_missing_ffmpeg(self):
        with patch("classes.managers.file_conversion_manager.shutil.which", return_value=None):
            with self.assertRaisesRegex(ConversionError, "FFmpeg was not found"):
                FileConversionManager()._get_ffmpeg()

    def test_directory_and_executable_locations(self):
        with TemporaryDirectory() as directory:
            executable = Path(directory) / "ffmpeg.exe"
            executable.touch()
            with patch("classes.managers.file_conversion_manager.shutil.which", return_value=str(executable)) as which:
                self.assertEqual(FileConversionManager(directory)._get_ffmpeg(), str(executable))
                which.assert_called_with(str(Path(directory) / "ffmpeg"))
                self.assertEqual(FileConversionManager(executable)._get_ffmpeg(), str(executable))
                which.assert_called_with(str(executable))


@unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is not installed on PATH")
class RealConversionTests(unittest.TestCase):
    def test_generated_mp4_converts_to_readable_mp3(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "sample.mp4"
            subprocess.run([
                shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin",
                "-f", "lavfi", "-i", "color=size=32x32:rate=10",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
                "-t", "0.5", "-c:v", "mpeg4", "-c:a", "aac",
                "-metadata", "title=Conversion test", str(source),
            ], check=True, capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            original = source.read_bytes()
            destination = FileConversionManager().mp4_to_mp3(source)
            audio = MP3(destination)
            self.assertGreater(audio.info.length, 0.4)
            self.assertEqual(str(audio.tags["TIT2"]), "Conversion test")
            self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
