#!/usr/bin/env python3
"""Process MorphoSource media records using the public API.

This script replaces the Selenium based workflow that previously relied on the
MorphoSource website.  It queries the MorphoSource JSON API, detects newly
created CT records, and downloads representative media for local analysis
inside the GitHub Actions runner.

Behaviour:
  * Reads prior processing state from ``.github/morphosource_state.json``.
  * Queries ``/api/media`` sorted by ``system_create_dtsi desc``.
  * Collects records newer than the stored ``last_processed_timestamp``.
  * Downloads IIIF manifests for 2D media and representative media files for
    3D datasets (when available via the API) into ``downloads/<media_id>``.
  * Writes a Markdown summary and updates ``morphosource_xray_count.txt``.
  * Persists the new processing state for subsequent runs.

The script is intentionally defensive: if a download endpoint is unavailable or
returns an unexpected payload the error is logged but the workflow continues so
that other records can still be analysed.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

import requests

BASE_SEARCH_URL = "https://www.morphosource.org/api/media"
IIIF_MANIFEST_TEMPLATE = "https://www.morphosource.org/concern/media/{media_id}/manifest"
FILE_SET_API_TEMPLATE = "https://www.morphosource.org/api/file_sets/{file_set_id}"

QUERY = os.getenv("MORPHOSOURCE_QUERY", "X-ray")
SEARCH_FIELD = os.getenv("MORPHOSOURCE_SEARCH_FIELD", "all_fields")
STATE_FILE = pathlib.Path(".github/morphosource_state.json")
COUNT_FILE = pathlib.Path("morphosource_xray_count.txt")
DOWNLOAD_ROOT = pathlib.Path("downloads")
SUMMARY_FILE = pathlib.Path("analysis_summary.md")

API_KEY = os.getenv("MORPHOSOURCE_API_KEY", "").strip()
REQUEST_TIMEOUT = (10, 60)
MAX_PAGES = int(os.getenv("MORPHOSOURCE_MAX_PAGES", "5"))
PER_PAGE = int(os.getenv("MORPHOSOURCE_PER_PAGE", "25"))


@dataclass
class DownloadResult:
    """Represents a single downloaded asset."""

    path: pathlib.Path
    size_bytes: int
    source_url: str
    description: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "path": str(self.path),
            "size_bytes": str(self.size_bytes),
            "source_url": self.source_url,
            "description": self.description or "",
        }


@dataclass
class MediaRecord:
    """Container for a MorphoSource media record."""

    media_id: str
    title: str
    created_at: datetime
    media_type: str
    modality: str
    raw: Dict[str, object]
    downloads: List[DownloadResult] = field(default_factory=list)
    iiif_manifest_path: Optional[pathlib.Path] = None

    def to_summary_block(self) -> str:
        created = self.created_at.isoformat()
        downloads_section = "\n".join(
            f"  - `{d.path}` ({d.size_bytes} bytes) ← {d.source_url}" +
            (f" — {d.description}" if d.description else "")
            for d in self.downloads
        ) or "  - _(no downloadable assets located)_"

        manifest_line = (
            f"* IIIF manifest stored at `{self.iiif_manifest_path}`"
            if self.iiif_manifest_path else
            "* _No IIIF manifest saved_"
        )

        return textwrap.dedent(
            f"""
            ### Media {self.media_id}
            * Title: {self.title}
            * Created: {created}
            * Media type: {self.media_type or 'unknown'}
            * Modality: {self.modality or 'unknown'}
            {manifest_line}
            * Downloads:\n{downloads_section}
            """
        ).strip()


class MorphosourceAPIClient:
    """Minimal API client used by the workflow."""

    def __init__(self, api_key: str | None = None) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "NOCTURN-X-ray-Workflow/1.0"
        })
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"

    def request(self, method: str, url: str, *, params: Optional[Dict[str, object]] = None) -> requests.Response:
        response = self.session.request(method, url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response

    def iter_new_media(self, *, since: Optional[datetime]) -> Iterable[Dict[str, object]]:
        """Yield media records newer than ``since``."""

        page = 1
        while page <= MAX_PAGES:
            params = {
                "utf8": "✓",
                "search_field": SEARCH_FIELD,
                "q": QUERY,
                "sort": "system_create_dtsi desc",
                "page": page,
                "per_page": PER_PAGE,
            }
            response = self.request("GET", BASE_SEARCH_URL, params=params)
            payload = response.json()
            media_items = payload.get("response", {}).get("media", [])
            if not media_items:
                break

            for record in media_items:
                created_raw = record.get("system_create_dtsi") or record.get("date_uploaded_dtsi")
                if not created_raw:
                    continue
                created = parse_timestamp(created_raw)
                if since and created <= since:
                    return
                yield record

            page += 1

    def fetch_iiif_manifest(self, media_id: str) -> Dict[str, object]:
        url = IIIF_MANIFEST_TEMPLATE.format(media_id=media_id)
        response = self.request("GET", url)
        return response.json()

    def fetch_file_set_metadata(self, file_set_id: str) -> Dict[str, object]:
        url = FILE_SET_API_TEMPLATE.format(file_set_id=file_set_id)
        response = self.request("GET", url)
        return response.json()

    def download_binary(self, url: str, dest: pathlib.Path) -> DownloadResult:
        with self.session.get(url, timeout=REQUEST_TIMEOUT, stream=True) as response:
            response.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            size = 0
            with dest.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)
                        size += len(chunk)
        return DownloadResult(path=dest, size_bytes=size, source_url=url)


def parse_timestamp(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def load_state() -> Tuple[int, Optional[datetime]]:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            total = int(data.get("last_total", 0))
            ts_raw = data.get("last_processed_timestamp")
            timestamp = parse_timestamp(ts_raw) if ts_raw else None
            return total, timestamp
        except Exception:
            pass
    if COUNT_FILE.exists():
        try:
            total = int(COUNT_FILE.read_text().strip())
        except Exception:
            total = 0
    else:
        total = 0
    return total, None


def save_state(total: int, latest_timestamp: Optional[datetime]) -> None:
    payload = {
        "last_total": total,
        "last_processed_timestamp": latest_timestamp.isoformat().replace("+00:00", "Z") if latest_timestamp else None,
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(payload, indent=2))


def write_summary(records: List[MediaRecord], new_total: int, delta: int) -> None:
    header = textwrap.dedent(
        f"""
        # MorphoSource CT Analysis

        * Query: `{QUERY}`
        * New total count: **{new_total}**
        * Change since last run: **{delta}**
        * Records analysed: **{len(records)}**
        """
    ).strip()

    blocks = [record.to_summary_block() for record in records]
    content = "\n\n".join([header] + blocks) if blocks else header + "\n\n_No new records processed._"
    SUMMARY_FILE.write_text(content)


def discover_download_url(file_set_data: Dict[str, object]) -> Optional[str]:
    """Extract a download URL from a file set payload."""

    candidates = [
        file_set_data.get("download_url"),
        file_set_data.get("download_url_ss"),
        file_set_data.get("download_url_ssi"),
    ]
    for key in ["download_url_ssim", "file_download_urls_ssim", "derived_files_ssim"]:
        value = file_set_data.get(key)
        if isinstance(value, list) and value:
            candidates.extend(value)
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.startswith("http"):
            return candidate
    return None


def _stringify(value: object) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item)
    if isinstance(value, str):
        return value
    return ""


def process_record(client: MorphosourceAPIClient, record: Dict[str, object]) -> MediaRecord:
    media_id = str(record.get("id") or record.get("media_id") or "unknown")
    title = (
        _stringify(record.get("title_tesim"))
        or _stringify(record.get("title_ssi"))
        or _stringify(record.get("title"))
        or "Unknown Title"
    )
    created_at = parse_timestamp(record.get("system_create_dtsi") or record.get("date_uploaded_dtsi"))
    media_type = (
        _stringify(record.get("media_type_ssim"))
        or _stringify(record.get("human_readable_media_type_ssim"))
    )
    modality = (
        _stringify(record.get("modality_ssim"))
        or _stringify(record.get("human_readable_modality_tesim"))
    )
    media = MediaRecord(media_id=media_id, title=title, created_at=created_at, media_type=media_type, modality=modality, raw=record)

    download_dir = DOWNLOAD_ROOT / media_id
    download_dir.mkdir(parents=True, exist_ok=True)

    media_types = record.get("media_type_ssim")
    if isinstance(media_types, str):
        media_types_iter = [media_types]
    elif isinstance(media_types, list):
        media_types_iter = [str(item) for item in media_types if item]
    else:
        media_types_iter = []

    is_2d = any("image" in item.lower() for item in media_types_iter)
    is_mesh = any("mesh" in item.lower() for item in media_types_iter)

    if is_2d:
        try:
            manifest = client.fetch_iiif_manifest(media_id)
            manifest_path = download_dir / "iiif_manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2))
            media.iiif_manifest_path = manifest_path
            image_url = extract_first_image_url(manifest)
            if image_url:
                dest = download_dir / "preview.jpg"
                media.downloads.append(client.download_binary(image_url, dest))
        except Exception as exc:  # pragma: no cover - network exceptions
            print(f"[warn] Failed to process IIIF manifest for media {media_id}: {exc}", file=sys.stderr)

    if is_mesh:
        raw_file_sets = record.get("file_set_ids_ssim") or []
        if isinstance(raw_file_sets, str):
            file_set_ids = [raw_file_sets]
        elif isinstance(raw_file_sets, list):
            file_set_ids = [str(item) for item in raw_file_sets if item]
        else:
            file_set_ids = []

        for file_set_id in file_set_ids:
            try:
                metadata = client.fetch_file_set_metadata(file_set_id)
            except Exception as exc:  # pragma: no cover
                print(f"[warn] Could not fetch metadata for file set {file_set_id}: {exc}", file=sys.stderr)
                continue
            download_url = discover_download_url(metadata)
            if not download_url:
                print(f"[warn] No download URL found for file set {file_set_id}", file=sys.stderr)
                continue
            filename = metadata.get("label") or pathlib.Path(download_url).name
            dest = download_dir / filename
            try:
                result = client.download_binary(download_url, dest)
                result.description = metadata.get("display_title", "") or metadata.get("label", "")
                media.downloads.append(result)
            except Exception as exc:  # pragma: no cover
                print(f"[warn] Failed to download {download_url}: {exc}", file=sys.stderr)

    return media


def extract_first_image_url(manifest: Dict[str, object]) -> Optional[str]:
    sequences = manifest.get("sequences") or []
    if not sequences:
        return None
    first_sequence = sequences[0] or {}
    canvases = first_sequence.get("canvases") or []
    if not canvases:
        return None
    first_canvas = canvases[0] or {}
    images = first_canvas.get("images") or []
    if not images:
        return None
    first_image = images[0] or {}
    resource = first_image.get("resource", {})
    if isinstance(resource, dict):
        url = resource.get("@id") or resource.get("id")
        if url:
            return url
        service = resource.get("service", {})
        if isinstance(service, dict):
            service_id = service.get("@id") or service.get("id")
            if service_id:
                # Construct a level-2 IIIF image request (full image)
                return f"{service_id.rstrip('/')}/full/full/0/default.jpg"
    if isinstance(first_image, dict):
        candidate = first_image.get("@id") or first_image.get("id")
        if isinstance(candidate, str):
            return candidate
    return None


def main() -> None:
    try:
        client = MorphosourceAPIClient(API_KEY)
    except Exception as exc:
        print(f"::error::Failed to initialise MorphoSource API client: {exc}")
        sys.exit(1)

    last_total, last_timestamp = load_state()
    new_records: List[MediaRecord] = []
    latest_timestamp = last_timestamp

    try:
        for record in client.iter_new_media(since=last_timestamp):
            media = process_record(client, record)
            new_records.append(media)
            if latest_timestamp is None or media.created_at > latest_timestamp:
                latest_timestamp = media.created_at
    except requests.HTTPError as exc:
        print(f"::error::MorphoSource API request failed: {exc}")
        sys.exit(1)

    # Determine the current total count regardless of whether new records were processed.
    try:
        total_payload = client.request("GET", BASE_SEARCH_URL, params={
            "utf8": "✓",
            "search_field": SEARCH_FIELD,
            "q": QUERY,
            "sort": "system_create_dtsi desc",
            "page": 1,
            "per_page": 1,
        }).json()
        total_count = int(total_payload.get("response", {}).get("pages", {}).get("total_count", last_total))
    except Exception as exc:
        print(f"[warn] Unable to refresh total_count from API: {exc}", file=sys.stderr)
        total_count = last_total

    delta = total_count - last_total

    write_summary(new_records, total_count, delta)

    if total_count:
        COUNT_FILE.write_text(str(total_count))

    save_state(total_count, latest_timestamp)

    outputs = {
        "new_total": str(total_count),
        "previous_total": str(last_total),
        "delta": str(delta),
        "records_processed": str(len(new_records)),
    }
    if latest_timestamp:
        outputs["latest_timestamp"] = latest_timestamp.isoformat().replace("+00:00", "Z")

    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                handle.write(f"{key}={value}\n")

    if new_records:
        print(f"Processed {len(new_records)} new MorphoSource record(s).")
    else:
        print("No new MorphoSource records to process.")


if __name__ == "__main__":
    main()
