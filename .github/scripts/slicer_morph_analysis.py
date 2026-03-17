#!/usr/bin/env python3
"""Run SlicerMorph analysis on downloaded mesh files in headless 3D Slicer.

Discovers mesh files (.ply, .stl, .obj, .vtk, .vtp, .gltf, .glb) in the
download directory, generates a Slicer Python script to load each one,
install SlicerMorph, collect mesh metrics, capture screenshots, and write
an analysis report.

Usage (inside GitHub Actions):
    python .github/scripts/slicer_morph_analysis.py \
        --download-dir downloads \
        --output-dir artifacts \
        --slicer-executable /opt/slicer/Slicer \
        --media-id 000840215

Environment variables:
    OPENAI_API_KEY  – Optional, for GPT-4 Vision analysis of screenshots.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import pathlib
import subprocess
import sys
import textwrap
import zipfile
from tempfile import TemporaryDirectory
from typing import Dict, Iterable, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".ply", ".stl", ".obj", ".vtk", ".vtp", ".off", ".gltf", ".glb"}


# ─── CLI ──────────────────────────────────────────────────────────────────

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run SlicerMorph analysis on mesh files")
    p.add_argument("--download-dir", required=True, type=pathlib.Path,
                   help="Directory containing downloaded mesh files or archives")
    p.add_argument("--output-dir", default=pathlib.Path("artifacts"),
                   type=pathlib.Path, help="Where to write screenshots and report")
    p.add_argument("--slicer-executable", required=True, type=pathlib.Path,
                   help="Path to the 3D Slicer executable")
    p.add_argument("--media-id", default="unknown",
                   help="MorphoSource media ID (used in filenames)")
    p.add_argument("--timeout", type=int, default=1800,
                   help="Timeout in seconds for the Slicer subprocess (default: 1800)")
    return p.parse_args(argv)


# ─── File discovery ───────────────────────────────────────────────────────

def _expand_archive(path: pathlib.Path, workdir: pathlib.Path) -> Iterable[pathlib.Path]:
    """Safely extract a ZIP archive into *workdir* and yield contained files."""
    target_dir = workdir / path.stem
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        archive.extractall(target_dir)
    return target_dir.rglob("*")


def find_mesh_files(
    download_dir: pathlib.Path,
    temp_root: pathlib.Path,
) -> List[pathlib.Path]:
    """Return a list of mesh file paths, extracting ZIPs when necessary."""
    results: List[pathlib.Path] = []
    for item in download_dir.rglob("*"):
        if not item.is_file():
            continue
        suffix = item.suffix.lower()
        if suffix == ".zip":
            try:
                for extracted in _expand_archive(item, temp_root):
                    if extracted.is_file() and extracted.suffix.lower() in SUPPORTED_EXTENSIONS:
                        results.append(extracted)
            except zipfile.BadZipFile:
                logger.warning("Skipping bad ZIP file: %s", item)
        elif suffix in SUPPORTED_EXTENSIONS:
            results.append(item)
    return results


# ─── Slicer script generation ────────────────────────────────────────────

def generate_slicer_script(
    mesh_paths: List[pathlib.Path],
    output_dir: pathlib.Path,
    media_id: str,
) -> str:
    """Return a Python script string for 3D Slicer to execute.

    The script:
    1. Installs SlicerMorph extension (if not already installed).
    2. Loads each mesh file into the scene.
    3. Collects mesh metrics (vertices, faces, surface area, volume, bounds).
    4. Captures screenshots from multiple viewpoints.
    5. Writes a JSON metrics file.
    """
    mesh_paths_json = json.dumps([str(p) for p in mesh_paths])
    output_dir_str = str(output_dir)

    return textwrap.dedent(f"""\
        #
        # SlicerMorph analysis script — executed inside headless 3D Slicer
        #
        import json, os, sys, time

        output_dir = {output_dir_str!r}
        media_id = {media_id!r}
        mesh_paths = {mesh_paths_json}

        os.makedirs(output_dir, exist_ok=True)

        # ── Install SlicerMorph extension ──────────────────────────────────
        em = slicer.app.extensionsManagerModel()
        if em is not None:
            slicer.app.processEvents()
            installed = [em.extensionMetadataByName(em.installedExtensions[i]).get("extensionName", "")
                         for i in range(em.installedExtensionsCount)]
            if "SlicerMorph" not in installed:
                print("Installing SlicerMorph extension...")
                md = em.retrieveExtensionMetadataByName("SlicerMorph")
                if md and md.get("extension_id"):
                    em.downloadAndInstallExtensionByName("SlicerMorph")
                    slicer.app.processEvents()
                    time.sleep(5)
                    slicer.app.processEvents()
                    print("SlicerMorph installation requested.")
                else:
                    print("WARNING: SlicerMorph metadata not found in extension index.")
            else:
                print("SlicerMorph is already installed.")
        else:
            print("WARNING: Extension manager not available.")

        # ── Load mesh files ────────────────────────────────────────────────
        all_metrics = []
        loaded_nodes = []
        for mesh_path in mesh_paths:
            print(f"Loading mesh: {{mesh_path}}")
            try:
                node = slicer.util.loadModel(mesh_path)
                if node is None:
                    print(f"WARNING: Failed to load {{mesh_path}}")
                    continue
                loaded_nodes.append((mesh_path, node))

                # Collect mesh metrics
                pd = node.GetPolyData()
                metrics = {{
                    "path": mesh_path,
                    "n_points": pd.GetNumberOfPoints() if pd else 0,
                    "n_cells": pd.GetNumberOfCells() if pd else 0,
                    "n_polys": pd.GetNumberOfPolys() if pd else 0,
                }}

                # Compute bounds
                if pd and pd.GetNumberOfPoints() > 0:
                    bounds = [0.0] * 6
                    pd.GetBounds(bounds)
                    metrics["bounds"] = bounds
                    metrics["extent_x"] = bounds[1] - bounds[0]
                    metrics["extent_y"] = bounds[3] - bounds[2]
                    metrics["extent_z"] = bounds[5] - bounds[4]

                    # Compute surface area and volume using vtkMassProperties
                    try:
                        import vtk
                        tri_filter = vtk.vtkTriangleFilter()
                        tri_filter.SetInputData(pd)
                        tri_filter.Update()
                        mass = vtk.vtkMassProperties()
                        mass.SetInputConnection(tri_filter.GetOutputPort())
                        mass.Update()
                        metrics["surface_area"] = mass.GetSurfaceArea()
                        metrics["volume"] = mass.GetVolume()
                    except Exception as e:
                        print(f"WARNING: Could not compute mass properties: {{e}}")

                all_metrics.append(metrics)
                print(f"  Loaded: {{metrics.get('n_points', 0)}} points, "
                      f"{{metrics.get('n_cells', 0)}} cells")
            except Exception as e:
                print(f"ERROR loading {{mesh_path}}: {{e}}")
                all_metrics.append({{"path": mesh_path, "error": str(e)}})

        # ── Capture screenshots from multiple viewpoints ───────────────────
        screenshot_paths = []
        viewpoints = [
            ("anterior", {{}}),
            ("posterior", {{"pitch": 180}}),
            ("superior", {{"pitch": -90}}),
            ("lateral_right", {{"yaw": 90}}),
        ]

        if loaded_nodes:
            lm = slicer.app.layoutManager()
            if lm is not None:
                lm.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)
                slicer.app.processEvents()

                view_widget = lm.threeDWidget(0)
                view_node = view_widget.mrmlThreeDViewNode()
                view = view_widget.threeDView()
                renderer = view.renderWindow().GetRenderers().GetFirstRenderer()
                camera = renderer.GetActiveCamera()

                # Reset view to show all content
                view.resetFocalPoint()
                renderer.ResetCamera()
                slicer.app.processEvents()

                for vp_name, transforms in viewpoints:
                    # Reset camera
                    view.resetFocalPoint()
                    renderer.ResetCamera()

                    if "pitch" in transforms:
                        camera.Elevation(transforms["pitch"])
                    if "yaw" in transforms:
                        camera.Azimuth(transforms["yaw"])

                    renderer.ResetCameraClippingRange()
                    slicer.app.processEvents()
                    view.forceRender()
                    slicer.app.processEvents()

                    fname = f"{{media_id}}_slicermorph_{{vp_name}}.png"
                    fpath = os.path.join(output_dir, fname)
                    view.grab().save(fpath)
                    screenshot_paths.append(fpath)
                    print(f"  Screenshot saved: {{fpath}}")

        # ── Write metrics JSON ─────────────────────────────────────────────
        results = {{
            "media_id": media_id,
            "mesh_count": len(mesh_paths),
            "loaded_count": len(loaded_nodes),
            "metrics": all_metrics,
            "screenshots": screenshot_paths,
        }}
        metrics_path = os.path.join(output_dir, f"slicermorph_metrics_{{media_id}}.json")
        with open(metrics_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Metrics written to: {{metrics_path}}")

        print("SlicerMorph analysis complete.")
        sys.exit(0)
    """)


# ─── Run Slicer ──────────────────────────────────────────────────────────

def run_slicer_analysis(
    slicer_executable: pathlib.Path,
    script_path: pathlib.Path,
    timeout: int = 600,
) -> subprocess.CompletedProcess:
    """Execute 3D Slicer in headless mode with the given Python script."""
    cmd = [
        str(slicer_executable),
        "--no-splash",
        "--no-main-window",
        "--python-script", str(script_path),
    ]
    logger.info("Running Slicer: %s", " ".join(cmd))

    env = os.environ.copy()
    env["DISPLAY"] = os.environ.get("DISPLAY", ":99")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    logger.info("Slicer stdout:\n%s", result.stdout)
    if result.stderr:
        logger.warning("Slicer stderr:\n%s", result.stderr)
    return result


# ─── Report generation ────────────────────────────────────────────────────

def write_analysis_report(
    output_dir: pathlib.Path,
    media_id: str,
    metrics: Dict,
    screenshot_paths: List[str],
    slicer_stdout: str,
) -> pathlib.Path:
    """Write a Markdown analysis report for SlicerMorph results."""
    report_path = output_dir / f"slicermorph_analysis_{media_id}.md"

    screenshots_section = "\n".join(
        f"![{pathlib.Path(p).stem}]({pathlib.Path(p).name})" for p in screenshot_paths
    )

    report = (
        f"# SlicerMorph Analysis — Media {media_id}\n\n"
        f"## Mesh Metrics\n\n"
        f"```json\n{json.dumps(metrics, indent=2)}\n```\n\n"
        f"## Screenshots\n\n{screenshots_section}\n\n"
        f"## Slicer Output\n\n```\n{slicer_stdout}\n```\n"
    )
    report_path.write_text(report, encoding="utf-8")
    logger.info("Analysis report written to %s", report_path)
    return report_path


# ─── Entrypoint ───────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    download_dir: pathlib.Path = args.download_dir
    output_dir: pathlib.Path = args.output_dir
    slicer_executable: pathlib.Path = args.slicer_executable
    media_id: str = args.media_id
    timeout: int = args.timeout

    if not download_dir.exists():
        logger.error("Download directory %s does not exist", download_dir)
        sys.exit(1)

    if not slicer_executable.exists():
        logger.error("Slicer executable %s not found", slicer_executable)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="slicer_mesh_extract_") as temp_root_str:
        temp_root = pathlib.Path(temp_root_str)
        mesh_files = find_mesh_files(download_dir, temp_root)

        if not mesh_files:
            logger.warning("No supported mesh files found in %s — nothing to analyze.", download_dir)
            _gh_output("analysis_skipped", "true")
            _gh_output("skip_reason", "No supported mesh files found in download directory")
            return

        logger.info("Found %d mesh file(s): %s", len(mesh_files), mesh_files)

        # Generate the Slicer Python script
        slicer_script_content = generate_slicer_script(mesh_files, output_dir, media_id)
        slicer_script_path = temp_root / "slicermorph_analysis.py"
        slicer_script_path.write_text(slicer_script_content, encoding="utf-8")
        logger.info("Slicer script written to %s", slicer_script_path)

        # Run Slicer
        try:
            result = run_slicer_analysis(slicer_executable, slicer_script_path, timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.error("Slicer analysis timed out")
            _gh_output("analysis_skipped", "true")
            _gh_output("skip_reason", "Slicer analysis timed out")
            sys.exit(1)

        if result.returncode != 0:
            logger.error("Slicer exited with code %d", result.returncode)
            _gh_output("analysis_skipped", "true")
            _gh_output("skip_reason", f"Slicer exited with code {result.returncode}")

        # Read metrics JSON if produced
        metrics_path = output_dir / f"slicermorph_metrics_{media_id}.json"
        metrics = {}
        screenshot_paths: List[str] = []
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            screenshot_paths = metrics.get("screenshots", [])
            logger.info("Loaded metrics: %d mesh(es) analyzed", metrics.get("loaded_count", 0))

        # Write report
        report_path = write_analysis_report(
            output_dir, media_id, metrics, screenshot_paths, result.stdout,
        )

    # Emit GitHub Actions outputs
    _gh_output("analysis_skipped", "false")
    _gh_output("analysis_report", str(report_path))
    _gh_output("screenshots_count", str(len(screenshot_paths)))

    print(f"\n{'='*60}")
    print(f"SlicerMorph analysis complete for media {media_id}")
    print(f"Report: {report_path}")
    print(f"Screenshots: {len(screenshot_paths)}")
    print(f"{'='*60}\n")


def _gh_output(key: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        if "\n" in value:
            fh.write(f"{key}<<EOF\n{value}\nEOF\n")
        else:
            fh.write(f"{key}={value}\n")


if __name__ == "__main__":
    main()
