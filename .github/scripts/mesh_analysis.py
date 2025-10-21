#!/usr/bin/env python3
"""Analyse downloaded 3D mesh assets using trimesh."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import zipfile
from typing import Iterable, List

from tempfile import TemporaryDirectory

import trimesh

SUPPORTED_EXTENSIONS = {".ply", ".stl", ".obj", ".off", ".gltf", ".glb"}


class MeshAnalysisError(RuntimeError):
    """Raised when the mesh cannot be analysed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyse MorphoSource mesh downloads")
    parser.add_argument(
        "--download-dir",
        required=True,
        type=pathlib.Path,
        help="Directory containing mesh downloads (may include archives)",
    )
    parser.add_argument(
        "--output",
        default=pathlib.Path("artifacts/mesh_analysis.json"),
        type=pathlib.Path,
        help="Where to write the JSON analysis report",
    )
    return parser.parse_args()


def _expand_archive(path: pathlib.Path, workdir: pathlib.Path) -> Iterable[pathlib.Path]:
    target_dir = workdir / path.stem
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        archive.extractall(target_dir)
    return target_dir.rglob("*")


def _iter_candidate_paths(download_dir: pathlib.Path, temp_root: pathlib.Path) -> Iterable[pathlib.Path]:
    for item in download_dir.rglob("*"):
        if not item.is_file():
            continue
        suffix = item.suffix.lower()
        if suffix == ".zip":
            for extracted in _expand_archive(item, temp_root):
                if extracted.is_file() and extracted.suffix.lower() in SUPPORTED_EXTENSIONS:
                    yield extracted
        elif suffix in SUPPORTED_EXTENSIONS:
            yield item


def load_mesh(path: pathlib.Path) -> trimesh.Trimesh:
    try:
        mesh = trimesh.load(path, force="mesh")
    except Exception as exc:  # pragma: no cover - defensive guard around trimesh
        raise MeshAnalysisError(f"Failed to load mesh {path}: {exc}") from exc
    if mesh.is_empty:
        raise MeshAnalysisError(f"Mesh {path} contained no geometry")
    return mesh


def summarise_mesh(mesh: trimesh.Trimesh, path: pathlib.Path) -> dict:
    summary = {
        "path": str(path),
        "vertices": int(mesh.vertices.shape[0]) if mesh.vertices is not None else 0,
        "faces": int(mesh.faces.shape[0]) if mesh.faces is not None else 0,
        "is_watertight": bool(getattr(mesh, "is_watertight", False)),
        "surface_area": float(mesh.area) if hasattr(mesh, "area") else None,
        "volume": float(mesh.volume) if hasattr(mesh, "volume") else None,
        "bounding_box_extents": mesh.bounding_box.extents.tolist(),
        "bounding_box_volume": float(mesh.bounding_box.volume),
        "centroid": mesh.centroid.tolist(),
    }
    return summary


def main() -> None:
    args = parse_args()
    download_dir: pathlib.Path = args.download_dir
    if not download_dir.exists():
        print(f"::error::Download directory {download_dir} does not exist")
        sys.exit(1)

    with TemporaryDirectory(prefix="mesh_extract_") as temp_root_str:
        temp_root = pathlib.Path(temp_root_str)
        candidates: List[pathlib.Path] = list(_iter_candidate_paths(download_dir, temp_root))
        if not candidates:
            print("::error::No supported mesh files were located in the download directory")
            sys.exit(1)

        # Analyse the first mesh to keep execution time predictable; list all candidates
        target = candidates[0]
        try:
            mesh = load_mesh(target)
        except MeshAnalysisError as exc:
            print(f"::error::{exc}")
            sys.exit(1)

        summary = {
            "analysed_file": str(target),
            "available_files": [str(path) for path in candidates],
            "metrics": summarise_mesh(mesh, target),
        }

    output_path: pathlib.Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
