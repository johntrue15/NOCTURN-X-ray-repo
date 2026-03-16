#!/usr/bin/env python3
"""
Unit tests for morphosource_api_download.py.

Validates record parsing, visibility checks, and download logic
without making actual network requests.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add the scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up a fake GITHUB_OUTPUT so gh_set_outputs doesn't error
os.environ["GITHUB_OUTPUT"] = os.path.join(tempfile.gettempdir(), "test_gh_output")

import morphosource_api_download as mod


# ---------- Sample record from parse_morphosource API output ----------
SAMPLE_RECORD = {
    "id": ["000840215"],
    "title": ["Surangular [Mesh] [CT]"],
    "media_type": ["Mesh"],
    "modality": ["MicroNanoXRayComputedTomography"],
    "device": ["Custom Make CT Scanner Assembled In-House"],
    "visibility": ["open"],
    "creator": ["Yann Rollot"],
    "physical_object_title": ["SMNK:pal:45053"],
    "physical_object_taxonomy_name": ["Allaeochelys crassesculpta"],
    "license": ["https://creativecommons.org/licenses/by-nc/4.0/"],
    "ark": ["ark:/87602/m4/840215"],
    "date_uploaded": ["2026-03-13T23:45:20Z"],
}


class TestParseRecord(unittest.TestCase):
    """Test JSON record parsing."""

    def test_parse_valid_json(self):
        record = mod.parse_record(json.dumps(SAMPLE_RECORD))
        self.assertIsInstance(record, dict)
        self.assertIn("id", record)

    def test_parse_invalid_json_raises(self):
        with self.assertRaises(SystemExit):
            mod.parse_record("not valid json {{{")

    def test_parse_empty_json_object(self):
        record = mod.parse_record("{}")
        self.assertEqual(record, {})


class TestExtractMediaId(unittest.TestCase):
    """Test media ID extraction from records."""

    def test_list_id(self):
        self.assertEqual(mod.extract_media_id({"id": ["000840215"]}), "000840215")

    def test_scalar_id(self):
        self.assertEqual(mod.extract_media_id({"id": "000840215"}), "000840215")

    def test_media_id_key(self):
        self.assertEqual(mod.extract_media_id({"media_id": "000999"}), "000999")

    def test_missing_id(self):
        self.assertEqual(mod.extract_media_id({}), "")


class TestExtractVisibility(unittest.TestCase):
    """Test visibility extraction."""

    def test_open_list(self):
        self.assertEqual(mod.extract_visibility({"visibility": ["open"]}), "open")

    def test_restricted_scalar(self):
        self.assertEqual(mod.extract_visibility({"visibility": "restricted"}), "restricted")

    def test_missing_visibility(self):
        self.assertEqual(mod.extract_visibility({}), "")


class TestExtractMetadata(unittest.TestCase):
    """Test metadata extraction from a full record."""

    def test_full_record(self):
        meta = mod.extract_metadata(SAMPLE_RECORD)
        self.assertEqual(meta["title"], "Surangular [Mesh] [CT]")
        self.assertEqual(meta["media_type"], "Mesh")
        self.assertEqual(meta["modality"], "MicroNanoXRayComputedTomography")
        self.assertEqual(meta["visibility"], "open")
        self.assertEqual(meta["creator"], "Yann Rollot")
        self.assertEqual(meta["physical_object_taxonomy_name"], "Allaeochelys crassesculpta")
        self.assertEqual(meta["license"], "https://creativecommons.org/licenses/by-nc/4.0/")
        self.assertEqual(meta["ark"], "ark:/87602/m4/840215")
        self.assertEqual(meta["date_uploaded"], "2026-03-13T23:45:20Z")

    def test_empty_record(self):
        meta = mod.extract_metadata({})
        self.assertEqual(meta["title"], "")
        self.assertEqual(meta["visibility"], "")


class TestFirstHelper(unittest.TestCase):
    """Test the _first helper."""

    def test_list(self):
        self.assertEqual(mod._first(["a", "b"]), "a")

    def test_empty_list(self):
        self.assertEqual(mod._first([]), "")

    def test_scalar(self):
        self.assertEqual(mod._first("hello"), "hello")

    def test_none(self):
        self.assertEqual(mod._first(None), "")


class TestHeaderFilename(unittest.TestCase):
    """Test Content-Disposition filename extraction."""

    def test_quoted_filename(self):
        self.assertEqual(
            mod.header_filename('attachment; filename="scan.zip"'),
            "scan.zip",
        )

    def test_unquoted_filename(self):
        self.assertEqual(
            mod.header_filename("attachment; filename=scan.zip"),
            "scan.zip",
        )

    def test_no_header(self):
        self.assertIsNone(mod.header_filename(None))

    def test_empty_header(self):
        self.assertIsNone(mod.header_filename(""))


class TestMainSkipsRestricted(unittest.TestCase):
    """Test that main() skips download for restricted media."""

    @patch.dict(os.environ, {
        "RECORD_JSON": json.dumps({
            "id": ["000123"],
            "title": ["Test"],
            "visibility": ["restricted"],
        }),
        "MEDIA_ID": "",
        "MORPHOSOURCE_API_KEY": "",
        "OUT_DIR": "/tmp/test_downloads",
    })
    def test_restricted_skips_download(self):
        """Should return without error when visibility is restricted."""
        # Ensure we don't make any network calls
        with patch("morphosource_api_download.requests.Session") as mock_sess:
            mod.main()
            # Session should not have been used (no network calls for restricted)
            mock_sess.return_value.__enter__.return_value.get.assert_not_called()


class TestMainOpenDownload(unittest.TestCase):
    """Test the full download path for open media."""

    @patch.dict(os.environ, {
        "RECORD_JSON": json.dumps(SAMPLE_RECORD),
        "MEDIA_ID": "",
        "MORPHOSOURCE_API_KEY": "test-key-123",
        "OUT_DIR": "",
    })
    def test_open_media_download_flow(self):
        """Verify the download flow for open media (mocked network)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["OUT_DIR"] = tmpdir

            mock_session = MagicMock()

            # Mock check_media_exists response
            check_resp = Mock()
            check_resp.status_code = 200
            check_resp.json.return_value = {"response": {"id": "000840215"}}

            # Mock request_download_url response
            download_url_resp = Mock()
            download_url_resp.status_code = 200
            download_url_resp.json.return_value = {"url": "https://example.com/signed/file.zip"}

            # Mock actual file download
            file_resp = Mock()
            file_resp.status_code = 200
            file_resp.headers = {"Content-Disposition": 'attachment; filename="media_000840215.zip"'}
            file_resp.iter_content = Mock(return_value=[b"fake file data"])
            file_resp.__enter__ = Mock(return_value=file_resp)
            file_resp.__exit__ = Mock(return_value=False)

            # Wire up session mock
            mock_session.get.side_effect = [check_resp, file_resp]
            mock_session.post.return_value = download_url_resp

            with patch("morphosource_api_download.requests.Session") as sess_cls:
                sess_cls.return_value.__enter__ = Mock(return_value=mock_session)
                sess_cls.return_value.__exit__ = Mock(return_value=False)

                mod.main()

            # Verify the download was attempted
            self.assertTrue(mock_session.post.called, "Should have POSTed for download URL")

            # Verify the payload contains the correct keys
            call_args = mock_session.post.call_args
            import json as _json
            posted_payload = _json.loads(call_args[1]["data"] if "data" in call_args[1] else call_args[0][1])
            self.assertIn("agreements_accepted", posted_payload, "Payload must use 'agreements_accepted'")
            self.assertTrue(posted_payload["agreements_accepted"], "agreements_accepted must be True")
            self.assertNotIn("agree_to_terms", posted_payload, "Should not use legacy 'agree_to_terms' key")
            self.assertGreaterEqual(len(posted_payload["use_statement"]), 50,
                                    "use_statement must be >= 50 characters")
            self.assertIn("use_categories", posted_payload, "Payload must include use_categories")

            downloaded = Path(tmpdir) / "media_000840215.zip"
            self.assertTrue(downloaded.exists(), f"Expected {downloaded} to exist")


class TestRequestDownloadUrlResponseParsing(unittest.TestCase):
    """Test that request_download_url correctly parses the API response format."""

    def _make_session(self, json_response):
        session = MagicMock()
        resp = Mock()
        resp.status_code = 200
        resp.json.return_value = json_response
        session.post.return_value = resp
        return session

    def test_official_api_format(self):
        """Parse response.media.download_url list (official API format)."""
        session = self._make_session({
            "response": {
                "media": {
                    "id": ["000840215"],
                    "download_url": ["https://example.com/signed/file.zip"],
                }
            }
        })
        url = mod.request_download_url(session, "key", "000840215")
        self.assertEqual(url, "https://example.com/signed/file.zip")

    def test_official_api_format_scalar(self):
        """Parse response.media.download_url as scalar string."""
        session = self._make_session({
            "response": {
                "media": {
                    "id": "000840215",
                    "download_url": "https://example.com/signed/file.zip",
                }
            }
        })
        url = mod.request_download_url(session, "key", "000840215")
        self.assertEqual(url, "https://example.com/signed/file.zip")

    def test_fallback_response_url(self):
        """Fallback: parse response.url."""
        session = self._make_session({
            "response": {"url": "https://example.com/fallback.zip"}
        })
        url = mod.request_download_url(session, "key", "000840215")
        self.assertEqual(url, "https://example.com/fallback.zip")

    def test_fallback_top_level_url(self):
        """Fallback: parse top-level url."""
        session = self._make_session({
            "url": "https://example.com/top-level.zip"
        })
        url = mod.request_download_url(session, "key", "000840215")
        self.assertEqual(url, "https://example.com/top-level.zip")

    def test_no_url_raises(self):
        """Raise SystemExit when no download URL is found."""
        session = self._make_session({"response": {"media": {}}})
        with self.assertRaises(SystemExit):
            mod.request_download_url(session, "key", "000840215")


if __name__ == "__main__":
    unittest.main()
