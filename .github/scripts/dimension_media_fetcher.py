#!/usr/bin/env python3
"""Utility for selecting MorphoSource media for the dimension test workflow.

The ``dimension_test`` GitHub Actions workflow previously relied on hard-coded
URLs and manual input to determine whether to execute the 2D or 3D Selenium
fullscreen test.  This script replaces that behaviour with a data-driven
approach:

* Queries the MorphoSource public API for a media record (optionally provided
  via ``--media-id``).
* Inspects the media metadata to determine whether it represents a 2D image or
  a 3D dataset (mesh/volumetric).
* For 2D media, downloads the IIIF manifest to ``artifacts/`` so it can be
  attached to the workflow run.
* For 3D media, downloads representative files after including the required
  "reason for download" metadata in the HTTP request.
* Emits GitHub Actions outputs (``media_id``, ``media_url``, ``media_dimension``
  etc.) that subsequent steps can consume to drive Selenium and artifact
  uploads.

The script intentionally mirrors the conservative networking behaviour used by
``process_morphosource_records.py``.  Network failures result in a non-zero exit
status so the workflow can surface actionable errors.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import textwrap
import urllib.parse
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import requests


BASE_SEARCH_URL = "https://www.morphosource.org/api/media"
IIIF_MANIFEST_TEMPLATE = "https://www.morphosource.org/concern/media/{media_id}/manifest"
FILE_SET_API_TEMPLATE = "https://www.morphosource.org/api/file_sets/{file_set_id}"
MEDIA_DETAIL_URL = "https://www.morphosource.org/concern/media/{media_id}"
DEFAULT_DOWNLOAD_REASON = "Automated testing via GitHub Actions"
USER_AGENT = "NOCTURN-Dimension-Test/1.0"


class MediaLookupError(RuntimeError):
    """Raised when a media record cannot be located."""


@dataclass
class DownloadedFile:
    path: pathlib.Path
    size_bytes: int
    source_url: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "path": str(self.path),
            "size_bytes": str(self.size_bytes),
            "source_url": self.source_url,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select a MorphoSource media record")
    parser.add_argument(
        "--media-id",
        help="Optional MorphoSource media identifier. If omitted the latest record matching the query is used.",
    )
    parser.add_argument(
        "--query",
        default="X-Ray Computed Tomography",
        help="Search query to use when --media-id is not supplied (default: %(default)s)",
    )
    parser.add_argument(
        "--search-field",
        default="all_fields",
        help="MorphoSource search field (default: %(default)s)",
    )
    parser.add_argument(
        "--download-reason",
        default=DEFAULT_DOWNLOAD_REASON,
        help="Reason submitted when requesting downloads for 3D media.",
    )
    parser.add_argument(
        "--output-json",
        default="dimension_media_summary.json",
        help="File where a JSON summary will be written.",
    )
    parser.add_argument(
        "--artifact-dir",
        default="artifacts",
        help="Directory where manifests/downloads will be stored (default: %(default)s)",
    )
    return parser.parse_args()


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
    )
    return session


def search_latest_media(
    session: requests.Session,
    *,
    query: str,
    search_field: str,
    per_page: int = 1,
) -> Dict[str, object]:
    params = {
        "utf8": "✓",
        "search_field": search_field,
        "q": query,
        "sort": "system_create_dtsi desc",
        "per_page": per_page,
        "page": 1,
    }
    response = session.get(BASE_SEARCH_URL, params=params, timeout=(10, 60))
    response.raise_for_status()
    payload = response.json()
    media_items = payload.get("response", {}).get("media", [])
    if not media_items:
        raise MediaLookupError("No media records returned by MorphoSource search")
    return media_items[0]


def fetch_media_by_id(session: requests.Session, media_id: str) -> Dict[str, object]:
    detail_url = f"{BASE_SEARCH_URL}/{media_id}"
    response = session.get(detail_url, timeout=(10, 60))
    if response.status_code == 404:
        raise MediaLookupError(f"Media record {media_id} not found")
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and payload.get("response", {}).get("media"):
        # Some endpoints nest the record under response->media
        items = payload["response"]["media"]
        if isinstance(items, list) and items:
            return items[0]
    return payload


PREFERRED_MEDIA_ID_KEYS = (
    "id",
    "media_id",
    "media_id_ssi",
    "media_id_ssim",
    "media_id_tesim",
    "record_id",
    "system_identifier_ssi",
    "system_identifier_ssim",
    "system_identifier_tesim",
)

SECONDARY_MEDIA_ID_KEYS = (
    "ark_ssi",
    "ark_ssim",
    "url",
    "media_url",
    "detail_url",
)


def _normalise_media_id(value: object) -> Optional[str]:
    if value is None:
        return None
    candidate = str(value).strip().strip("\"'")
    if not candidate:
        return None
    lower_candidate = candidate.lower()
    if lower_candidate.startswith("ms-"):
        return candidate
    if candidate.isdigit():
        return candidate

    parsed = urllib.parse.urlparse(candidate)
    if parsed.scheme and parsed.path:
        path_parts = [part for part in parsed.path.split("/") if part]
        for part in reversed(path_parts):
            lowered = part.lower()
            if lowered in {"media", "concern", "manifest", "file_sets", "files"}:
                continue
            if lowered == "iiif" and path_parts:
                continue
            normalised = part.strip()
            if normalised:
                return normalised
    if "/" in candidate or "#" in candidate or ":" in candidate:
        for token in re.split(r"[/:#]", candidate):
            token = token.strip()
            if token and token.lower() not in {"media", "concern", "manifest", "iiif"}:
                return token
    return candidate or None


def _iter_candidate_values(record: Dict[str, object], keys: Iterable[str]):
    for key in keys:
        value = record.get(key)
        if isinstance(value, list):
            for item in value:
                yield item
        elif value is not None:
            yield value


def _search_nested_for_media_id(record: Dict[str, object]) -> Optional[str]:
    stack: List[object] = [record]
    visited: set[int] = set()
    while stack:
        current = stack.pop()
        identifier = id(current)
        if identifier in visited:
            continue
        visited.add(identifier)
        if isinstance(current, dict):
            for key in (*PREFERRED_MEDIA_ID_KEYS, *SECONDARY_MEDIA_ID_KEYS):
                if key in current:
                    for value in _iter_candidate_values(current, (key,)):
                        normalised = _normalise_media_id(value)
                        if normalised:
                            return normalised
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return None


def extract_media_id(record: Dict[str, object]) -> str:
    for value in _iter_candidate_values(record, PREFERRED_MEDIA_ID_KEYS):
        normalised = _normalise_media_id(value)
        if normalised:
            return normalised

    for value in _iter_candidate_values(record, SECONDARY_MEDIA_ID_KEYS):
        normalised = _normalise_media_id(value)
        if normalised:
            return normalised

    nested = _search_nested_for_media_id(record)
    if nested:
        return nested

    snippet = json.dumps(record)[:500]
    raise MediaLookupError(
        "Unable to determine media identifier from record; keys present were: "
        f"{', '.join(sorted(record.keys()))} | snippet={snippet}"
    )
def extract_media_id(record: Dict[str, object]) -> str:
    for key in ("id", "media_id", "record_id", "system_identifier_ssim"):
        value = record.get(key)
        if isinstance(value, list) and value:
            return str(value[0])
        if value:
            return str(value)
    raise MediaLookupError("Unable to determine media identifier from record")


def flatten_values(record: Dict[str, object], keys: Iterable[str]) -> List[str]:
    values: List[str] = []
    for key in keys:
        value = record.get(key)
        if isinstance(value, list):
            values.extend(str(item).lower() for item in value if item)
        elif isinstance(value, str):
            values.append(value.lower())
    return values


def determine_dimension(record: Dict[str, object]) -> str:
    tokens = flatten_values(
        record,
        (
            "media_type_ssim",
            "human_readable_media_type_ssim",
            "media_type_ssi",
            "modality_ssim",
            "human_readable_modality_tesim",
            "file_type_ssim",
        ),
    )
    if any(token for token in tokens if "mesh" in token or "volumetric" in token or "3d" in token):
        return "3d"
    if any(token for token in tokens if "image" in token or "2d" in token):
        return "2d"
    return "unknown"


def fetch_iiif_manifest(session: requests.Session, media_id: str, dest_dir: pathlib.Path) -> pathlib.Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    manifest_url = IIIF_MANIFEST_TEMPLATE.format(media_id=media_id)
    response = session.get(manifest_url, timeout=(10, 60))
    response.raise_for_status()
    manifest_path = dest_dir / f"iiif_manifest_{media_id}.json"
    manifest_path.write_text(json.dumps(response.json(), indent=2))
    return manifest_path


def discover_download_url(file_set_data: Dict[str, object]) -> Optional[str]:
    candidates: List[str] = []
    for key in (
        "download_url",
        "download_url_ss",
        "download_url_ssi",
        "download_url_ssim",
        "file_download_urls_ssim",
        "derived_files_ssim",
    ):
        value = file_set_data.get(key)
        if isinstance(value, list):
            candidates.extend(str(item) for item in value if isinstance(item, str))
        elif isinstance(value, str):
            candidates.append(value)
    for candidate in candidates:
        if candidate and candidate.startswith("http"):
            return candidate
    return None


def download_with_reason(
    session: requests.Session, url: str, dest: pathlib.Path, reason: str
) -> DownloadedFile:
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": USER_AGENT,
        "X-Download-Reason": reason,
        "X-MorphoSource-Download-Reason": reason,
    }
    parsed = urllib.parse.urlparse(url)
    params: Dict[str, str] = {}
    if "reason" not in urllib.parse.parse_qs(parsed.query):
        params["reason"] = reason

    with session.get(url, headers=headers, params=params, stream=True, timeout=(10, 120)) as response:
        response.raise_for_status()
        size = 0
        with dest.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)
                    size += len(chunk)
    return DownloadedFile(path=dest, size_bytes=size, source_url=response.url)


def download_mesh_assets(
    session: requests.Session,
    record: Dict[str, object],
    dest_dir: pathlib.Path,
    reason: str,
) -> List[DownloadedFile]:
    raw_file_sets = record.get("file_set_ids_ssim") or []
    if isinstance(raw_file_sets, str):
        file_set_ids = [raw_file_sets]
    elif isinstance(raw_file_sets, list):
        file_set_ids = [str(item) for item in raw_file_sets if item]
    else:
        file_set_ids = []

    downloads: List[DownloadedFile] = []
    for file_set_id in file_set_ids:
        metadata_url = FILE_SET_API_TEMPLATE.format(file_set_id=file_set_id)
        response = session.get(metadata_url, timeout=(10, 60))
        if response.status_code == 404:
            continue
        response.raise_for_status()
        metadata = response.json()
        download_url = discover_download_url(metadata)
        if not download_url:
            continue
        filename = metadata.get("label") or pathlib.Path(urllib.parse.urlparse(download_url).path).name
        if not filename:
            filename = f"{file_set_id}.bin"
        dest = dest_dir / filename
        downloads.append(download_with_reason(session, download_url, dest, reason))
    return downloads


def write_outputs(
    *,
    media_id: str,
    dimension: str,
    detail_url: str,
    manifest_path: Optional[pathlib.Path],
    downloads: List[DownloadedFile],
    summary_path: pathlib.Path,
) -> None:
    summary = {
        "media_id": media_id,
        "media_dimension": dimension,
        "detail_url": detail_url,
        "manifest_path": str(manifest_path) if manifest_path else "",
        "downloads": [d.to_dict() for d in downloads],
    }
    summary_path.write_text(json.dumps(summary, indent=2))

    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.write(f"media_id={media_id}\n")
            fh.write(f"media_url={detail_url}\n")
            fh.write(f"media_dimension={dimension}\n")
            fh.write(f"summary_path={summary_path}\n")
            if manifest_path:
                fh.write(f"manifest_path={manifest_path}\n")
            if downloads:
                download_dir = str(downloads[0].path.parent)
                fh.write(f"download_dir={download_dir}\n")
                fh.write(f"download_files={json.dumps([d.to_dict() for d in downloads])}\n")


def main() -> None:
    args = parse_args()
    session = create_session()

    try:
        if args.media_id:
            record = fetch_media_by_id(session, args.media_id)
        else:
            record = search_latest_media(session, query=args.query, search_field=args.search_field)
    except (requests.RequestException, MediaLookupError) as exc:
        print(f"::error::Failed to retrieve MorphoSource record: {exc}")
        sys.exit(1)

    try:
        media_id = extract_media_id(record)
    except MediaLookupError as exc:
        print(f"::error::{exc}")
        sys.exit(1)

    detail_url = MEDIA_DETAIL_URL.format(media_id=media_id)
    dimension = determine_dimension(record)
    artifact_root = pathlib.Path(args.artifact_dir)
    manifest_path: Optional[pathlib.Path] = None
    downloads: List[DownloadedFile] = []

    try:
        if dimension == "2d":
            manifest_path = fetch_iiif_manifest(session, media_id, artifact_root)
        elif dimension == "3d":
            downloads = download_mesh_assets(
                session,
                record,
                artifact_root / f"media_{media_id}",
                args.download_reason.strip() or DEFAULT_DOWNLOAD_REASON,
            )
    except requests.RequestException as exc:
        print(f"::error::Failed while collecting media artifacts: {exc}")
        sys.exit(1)

    summary_path = pathlib.Path(args.output_json)
    write_outputs(
        media_id=media_id,
        dimension=dimension,
        detail_url=detail_url,
        manifest_path=manifest_path,
        downloads=downloads,
        summary_path=summary_path,
    )

    print(
        textwrap.dedent(
            f"""
            Selected media {media_id}
              Dimension: {dimension}
              Detail URL: {detail_url}
              Summary written to: {summary_path}
            """
        ).strip()
    )


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()

