import contextlib
import functools
import io
import threading
import unittest
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError as YtDlpError, PostProcessingError

from classes.downloaders.yt_dlp_downloader import FinalFilePP, YtDlpDownloader
from classes.managers.download_manager import DownloadManager
from classes.object_relation_models.download_request import DownloadRequest
from classes.object_relation_models.download_result import DownloadError, DownloadedFile
from main import main


class DownloaderTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.request = DownloadRequest("https://example.com/video", self.root / "output")

    def test_invalid_requests(self):
        for settings in (
            {"url": "file:///private.txt"}, {"url": "not a URL"},
            {"mode": "invalid"}, {"audio_format": "wav"},
            {"audio_format": "mp3"}, {"max_height": 0}, {"max_height": True},
            {"mode": "audio", "max_height": 1080},
        ):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                DownloadRequest(**({"url": self.request.url} | settings))

    def test_video_selection_respects_height_and_defaults(self):
        request = DownloadRequest(self.request.url, self.root, max_height=720)
        options = YtDlpDownloader._options(request, lambda event: None)
        with YoutubeDL(options) as downloader:
            info = downloader.process_ie_result({
                "id": "clip", "title": "Clip",
                "formats": [
                    {"format_id": "audio", "url": "https://example.com/audio.m4a",
                     "ext": "m4a", "vcodec": "none", "acodec": "aac"},
                    {"format_id": "720", "url": "https://example.com/720.mp4",
                     "ext": "mp4", "height": 720, "vcodec": "h264", "acodec": "none"},
                    {"format_id": "1080", "url": "https://example.com/1080.mp4",
                     "ext": "mp4", "height": 1080, "vcodec": "h264", "acodec": "none"},
                ],
            }, download=False)
        self.assertEqual(info["height"], 720)
        self.assertEqual([item["format_id"] for item in info["requested_formats"]], ["720", "audio"])
        self.assertTrue(options["noplaylist"])
        self.assertEqual(options["playlist_items"], "1")
        self.assertTrue(options["continuedl"])
        self.assertFalse(options["nopart"])
        self.assertFalse(options["skip_unavailable_fragments"])
        self.assertFalse(options["updatetime"])

    def test_playlist_opt_in_and_mp3_conversion(self):
        request = DownloadRequest(self.request.url, self.root, mode="audio", audio_format="mp3", playlist=True)
        options = YtDlpDownloader._options(request, lambda event: None)
        self.assertFalse(options["noplaylist"])
        self.assertIsNone(options["playlist_items"])
        self.assertEqual(options["final_ext"], "mp3")
        self.assertEqual(options["postprocessors"][0]["preferredcodec"], "mp3")
        self.assertEqual(options["postprocessors"][1]["key"], "FFmpegMetadata")

    def test_pure_playlist_only_processes_first_item_by_default(self):
        for enabled, expected in ((False, 1), (True, 2)):
            with self.subTest(playlist=enabled):
                request = DownloadRequest(self.request.url, self.root, playlist=enabled)
                options = YtDlpDownloader._options(request, lambda event: None)
                entries = [
                    {"id": str(index), "title": str(index),
                     "url": f"https://example.com/{index}.mp4", "ext": "mp4"}
                    for index in range(2)
                ]
                with YoutubeDL(options) as downloader:
                    info = downloader.process_ie_result(
                        {"_type": "playlist", "id": "list", "entries": entries,
                         "extractor": "generic", "extractor_key": "Generic",
                         "webpage_url": self.request.url}, download=False,
                    )
                self.assertEqual(len(info["entries"]), expected)

    def test_hooks_do_not_report_completion_before_processing(self):
        events = []
        options = YtDlpDownloader._options(self.request, events.append)
        hook = options["progress_hooks"][0]
        hook({"status": "downloading", "downloaded_bytes": 123})
        hook({"status": "finished"})
        options["postprocessor_hooks"][0]({"status": "started", "postprocessor": "FFmpegMerger"})
        self.assertEqual([event.stage for event in events], ["downloading", "processing", "processing"])
        self.assertIsNone(events[0].total_bytes)

    def test_final_path_and_source_date(self):
        final = self.root / "converted.mp3"
        final.write_bytes(b"finished")
        files, events = [], []
        with YoutubeDL({"quiet": True}) as downloader:
            processor = FinalFilePP(downloader, self.request, files.append, events.append)
            processor.run({
                "filepath": str(final), "_filename": str(self.root / "original.webm"),
                "id": "clip", "title": "Clip", "upload_date": "20240102",
            })
        self.assertEqual(files[0].path, final.resolve())
        self.assertEqual(files[0].upload_date, date(2024, 1, 2))
        self.assertEqual(events[-1].stage, "saved")

    def test_missing_final_file_is_not_success(self):
        with YoutubeDL({"quiet": True}) as downloader:
            processor = FinalFilePP(downloader, self.request, Mock(), Mock())
            with self.assertRaises(PostProcessingError):
                processor.run({"filepath": str(self.root / "missing.mp4")})

    def test_partial_playlist_failure_reports_completed_items(self):
        file = DownloadedFile(self.root / "first.mp4", self.request.url, "1", "First")
        backend = Mock()

        def fail_after_one(request, emit, on_file):
            on_file(file)
            raise DownloadError("Second item failed")

        backend.download.side_effect = fail_after_one
        events = []
        with self.assertRaises(DownloadError) as caught:
            DownloadManager(backend).download(self.request, events.append)
        self.assertEqual(caught.exception.result.files, (file,))
        self.assertEqual(caught.exception.result.status, "failed")
        self.assertEqual(events[-1].stage, "failed")
        self.assertNotIn("completed", [event.stage for event in events])

    def test_empty_result_is_a_failure(self):
        with self.assertRaisesRegex(DownloadError, "No media files"):
            DownloadManager(Mock()).download(self.request)

    def test_missing_dependency_fails_before_network(self):
        with patch("classes.downloaders.yt_dlp_downloader.shutil.which", return_value=None), \
                patch("classes.downloaders.yt_dlp_downloader.YoutubeDL") as youtube:
            with self.assertRaisesRegex(DownloadError, "ffmpeg.*not found"):
                DownloadManager().download(self.request)
            youtube.assert_not_called()

    def test_backend_wraps_network_failure(self):
        with patch.object(YtDlpDownloader, "_check_dependencies"), \
                patch("classes.downloaders.yt_dlp_downloader.YoutubeDL") as youtube:
            youtube.return_value.__enter__.return_value.extract_info.side_effect = YtDlpError("Unavailable")
            with self.assertRaisesRegex(DownloadError, "Unavailable"):
                DownloadManager().download(self.request)

    def test_cli_exit_codes_and_validation(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main([self.request.url, "--audio", "--max-height", "1080"])
            self.assertEqual(caught.exception.code, 2)
            with patch("main.DownloadManager") as manager:
                manager.return_value.download.side_effect = DownloadError("Failure")
                self.assertEqual(main([self.request.url]), 1)
                manager.return_value.download.side_effect = KeyboardInterrupt
                self.assertEqual(main([self.request.url]), 130)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


class LocalDownloadTests(unittest.TestCase):
    def test_real_ytdlp_download_and_repeat_against_local_http(self):
        """Exercise extraction, HTTP transfer, and final hooks without an external site.

        This native MP3 fixture requires no conversion; only the dependency preflight
        is bypassed so this transport test also runs on machines without FFmpeg.
        """
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            audio = (b"\xff\xfb\x90\x00" + bytes(413)) * 40
            (source / "sample.mp3").write_bytes(audio)
            handler = functools.partial(QuietHandler, directory=str(source))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/sample.mp3"
                request = DownloadRequest(url, root / "downloads", mode="audio", embed_metadata=False)
                events = []
                with patch.object(YtDlpDownloader, "_check_dependencies"):
                    result = DownloadManager().download(request, events.append)
                    repeated = DownloadManager().download(request)
                self.assertEqual(result.status, "completed")
                self.assertEqual(len(result.files), 1)
                output = result.files[0].path
                self.assertEqual(output.read_bytes(), audio)
                self.assertEqual(repeated.files[0].path, output)
                self.assertEqual(events[-1].stage, "completed")
                self.assertIn("saved", [event.stage for event in events])
                self.assertFalse(list(output.parent.glob("*.part")))
                metadata = DownloadManager.metadata_for(result.files[0])
                self.assertEqual(metadata.sample_rate, 44100)
                # Simulate an interrupted transfer. This server ignores Range, so
                # yt-dlp must safely restart instead of appending duplicate bytes.
                output.unlink()
                partial = Path(str(output) + ".part")
                partial.write_bytes(audio[:600])
                with patch.object(YtDlpDownloader, "_check_dependencies"):
                    resumed = DownloadManager().download(request)
                self.assertEqual(resumed.files[0].path.read_bytes(), audio)
                self.assertFalse(partial.exists())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
