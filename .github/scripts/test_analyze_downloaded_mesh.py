#!/usr/bin/env python3
"""Unit tests for analyze_downloaded_mesh.py.

Validates file discovery, mesh rendering, report generation, and
GPT-4 Vision integration without making actual network requests.
"""

import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np

# Add the scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up a fake GITHUB_OUTPUT so _gh_output doesn't error
os.environ["GITHUB_OUTPUT"] = os.path.join(tempfile.gettempdir(), "test_gh_output_mesh")

import analyze_downloaded_mesh as mod


def _make_minimal_ply(path: Path) -> None:
    """Write a minimal valid PLY file with a simple triangle."""
    content = (
        "ply\n"
        "format ascii 1.0\n"
        "element vertex 3\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "element face 1\n"
        "property list uchar int vertex_indices\n"
        "end_header\n"
        "0 0 0\n"
        "1 0 0\n"
        "0 1 0\n"
        "3 0 1 2\n"
    )
    path.write_text(content, encoding="utf-8")


def _make_minimal_stl(path: Path) -> None:
    """Write a minimal valid ASCII STL file."""
    content = (
        "solid test\n"
        "  facet normal 0 0 1\n"
        "    outer loop\n"
        "      vertex 0 0 0\n"
        "      vertex 1 0 0\n"
        "      vertex 0 1 0\n"
        "    endloop\n"
        "  endfacet\n"
        "endsolid test\n"
    )
    path.write_text(content, encoding="utf-8")


class TestFindMeshFiles(unittest.TestCase):
    """Test mesh file discovery in download directories."""

    def test_find_ply_file(self):
        with tempfile.TemporaryDirectory() as dl_dir, \
             tempfile.TemporaryDirectory() as tmp_root:
            ply = Path(dl_dir) / "model.ply"
            _make_minimal_ply(ply)
            found = mod.find_mesh_files(Path(dl_dir), Path(tmp_root))
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].name, "model.ply")

    def test_find_stl_file(self):
        with tempfile.TemporaryDirectory() as dl_dir, \
             tempfile.TemporaryDirectory() as tmp_root:
            stl = Path(dl_dir) / "model.stl"
            _make_minimal_stl(stl)
            found = mod.find_mesh_files(Path(dl_dir), Path(tmp_root))
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].name, "model.stl")

    def test_find_mesh_in_subdirectory(self):
        with tempfile.TemporaryDirectory() as dl_dir, \
             tempfile.TemporaryDirectory() as tmp_root:
            sub = Path(dl_dir) / "subdir"
            sub.mkdir()
            ply = sub / "nested.ply"
            _make_minimal_ply(ply)
            found = mod.find_mesh_files(Path(dl_dir), Path(tmp_root))
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].name, "nested.ply")

    def test_find_mesh_inside_zip(self):
        with tempfile.TemporaryDirectory() as dl_dir, \
             tempfile.TemporaryDirectory() as tmp_root:
            # Create a ZIP containing a PLY
            ply_path = Path(tmp_root) / "inner.ply"
            _make_minimal_ply(ply_path)
            zip_path = Path(dl_dir) / "archive.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.write(ply_path, "inner.ply")

            found = mod.find_mesh_files(
                Path(dl_dir), Path(tempfile.mkdtemp())
            )
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].name, "inner.ply")

    def test_no_mesh_files(self):
        with tempfile.TemporaryDirectory() as dl_dir, \
             tempfile.TemporaryDirectory() as tmp_root:
            # Put a non-mesh file in the directory
            txt = Path(dl_dir) / "readme.txt"
            txt.write_text("not a mesh")
            found = mod.find_mesh_files(Path(dl_dir), Path(tmp_root))
            self.assertEqual(len(found), 0)

    def test_bad_zip_skipped(self):
        with tempfile.TemporaryDirectory() as dl_dir, \
             tempfile.TemporaryDirectory() as tmp_root:
            bad_zip = Path(dl_dir) / "corrupt.zip"
            bad_zip.write_bytes(b"this is not a zip")
            found = mod.find_mesh_files(Path(dl_dir), Path(tmp_root))
            self.assertEqual(len(found), 0)


class TestRenderMeshScreenshots(unittest.TestCase):
    """Test mesh rendering produces screenshots."""

    def test_render_produces_four_screenshots(self):
        import trimesh
        with tempfile.TemporaryDirectory() as out_dir:
            mesh = trimesh.Trimesh(
                vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
                faces=[[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]],
            )
            paths = mod.render_mesh_screenshots(mesh, Path(out_dir), "test123")
            self.assertEqual(len(paths), 4)
            for p in paths:
                self.assertTrue(p.exists(), f"Screenshot {p} should exist")
                self.assertGreater(p.stat().st_size, 0, f"Screenshot {p} should be non-empty")
                self.assertTrue(p.name.endswith(".png"))

    def test_screenshot_filenames_include_media_id(self):
        import trimesh
        with tempfile.TemporaryDirectory() as out_dir:
            mesh = trimesh.Trimesh(
                vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                faces=[[0, 1, 2]],
            )
            paths = mod.render_mesh_screenshots(mesh, Path(out_dir), "M999")
            for p in paths:
                self.assertIn("M999", p.name)


class TestSummariseMesh(unittest.TestCase):
    """Test mesh metrics summary."""

    def test_summary_keys(self):
        import trimesh
        mesh = trimesh.Trimesh(
            vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
            faces=[[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]],
        )
        summary = mod.summarise_mesh(mesh, Path("/tmp/test.ply"))
        self.assertIn("vertices", summary)
        self.assertIn("faces", summary)
        self.assertIn("is_watertight", summary)
        self.assertIn("surface_area", summary)
        self.assertIn("bounding_box_extents", summary)
        self.assertIn("centroid", summary)
        self.assertEqual(summary["vertices"], 4)
        self.assertEqual(summary["faces"], 4)


class TestEncodeImage(unittest.TestCase):
    """Test base64 image encoding."""

    def test_encode_roundtrip(self):
        import base64
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake png data")
            f.flush()
            encoded = mod.encode_image(Path(f.name))
            decoded = base64.b64decode(encoded)
            self.assertEqual(decoded, b"fake png data")
            os.unlink(f.name)


class TestAnalyzeWithGPT4Vision(unittest.TestCase):
    """Test GPT-4 Vision integration (mocked)."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    def test_missing_api_key(self):
        result = mod.analyze_with_gpt4_vision([], {})
        self.assertIn("OPENAI_API_KEY is missing", result)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_successful_analysis(self):
        """Verify that a mocked OpenAI call produces expected output."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is a detailed analysis."

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake screenshot
            fake_img = Path(tmpdir) / "test.png"
            fake_img.write_bytes(b"\x89PNG\r\n\x1a\nfake")

            # Patch OpenAI at the import level inside the function
            mock_openai_module = MagicMock()
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai_module.OpenAI.return_value = mock_client

            with patch.dict("sys.modules", {"openai": mock_openai_module}):
                result = mod.analyze_with_gpt4_vision(
                    [fake_img], {"vertices": 100, "faces": 200}
                )
                self.assertEqual(result, "This is a detailed analysis.")
                mock_client.chat.completions.create.assert_called_once()

                # Verify model used matches ct_image_to_text.py convention
                call_kwargs = mock_client.chat.completions.create.call_args
                self.assertEqual(call_kwargs.kwargs.get("model") or call_kwargs[1].get("model"), "gpt-4o-mini")


class TestWriteAnalysisReport(unittest.TestCase):
    """Test Markdown report generation."""

    def test_report_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            fake_screenshots = [
                output_dir / "test_Default_Yplus_Up.png",
                output_dir / "test_Forward_90_Z-_Up.png",
            ]
            for p in fake_screenshots:
                p.write_bytes(b"fake")

            report = mod.write_analysis_report(
                output_dir=output_dir,
                media_id="000123",
                mesh_path=Path("/tmp/model.ply"),
                mesh_summary={"vertices": 100, "faces": 50},
                screenshot_paths=fake_screenshots,
                analysis_text="Sample analysis text.",
            )
            self.assertTrue(report.exists())
            content = report.read_text()
            self.assertIn("Media 000123", content)
            self.assertIn("vertices", content)
            self.assertIn("Sample analysis text.", content)
            self.assertIn("mesh_analysis_000123.md", report.name)


class TestGhOutput(unittest.TestCase):
    """Test GitHub Actions output helper."""

    def test_single_line_output(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            output_path = f.name

        with patch.dict(os.environ, {"GITHUB_OUTPUT": output_path}):
            mod._gh_output("test_key", "test_value")

        with open(output_path) as f:
            content = f.read()
        self.assertIn("test_key=test_value", content)
        os.unlink(output_path)

    def test_multiline_output(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            output_path = f.name

        with patch.dict(os.environ, {"GITHUB_OUTPUT": output_path}):
            mod._gh_output("multi", "line1\nline2")

        with open(output_path) as f:
            content = f.read()
        self.assertIn("multi<<EOF", content)
        self.assertIn("line1\nline2", content)
        os.unlink(output_path)


if __name__ == "__main__":
    unittest.main()
