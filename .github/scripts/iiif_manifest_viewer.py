#!/usr/bin/env python3
"""Render a representative IIIF image and record metadata.

The dimension test workflow now analyses 2D media by downloading the IIIF
manifest during the media selection phase.  This helper script consumes that
manifest, resolves a displayable image using open IIIF conventions, and uses
Pillow (an open-source imaging library) to open and save the image locally.  The
resulting PNG artefact gives us a lightweight preview without relying on a
proprietary browser engine.

The script emits a JSON side-car file containing useful diagnostic information
such as the original image service URL and the pixel dimensions reported by
Pillow.  The GitHub Actions workflow can upload both files as artefacts so the
results are easy to inspect after a run.
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import sys
import urllib.parse
from typing import Any, Dict, Iterable, Iterator, Optional

import requests
from PIL import Image


class IIIFImageResolutionError(RuntimeError):
    """Raised when an image resource cannot be resolved from a manifest."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render an IIIF image locally")
    parser.add_argument(
        "--manifest",
        required=True,
        type=pathlib.Path,
        help="Path to the IIIF manifest JSON file",
    )
    parser.add_argument(
        "--output-dir",
        default=pathlib.Path("artifacts"),
        type=pathlib.Path,
        help="Directory where the rendered image and summary will be written",
    )
    parser.add_argument(
        "--image-name",
        default="iiif_view.png",
        help="Filename for the rendered PNG preview",
    )
    parser.add_argument(
        "--summary-name",
        default="iiif_view_summary.json",
        help="Filename for the JSON summary output",
    )
    return parser.parse_args()


def _iter_dicts(values: Iterable[Any]) -> Iterator[Dict[str, Any]]:
    for value in values:
        if isinstance(value, dict):
            yield value


def _extract_image_url_from_v3(manifest: Dict[str, Any]) -> Optional[str]:
    for canvas in _iter_dicts(manifest.get("items", [])):
        for annotation_page in _iter_dicts(canvas.get("items", [])):
            for annotation in _iter_dicts(annotation_page.get("items", [])):
                body = annotation.get("body")
                if isinstance(body, dict):
                    candidate = body.get("id") or body.get("@id")
                    if candidate:
                        return candidate
                elif isinstance(body, list):
                    for body_item in _iter_dicts(body):
                        candidate = body_item.get("id") or body_item.get("@id")
                        if candidate:
                            return candidate
    return None


def _extract_image_url_from_v2(manifest: Dict[str, Any]) -> Optional[str]:
    for sequence in _iter_dicts(manifest.get("sequences", [])):
        for canvas in _iter_dicts(sequence.get("canvases", [])):
            for image in _iter_dicts(canvas.get("images", [])):
                resource = image.get("resource")
                if isinstance(resource, dict):
                    candidate = resource.get("@id") or resource.get("id")
                    if candidate:
                        return candidate
                candidate = image.get("@id") or image.get("id")
                if candidate:
                    return candidate
    return None


def resolve_image_url(manifest: Dict[str, Any]) -> str:
    """Return a direct URL to a displayable raster image from the manifest."""

    candidate = _extract_image_url_from_v3(manifest) or _extract_image_url_from_v2(manifest)
    if not candidate:
        raise IIIFImageResolutionError("Manifest did not contain a compatible image resource")

    parsed = urllib.parse.urlparse(candidate)
    if not parsed.scheme:
        raise IIIFImageResolutionError(f"Unsupported IIIF image reference: {candidate}")

    # IIIF references frequently include a fragment identifier (e.g. #xywh)
    candidate = urllib.parse.urlunparse(parsed._replace(fragment=""))

    if candidate.endswith("/info.json"):
        candidate = candidate[: -len("/info.json")]
    if candidate.endswith("/manifest"):
        candidate = candidate[: -len("/manifest")]

    # Request a reasonably sized derivative using the standard IIIF pattern.
    if not candidate.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff')):
        candidate = candidate.rstrip("/") + "/full/!2048,2048/0/default.jpg"

    return candidate


def download_image(url: str) -> Image.Image:
    response = requests.get(url, timeout=(10, 60))
    response.raise_for_status()
    try:
        return Image.open(io.BytesIO(response.content))
    except Exception as exc:  # pragma: no cover - defensive conversion guard
        raise IIIFImageResolutionError(f"Failed to decode IIIF image: {exc}") from exc


def main() -> None:
    args = parse_args()
    manifest_data = json.loads(args.manifest.read_text(encoding="utf-8"))

    try:
        image_url = resolve_image_url(manifest_data)
        image = download_image(image_url)
    except (requests.RequestException, IIIFImageResolutionError) as exc:
        print(f"::error::Unable to render IIIF image: {exc}")
        sys.exit(1)

    output_dir: pathlib.Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / args.image_name
    # Ensure a consistent format regardless of the source
    image.convert("RGB").save(output_path, format="PNG")

    summary = {
        "manifest": str(args.manifest),
        "image_url": image_url,
        "render_path": str(output_path),
        "width": image.width,
        "height": image.height,
        "mode": image.mode,
    }

    summary_path = output_dir / args.summary_name
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
