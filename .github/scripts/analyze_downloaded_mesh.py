#!/usr/bin/env python3
"""Analyze downloaded MorphoSource mesh files (.ply, .stl, .obj, etc.).

Extracts archives, renders screenshots from multiple viewpoints using
trimesh + matplotlib, and sends them to the ChatGPT Vision API for
analysis — mirroring the pipeline in combined_ct_images_to_text.yml.

Usage (inside GitHub Actions):
    python .github/scripts/analyze_downloaded_mesh.py \
        --download-dir downloads \
        --output-dir artifacts \
        --media-id 000840215

Environment variables:
    OPENAI_API_KEY  – Required for GPT-4 Vision analysis.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import pathlib
import sys
import zipfile
from tempfile import TemporaryDirectory
from typing import Dict, Iterable, List, Optional

import matplotlib
matplotlib.use("Agg")  # headless backend — must be set before pyplot import
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 — registers 3-D projection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

import trimesh

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".ply", ".stl", ".obj", ".off", ".gltf", ".glb"}

# Four viewpoints matching the orientations used in ct_image_to_text.py
VIEWPOINTS: List[Dict[str, object]] = [
    {"name": "Default_Yplus_Up",     "elev": 30,  "azim": -60,  "label": "Default (Y+ Up)"},
    {"name": "Upside_Down_Y-_Up",    "elev": -30, "azim": -60,  "label": "Upside Down (Y- Up)"},
    {"name": "Forward_90_Z-_Up",     "elev": 0,   "azim": 0,    "label": "Forward 90° (Z- Up)"},
    {"name": "Back_90_Zplus_Up",     "elev": 0,   "azim": 180,  "label": "Back 90° (Z+ Up)"},
]


# ─── CLI ──────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Render & analyse downloaded meshes")
    p.add_argument("--download-dir", required=True, type=pathlib.Path,
                   help="Directory containing downloaded mesh files or archives")
    p.add_argument("--output-dir", default=pathlib.Path("artifacts"),
                   type=pathlib.Path, help="Where to write screenshots and report")
    p.add_argument("--media-id", default="unknown",
                   help="MorphoSource media ID (used in filenames)")
    return p.parse_args()


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


# ─── Mesh rendering ──────────────────────────────────────────────────────

def _load_mesh(path: pathlib.Path) -> trimesh.Trimesh:
    try:
        mesh = trimesh.load(path, force="mesh")
    except Exception as exc:
        raise RuntimeError(f"Failed to load mesh {path}: {exc}") from exc
    if mesh.is_empty:
        raise RuntimeError(f"Mesh {path} contained no geometry")
    return mesh


def render_mesh_screenshots(
    mesh: trimesh.Trimesh,
    output_dir: pathlib.Path,
    media_id: str,
) -> List[pathlib.Path]:
    """Render *mesh* from four viewpoints and save as PNG screenshots.

    Returns a list of screenshot file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    vertices = mesh.vertices
    faces = mesh.faces

    # Centre the mesh at the origin for consistent rendering
    centroid = vertices.mean(axis=0)
    vertices_centred = vertices - centroid

    screenshot_paths: List[pathlib.Path] = []

    for vp in VIEWPOINTS:
        fig = plt.figure(figsize=(12, 10), dpi=100)
        ax = fig.add_subplot(111, projection="3d")

        # Build face polygons
        polys = vertices_centred[faces]
        collection = Poly3DCollection(
            polys, alpha=0.85, edgecolor="darkgray", linewidths=0.15
        )
        collection.set_facecolor("steelblue")
        ax.add_collection3d(collection)

        # Set axis limits based on mesh extents
        max_range = np.abs(vertices_centred).max() * 1.1
        ax.set_xlim(-max_range, max_range)
        ax.set_ylim(-max_range, max_range)
        ax.set_zlim(-max_range, max_range)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
        ax.set_title(f"{vp['label']}  —  Media {media_id}")
        ax.view_init(elev=vp["elev"], azim=vp["azim"])

        fname = f"{media_id}_{vp['name']}.png"
        dest = output_dir / fname
        fig.savefig(str(dest), bbox_inches="tight", pad_inches=0.3)
        plt.close(fig)
        screenshot_paths.append(dest)
        logger.info("Saved screenshot: %s", dest)

    return screenshot_paths


# ─── Mesh metrics ─────────────────────────────────────────────────────────

def summarise_mesh(mesh: trimesh.Trimesh, path: pathlib.Path) -> Dict[str, object]:
    return {
        "path": str(path),
        "vertices": int(mesh.vertices.shape[0]),
        "faces": int(mesh.faces.shape[0]),
        "is_watertight": bool(getattr(mesh, "is_watertight", False)),
        "surface_area": float(mesh.area) if hasattr(mesh, "area") else None,
        "volume": float(mesh.volume) if hasattr(mesh, "volume") else None,
        "bounding_box_extents": mesh.bounding_box.extents.tolist(),
        "centroid": mesh.centroid.tolist(),
    }


# ─── GPT-4 Vision analysis ───────────────────────────────────────────────

def encode_image(path: pathlib.Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def analyze_with_gpt4_vision(
    screenshot_paths: List[pathlib.Path],
    mesh_summary: Dict[str, object],
) -> str:
    """Send mesh screenshots to the ChatGPT Vision API for analysis.

    Mirrors the approach in ct_image_to_text.py.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return "Error: OPENAI_API_KEY is missing — skipping GPT-4 Vision analysis."

    try:
        from openai import OpenAI
    except ImportError:
        return "Error: openai library is not installed — skipping GPT-4 Vision analysis."

    client = OpenAI()

    # Build multi-modal content list
    content: List[Dict[str, object]] = [
        {
            "type": "text",
            "text": (
                "You are analyzing 3D mesh data downloaded from MorphoSource.org. "
                "The images show the same specimen rendered from four different "
                "orientations (Default Y+ Up, Upside Down Y- Up, Forward 90° Z- Up, "
                "Back 90° Z+ Up). "
                f"\n\nMesh metrics:\n```json\n{json.dumps(mesh_summary, indent=2)}\n```\n\n"
                "Please provide a detailed analysis of:\n"
                "1. The structural characteristics and overall morphology\n"
                "2. Surface features and any notable topology\n"
                "3. Potential specimen type (bone, fossil, artifact, etc.)\n"
                "4. Any notable features or anomalies visible across views"
            ),
        }
    ]

    for img_path in screenshot_paths:
        try:
            b64 = encode_image(img_path)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })
            logger.info("Added image %s to analysis batch", img_path.name)
        except Exception as exc:
            logger.error("Error encoding image %s: %s", img_path, exc)

    try:
        logger.info("Sending images to GPT-4 Vision API …")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": content}],
            max_tokens=1000,
        )
        logger.info("GPT-4 Vision response received.")
        return response.choices[0].message.content
    except Exception as exc:
        error_msg = f"Error analysing images: {exc}"
        logger.error(error_msg)
        return error_msg


# ─── Report generation ────────────────────────────────────────────────────

def write_analysis_report(
    output_dir: pathlib.Path,
    media_id: str,
    mesh_path: pathlib.Path,
    mesh_summary: Dict[str, object],
    screenshot_paths: List[pathlib.Path],
    analysis_text: str,
) -> pathlib.Path:
    """Write a Markdown analysis report."""
    report_path = output_dir / f"mesh_analysis_{media_id}.md"
    screenshots_section = "\n".join(
        f"![{p.stem}]({p.name})" for p in screenshot_paths
    )
    report = (
        f"# Mesh Analysis — Media {media_id}\n\n"
        f"**Source file**: `{mesh_path}`\n\n"
        f"## Mesh Metrics\n\n"
        f"```json\n{json.dumps(mesh_summary, indent=2)}\n```\n\n"
        f"## Screenshots\n\n{screenshots_section}\n\n"
        f"## GPT-4 Vision Analysis\n\n{analysis_text}\n"
    )
    report_path.write_text(report, encoding="utf-8")
    logger.info("Analysis report written to %s", report_path)
    return report_path


# ─── Entrypoint ───────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    download_dir: pathlib.Path = args.download_dir
    output_dir: pathlib.Path = args.output_dir
    media_id: str = args.media_id

    if not download_dir.exists():
        logger.error("Download directory %s does not exist", download_dir)
        sys.exit(1)

    with TemporaryDirectory(prefix="mesh_extract_") as temp_root_str:
        temp_root = pathlib.Path(temp_root_str)
        mesh_files = find_mesh_files(download_dir, temp_root)

        if not mesh_files:
            logger.warning("No supported mesh files found in %s — nothing to analyse.", download_dir)
            # Set output so the workflow knows analysis was skipped
            _gh_output("analysis_skipped", "true")
            _gh_output("skip_reason", "No supported mesh files found in download directory")
            return

        logger.info("Found %d mesh file(s): %s", len(mesh_files), mesh_files)

        # Analyse the first mesh (consistent with existing mesh_analysis.py behaviour)
        target = mesh_files[0]
        logger.info("Loading mesh: %s", target)
        try:
            mesh = _load_mesh(target)
        except RuntimeError as exc:
            logger.error("Failed to load mesh: %s", exc)
            _gh_output("analysis_skipped", "true")
            _gh_output("skip_reason", str(exc))
            sys.exit(1)

        mesh_summary = summarise_mesh(mesh, target)
        logger.info("Mesh metrics: %s", json.dumps(mesh_summary, indent=2))

        # Render screenshots from multiple viewpoints
        logger.info("Rendering screenshots …")
        screenshot_paths = render_mesh_screenshots(mesh, output_dir, media_id)
        logger.info("Captured %d screenshots", len(screenshot_paths))

        # Send to GPT-4 Vision
        logger.info("Starting GPT-4 Vision analysis …")
        analysis_text = analyze_with_gpt4_vision(screenshot_paths, mesh_summary)
        logger.info("Analysis complete.")

        # Write report
        report_path = write_analysis_report(
            output_dir, media_id, target, mesh_summary, screenshot_paths, analysis_text,
        )

    # Emit GitHub Actions outputs
    _gh_output("analysis_skipped", "false")
    _gh_output("analysis_report", str(report_path))
    _gh_output("screenshots_count", str(len(screenshot_paths)))

    print(f"\n{'='*60}")
    print(f"Analysis complete for media {media_id}")
    print(f"Report: {report_path}")
    print(f"Screenshots: {len(screenshot_paths)}")
    print(f"{'='*60}\n")
    print(analysis_text)


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
