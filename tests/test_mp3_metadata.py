import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mutagen import MutagenError
from mutagen.id3 import APIC, COMM, ID3, TIT2, TXXX
from mutagen.mp3 import HeaderNotFoundError

from classes.object_relation_models.mp3_metadata_class import MP3Metadata


class MP3MetadataTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "sample.mp3"
        # MPEG-1 Layer III frames: 128 kbps, 44.1 kHz, stereo.
        self.audio_data = (b"\xff\xfb\x90\x00" + bytes(413)) * 40
        self.path.write_bytes(self.audio_data)
        self.metadata = MP3Metadata(str(self.path))

    def test_tag_round_trips_and_removal(self):
        values = {
            "title": "Café 音楽",
            "artist": "Artist",
            "album": "Album",
            "album_artist": "Album artist",
            "genre": "Rock",
            "composer": "Composer",
            "year": 2024,
            "track_number": "3/12",
            "disc_number": "1/2",
            "comment": "A comment",
        }
        for name, value in values.items():
            with self.subTest(name=name):
                self.assertIsNone(getattr(self.metadata, name))
                setattr(self.metadata, name, value)
                reopened = MP3Metadata(str(self.path))
                self.assertEqual(getattr(reopened, name), value)
        for name, value in values.items():
            self.assertEqual(getattr(self.metadata, name), value)
        for name in values:
            setattr(self.metadata, name, None)
            self.assertIsNone(getattr(MP3Metadata(str(self.path)), name))
        self.assertTrue(self.path.read_bytes().endswith(self.audio_data))

    def test_removing_missing_tags_leaves_untagged_file_unchanged(self):
        self.metadata.title = None
        self.metadata.comment = None
        self.assertEqual(self.path.read_bytes(), self.audio_data)

    def test_unrelated_tags_and_audio_survive_edits(self):
        tags = ID3()
        tags.add(APIC(mime="image/png", type=3, desc="cover", data=b"image payload"))
        tags.add(TXXX(encoding=3, desc="custom", text=["keep me"]))
        tags.add(COMM(encoding=3, lang="fra", desc="", text=["bonjour"]))
        tags.add(COMM(encoding=3, lang="eng", desc="notes", text=["other comment"]))
        tags.save(self.path)
        self.metadata.title = "New title"
        self.metadata.comment = "Default comment"
        self.metadata.comment = None
        saved = ID3(self.path)
        self.assertEqual(saved["APIC:cover"].data, b"image payload")
        self.assertEqual(saved["TXXX:custom"].text, ["keep me"])
        self.assertEqual(saved["COMM::fra"].text, ["bonjour"])
        self.assertEqual(saved["COMM:notes:eng"].text, ["other comment"])
        self.assertTrue(self.path.read_bytes().endswith(self.audio_data))

    def test_audio_properties_are_read_only(self):
        self.assertAlmostEqual(self.metadata.duration, len(self.audio_data) * 8 / 128000)
        self.assertEqual(self.metadata.bitrate, 128000)
        self.assertEqual(self.metadata.sample_rate, 44100)
        self.assertEqual(self.metadata.channels, 2)
        for name in ("duration", "bitrate", "sample_rate", "channels"):
            with self.assertRaises(AttributeError):
                setattr(self.metadata, name, 1)

    def test_renames_and_external_edits_use_current_file(self):
        self.metadata.title = "Before"
        self.metadata.name = "renamed.mp3"
        self.metadata.title = "After"
        self.assertFalse(self.path.exists())
        renamed = Path(self.metadata.path)
        self.assertEqual(MP3Metadata(str(renamed)).title, "After")
        tags = ID3(renamed)
        tags.add(TIT2(encoding=3, text=["External edit"]))
        tags.save(renamed)
        self.assertEqual(self.metadata.title, "External edit")

    def test_invalid_year_does_not_modify_file(self):
        for year in (0, 10000, -1, True, "2024"):
            with self.assertRaises(ValueError):
                self.metadata.year = year
        self.assertEqual(self.path.read_bytes(), self.audio_data)

    def test_read_only_file_rejects_writes(self):
        self.metadata.is_read_only = True
        try:
            with self.assertRaises(MutagenError):
                self.metadata.title = "Cannot save"
            self.assertEqual(self.path.read_bytes(), self.audio_data)
        finally:
            self.metadata.is_read_only = False

    def test_missing_and_invalid_files_raise(self):
        missing = MP3Metadata(str(self.path.with_name("missing.mp3")))
        with self.assertRaises(MutagenError):
            _ = missing.title
        self.path.write_bytes(b"Not an MP3")
        with self.assertRaises(HeaderNotFoundError):
            _ = self.metadata.duration
        with self.assertRaises(HeaderNotFoundError):
            self.metadata.title = "Cannot tag"
        self.assertEqual(self.path.read_bytes(), b"Not an MP3")


if __name__ == "__main__":
    unittest.main()
