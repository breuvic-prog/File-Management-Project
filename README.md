# DownloaderProject

Download videos, playlists, or audio through a synchronous Python API or command line.

## Setup (Windows, Python 3.14)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Install **FFmpeg and ffprobe** using a build linked from
[FFmpeg's download page](https://ffmpeg.org/download.html). Both executables must be
on PATH, or supplied through `--ffmpeg-location C:\tools\ffmpeg\bin`.
The application checks for both before contacting a video site.

For YouTube, install a current supported **Deno or Node.js** runtime and put it on
PATH. Both are enabled in this application; the Python requirements include the
yt-dlp JavaScript support package. See
[yt-dlp's dependency documentation](https://github.com/yt-dlp/yt-dlp#dependencies).

## Command line

```powershell
.\.venv\Scripts\python.exe main.py "https://example.com/video" -o downloads
.\.venv\Scripts\python.exe main.py "https://example.com/video" --max-height 1080
.\.venv\Scripts\python.exe main.py "https://example.com/video" --audio
.\.venv\Scripts\python.exe main.py "https://example.com/video" --mp3
.\.venv\Scripts\python.exe main.py "https://example.com/playlist" --playlist
.\.venv\Scripts\python.exe main.py --help
```

Replace the example URLs with URLs supported by yt-dlp. Video downloads select the
best available streams within the optional height limit and merge without video
re-encoding. The output container follows the selected formats; MP4 is not forced.
`--audio` uses yt-dlp's best audio extraction; common codecs are copied without
re-encoding. `--mp3` explicitly requests MP3 conversion at high variable bitrate quality.

Source tags are embedded by default; use `--no-embed-metadata` to disable this.
The source upload date remains source metadata, not the filesystem creation date.
Your existing metadata classes can inspect or edit the finished files afterward.

Playlists require `--playlist` to download every entry. Otherwise a video URL with
a playlist downloads that video, and a pure playlist URL downloads its first item.
Downloads are sequential. A failure stops the request and prints any files already
completed. Exit codes: 0 success, 1 download/setup failure, 2 invalid arguments,
130 interrupted by Ctrl+C.

Partial downloads are retained; repeat the same command and destination to resume
when the source supports it. Names include the media ID and output profile to reduce
collisions. Existing downloads are reused; there is no force-overwrite option.
Re-running may repeat post-processing, including metadata embedding.

Progress distinguishes downloading from processing. Final output paths are printed
on stdout only after processing finishes; progress and failures go to stderr.

## Python API

```python
from classes.managers.download_manager import DownloadManager
from classes.object_relation_models.download_request import DownloadRequest

manager = DownloadManager()
request = DownloadRequest(
    url="https://example.com/video",
    destination="downloads",
    mode="audio",
    audio_format="mp3",
    ffmpeg_location=r"C:\tools\ffmpeg\bin",
)
result = manager.download(request, on_progress=lambda event: print(event.stage))
for file in result.files:
    print(file.path, file.title, file.upload_date)
    metadata = manager.metadata_for(file)
    print(metadata.size, metadata.duration)
```

`DownloadError.result` holds files completed before a failure. Callbacks run
synchronously; a future GUI should run the manager in a worker and forward events
to its UI thread. Callback exceptions propagate to the caller.

`DownloadRequest` holds user options, `YtDlpDownloader` handles site extraction and
processing, `DownloadManager` coordinates progress/results, and `DownloadResult`
contains final file paths and source information. Filesystem metadata remains in
`FileMetadata` and `MP3Metadata`. A separate generic HTTP backend and concurrent
queue can be added later behind the manager; they are not required for this first version.

## Convert an existing MP4 to MP3

```python
from classes.managers.file_conversion_manager import FileConversionManager

converter = FileConversionManager(ffmpeg_location=r"C:\tools\ffmpeg\bin")
mp3_path = converter.mp4_to_mp3("downloads/video.mp4")
# Or choose the output path and quality:
mp3_path = converter.mp4_to_mp3(
    "downloads/video.mp4", "music/song.mp3", quality=2, overwrite=False,
)
```

Omit `ffmpeg_location` to search PATH. This standalone conversion needs FFmpeg
with the `libmp3lame` encoder; it does not require ffprobe or a download URL.
The first audio stream is encoded to MP3; common text tags are copied, while
video, artwork, and additional audio streams are omitted. Quality ranges from
0 (highest) to 9 (lowest); the default is 2. The return value is an absolute `Path`.

The original MP4 is preserved. An existing output raises `FileExistsError` unless
`overwrite=True`. Conversion happens in a temporary directory beside the output,
so failed or cancelled conversions clean up their partial output and preserve any
existing MP3. FFmpeg errors, including missing audio or invalid media, raise
`ConversionError` with its diagnostic message.

## Tests

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Tests use temporary files, mocks, and a local HTTP server. They do not download
third-party videos. The local transfer test skips FFmpeg preflight and transfers
native MP3 data without conversion; actual FFmpeg transcoding and live-site
authentication are not covered by that test. The standalone converter also has an
integration test that generates a short MP4 and validates the resulting MP3; this
test runs when FFmpeg is on PATH and is otherwise skipped.
