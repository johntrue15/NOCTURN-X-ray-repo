#!/usr/bin/env python3
"""Unit tests for slicer_morph_analysis.py.

Validates file discovery, Slicer script generation, report writing, and
CLI argument parsing without requiring an actual 3D Slicer installation.
"""

import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up a fake GITHUB_OUTPUT so _gh_output doesn't error
os.environ["GITHUB_OUTPUT"] = os.path.join(tempfile.gettempdir(), "test_gh_output_slicer")

import slicer_morph_analysis as mod


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

    def test_find_vtk_file(self):
        """VTK is a Slicer-native format not supported by trimesh-based script."""
        with tempfile.TemporaryDirectory() as dl_dir, \
             tempfile.TemporaryDirectory() as tmp_root:
            vtk = Path(dl_dir) / "model.vtk"
            vtk.write_text("# vtk DataFile Version 3.0\n")
            found = mod.find_mesh_files(Path(dl_dir), Path(tmp_root))
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].name, "model.vtk")

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


class TestGenerateSlicerScript(unittest.TestCase):
    """Test Slicer Python script generation."""

    def test_script_contains_mesh_paths(self):
        mesh_paths = [Path("/tmp/mesh1.ply"), Path("/tmp/mesh2.stl")]
        output_dir = Path("/tmp/output")
        script = mod.generate_slicer_script(mesh_paths, output_dir, "test123")
        self.assertIn("/tmp/mesh1.ply", script)
        self.assertIn("/tmp/mesh2.stl", script)

    def test_script_contains_media_id(self):
        script = mod.generate_slicer_script(
            [Path("/tmp/test.ply")], Path("/tmp/out"), "M999"
        )
        self.assertIn("M999", script)

    def test_script_does_not_install_slicermorph(self):
        script = mod.generate_slicer_script(
            [Path("/tmp/test.ply")], Path("/tmp/out"), "test"
        )
        self.assertNotIn("downloadAndInstallExtensionByName", script)

    def test_script_contains_screenshot_capture(self):
        script = mod.generate_slicer_script(
            [Path("/tmp/test.ply")], Path("/tmp/out"), "test"
        )
        self.assertIn("screenshot", script.lower())
        self.assertIn("anterior", script)
        self.assertIn("posterior", script)

    def test_script_contains_metrics_collection(self):
        script = mod.generate_slicer_script(
            [Path("/tmp/test.ply")], Path("/tmp/out"), "test"
        )
        self.assertIn("GetNumberOfPoints", script)
        self.assertIn("GetNumberOfCells", script)
        self.assertIn("vtkMassProperties", script)

    def test_script_is_valid_python_syntax(self):
        """Verify the generated script compiles without syntax errors."""
        script = mod.generate_slicer_script(
            [Path("/tmp/test.ply")], Path("/tmp/out"), "test"
        )
        # The script references 'slicer' module which won't be available,
        # but we can at least check it compiles
        compile(script, "<slicer_script>", "exec")


class TestWriteAnalysisReport(unittest.TestCase):
    """Test Markdown report generation."""

    def test_report_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            metrics = {
                "media_id": "000123",
                "mesh_count": 1,
                "loaded_count": 1,
                "metrics": [{"path": "/tmp/model.ply", "n_points": 100, "n_cells": 50}],
                "screenshots": [],
            }
            report = mod.write_analysis_report(
                output_dir=output_dir,
                media_id="000123",
                metrics=metrics,
                screenshot_paths=[],
                slicer_stdout="Analysis complete.",
            )
            self.assertTrue(report.exists())
            content = report.read_text()
            self.assertIn("Media 000123", content)
            self.assertIn("n_points", content)
            self.assertIn("Analysis complete.", content)
            self.assertIn("slicermorph_analysis_000123.md", report.name)

    def test_report_includes_screenshots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            fake_ss = output_dir / "test_anterior.png"
            fake_ss.write_bytes(b"fake")
            report = mod.write_analysis_report(
                output_dir=output_dir,
                media_id="test",
                metrics={},
                screenshot_paths=[str(fake_ss)],
                slicer_stdout="",
            )
            content = report.read_text()
            self.assertIn("test_anterior", content)


class TestParseArgs(unittest.TestCase):
    """Test CLI argument parsing."""

    def test_required_args(self):
        args = mod.parse_args([
            "--download-dir", "/tmp/dl",
            "--slicer-executable", "/opt/slicer/Slicer",
        ])
        self.assertEqual(args.download_dir, Path("/tmp/dl"))
        self.assertEqual(args.slicer_executable, Path("/opt/slicer/Slicer"))
        self.assertEqual(args.output_dir, Path("artifacts"))
        self.assertEqual(args.media_id, "unknown")
        self.assertEqual(args.timeout, 300)
        self.assertEqual(args.max_meshes, 1)

    def test_all_args(self):
        args = mod.parse_args([
            "--download-dir", "/tmp/dl",
            "--output-dir", "/tmp/out",
            "--slicer-executable", "/opt/slicer/Slicer",
            "--media-id", "M123",
            "--timeout", "3600",
        ])
        self.assertEqual(args.download_dir, Path("/tmp/dl"))
        self.assertEqual(args.output_dir, Path("/tmp/out"))
        self.assertEqual(args.slicer_executable, Path("/opt/slicer/Slicer"))
        self.assertEqual(args.media_id, "M123")
        self.assertEqual(args.timeout, 3600)

    def test_max_meshes_arg(self):
        args = mod.parse_args([
            "--download-dir", "/tmp/dl",
            "--slicer-executable", "/opt/slicer/Slicer",
            "--max-meshes", "5",
        ])
        self.assertEqual(args.max_meshes, 5)

    def test_max_meshes_zero_unlimited(self):
        args = mod.parse_args([
            "--download-dir", "/tmp/dl",
            "--slicer-executable", "/opt/slicer/Slicer",
            "--max-meshes", "0",
        ])
        self.assertEqual(args.max_meshes, 0)

    def test_missing_required_fails(self):
        with self.assertRaises(SystemExit):
            mod.parse_args(["--download-dir", "/tmp/dl"])


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


class TestRunSlicerAnalysis(unittest.TestCase):
    """Test the Slicer execution wrapper (mocked)."""

    @patch("slicer_morph_analysis.subprocess.run")
    def test_slicer_called_with_correct_args(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="OK", stderr=""
        )
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            script_path = Path(f.name)

        slicer_bin = Path("/opt/slicer/Slicer")
        mod.run_slicer_analysis(slicer_bin, script_path)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        self.assertEqual(cmd[0], str(slicer_bin))
        self.assertIn("--no-splash", cmd)
        self.assertIn("--no-main-window", cmd)
        self.assertIn("--python-script", cmd)
        self.assertIn(str(script_path), cmd)
        os.unlink(script_path)


if __name__ == "__main__":
    unittest.main()
