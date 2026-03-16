#!/usr/bin/env python3
"""
Download a MorphoSource media file using parsed API record JSON.

Accepts either:
  1. A JSON string (from parse_morphosource API output) via RECORD_JSON env var
  2. A bare media ID via MEDIA_ID env var

Steps:
  1. Parse the record JSON and extract the media ID and visibility.
  2. Check that visibility is "open" (skip download if restricted).
  3. Request a signed download URL via POST /api/download/{media_id}.
  4. Download the file and save it to OUT_DIR.
  5. Emit outputs for downstream GitHub Actions steps.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse

import requests

BASE = "https://www.morphosource.org/api"
TIMEOUT = (10, 120)


# --------------- helpers ---------------

def eprint(*a: object, **k: object) -> None:
    print(*a, file=sys.stderr, **k)


def gh_set_outputs(**kv: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        for k, v in kv.items():
            if "\n" in str(v):
                fh.write(f"{k}<<EOF\n{v}\nEOF\n")
            else:
                fh.write(f"{k}={v}\n")


def _first(value: Any) -> str:
    """Return the first element if *value* is a list, else str(value)."""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value) if value is not None else ""


def header_filename(content_disposition: Optional[str]) -> Optional[str]:
    """Extract filename from a Content-Disposition header."""
    if not content_disposition:
        return None
    m = re.search(
        r'filename\*\s*=\s*[^\'"]*\'[^\'"]*\'([^;]+)',
        content_disposition,
        flags=re.I,
    )
    if m:
        return unquote(m.group(1).strip())
    m = re.search(r'filename\s*=\s*"([^"]+)"', content_disposition, flags=re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r'filename\s*=\s*([^;]+)', content_disposition, flags=re.I)
    if m:
        return m.group(1).strip().strip("'")
    return None


def derive_filename_from_url(url: str) -> str:
    path = urlparse(url).path
    name = Path(path).name or "download"
    return unquote(name)


# --------------- record parsing ---------------

def parse_record(raw_json: str) -> Dict[str, Any]:
    """Parse a MorphoSource API record JSON string."""
    try:
        return json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in RECORD_JSON: {exc}") from exc


def extract_media_id(record: Dict[str, Any]) -> str:
    """Extract the media ID from a parsed record."""
    raw = record.get("id") or record.get("media_id") or ""
    return _first(raw)


def extract_visibility(record: Dict[str, Any]) -> str:
    """Return the visibility value (e.g. 'open', 'restricted')."""
    return _first(record.get("visibility", ""))


def extract_metadata(record: Dict[str, Any]) -> Dict[str, str]:
    """Pull commonly useful metadata from the record."""
    return {
        "title": _first(record.get("title", "")),
        "media_type": _first(record.get("media_type", "")),
        "modality": _first(record.get("modality", "")),
        "visibility": extract_visibility(record),
        "creator": _first(record.get("creator", "")),
        "physical_object_title": _first(record.get("physical_object_title", "")),
        "physical_object_taxonomy_name": _first(
            record.get("physical_object_taxonomy_name", "")
        ),
        "license": _first(record.get("license", "")),
        "ark": _first(record.get("ark", "")),
        "date_uploaded": _first(record.get("date_uploaded", "")),
    }


# --------------- API interactions ---------------

def check_media_exists(
    session: requests.Session, api_key: str, media_id: str
) -> Dict[str, Any]:
    """GET /api/media/{id} to verify media exists and inspect its metadata."""
    url = f"{BASE}/media/{media_id}"
    headers: Dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = api_key
    resp = session.get(url, headers=headers, timeout=TIMEOUT)
    if resp.status_code != 200:
        raise SystemExit(
            f"Media check failed: HTTP {resp.status_code} — {resp.text[:500]}"
        )
    return resp.json()


def request_download_url(
    session: requests.Session, api_key: str, media_id: str
) -> str:
    """POST /api/download/{id} to obtain a signed download URL."""
    url = f"{BASE}/download/{media_id}"
    headers: Dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = api_key

    payload = {
        "use_statement": "Automated download for CT image analysis research workflow",
        "use_categories": ["Research"],
        "agreements_accepted": True,
    }
    resp = session.post(
        url, headers=headers, data=json.dumps(payload), timeout=TIMEOUT
    )
    if resp.status_code < 200 or resp.status_code >= 300:
        detail = ""
        try:
            detail = f" | {json.dumps(resp.json(), ensure_ascii=False)}"
        except Exception:
            if resp.text:
                detail = f" | {resp.text[:500]}"
        raise SystemExit(
            f"Download URL request failed: HTTP {resp.status_code}{detail}"
        )

    data = resp.json()
    # Try response.media.download_url (official API format), then fallback
    media_node = ((data.get("response") or {}).get("media") or {})
    download_urls = media_node.get("download_url") if isinstance(media_node, dict) else None
    if isinstance(download_urls, list) and download_urls:
        signed = download_urls[0]
    elif isinstance(download_urls, str):
        signed = download_urls
    else:
        signed = (data.get("response") or {}).get("url") or data.get("url")
    if not signed:
        raise SystemExit(
            f"No download URL in response: {json.dumps(data)[:600]}"
        )
    return signed


def download_file(
    session: requests.Session, signed_url: str, out_dir: Path, media_id: str,
    api_key: str = "",
) -> Path:
    """Stream the file from the signed URL to disk."""
    out_dir.mkdir(parents=True, exist_ok=True)
    headers: Dict[str, str] = {}
    if api_key:
        headers["Authorization"] = api_key
    with session.get(
        signed_url, headers=headers, stream=True, allow_redirects=True,
        timeout=(10, 300),
    ) as r:
        if r.status_code < 200 or r.status_code >= 300:
            raise SystemExit(
                f"Download failed: HTTP {r.status_code} — {r.text[:500]}"
            )
        fname = header_filename(r.headers.get("Content-Disposition"))
        if not fname:
            fname = derive_filename_from_url(signed_url)
        # Ensure no path traversal
        fname = Path(fname).name
        if not fname:
            fname = f"media_{media_id}"
        dest = out_dir / fname
        size = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    size += len(chunk)
    eprint(f"Downloaded {size:,} bytes -> {dest}")
    return dest


# --------------- main ---------------

def main() -> None:
    record_json = os.environ.get("RECORD_JSON", "").strip()
    media_id_env = os.environ.get("MEDIA_ID", "").strip()
    api_key = os.environ.get("MORPHOSOURCE_API_KEY", "").strip()
    out_dir = Path(os.environ.get("OUT_DIR", "downloads"))

    # --- determine media ID and metadata ---
    metadata: Dict[str, str] = {}
    if record_json:
        eprint("Parsing RECORD_JSON …")
        record = parse_record(record_json)
        media_id = extract_media_id(record)
        metadata = extract_metadata(record)
        if not media_id:
            raise SystemExit("Could not extract media ID from RECORD_JSON")
        eprint(f"  Media ID : {media_id}")
        eprint(f"  Title    : {metadata.get('title', '')}")
        eprint(f"  Visibility: {metadata.get('visibility', '')}")
    elif media_id_env:
        media_id = media_id_env
        eprint(f"Using MEDIA_ID from environment: {media_id}")
    else:
        raise SystemExit(
            "Either RECORD_JSON or MEDIA_ID must be set in the environment"
        )

    # --- check visibility ---
    visibility = metadata.get("visibility", "").lower()
    if visibility and visibility != "open":
        msg = (
            f"Media {media_id} has visibility '{visibility}' — "
            "skipping download (only open media is downloaded automatically)."
        )
        eprint(msg)
        gh_set_outputs(
            media_id=media_id,
            visibility=visibility,
            download_skipped="true",
            skip_reason=msg,
            **{k: v for k, v in metadata.items() if k != "visibility"},
        )
        return

    # --- verify media exists via API ---
    with requests.Session() as session:
        eprint("Checking media via API …")
        api_data = check_media_exists(session, api_key, media_id)

        # If we didn't get visibility from RECORD_JSON, check the API response
        if not visibility:
            api_vis = ""
            response_obj = api_data.get("response", api_data)
            if isinstance(response_obj, dict):
                vis_raw = response_obj.get("visibility_ssi") or response_obj.get("visibility")
                api_vis = _first(vis_raw).lower() if vis_raw else ""
            if api_vis and api_vis != "open":
                msg = (
                    f"Media {media_id} has API visibility '{api_vis}' — "
                    "skipping download (only open media is downloaded automatically)."
                )
                eprint(msg)
                gh_set_outputs(
                    media_id=media_id,
                    visibility=api_vis,
                    download_skipped="true",
                    skip_reason=msg,
                )
                return
            visibility = api_vis or "unknown"

        eprint("Media exists — proceeding to download.")

        # --- request download URL ---
        eprint("Requesting signed download URL …")
        signed_url = request_download_url(session, api_key, media_id)
        eprint("Signed URL received.")

        # --- download ---
        eprint("Downloading file …")
        dest = download_file(session, signed_url, out_dir, media_id, api_key)
        file_size = dest.stat().st_size

        eprint(f"Saved: {dest} ({file_size:,} bytes)")

        # --- emit outputs ---
        gh_set_outputs(
            media_id=media_id,
            visibility=visibility,
            download_skipped="false",
            downloaded_file=str(dest),
            downloaded_file_size=str(file_size),
            **{k: v for k, v in metadata.items() if k != "visibility"},
        )


if __name__ == "__main__":
    main()
