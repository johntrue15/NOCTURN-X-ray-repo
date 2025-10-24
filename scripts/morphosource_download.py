#!/usr/bin/env python3
"""
MorphoSource download helper for GitHub Actions.

- Verifies API key by calling /api/media/{id}
- Requests a time-limited download URL via /api/download/{id}
- Downloads the file and saves it to --out-dir
- Emits the saved file path to GITHUB_OUTPUT if available
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests


BASE = "https://www.morphosource.org/api"


def eprint(*a, **k):
    print(*a, file=sys.stderr, **k)


def header_filename(content_disposition: str | None) -> str | None:
    """Extract filename from a Content-Disposition header."""
    if not content_disposition:
        return None
    # Try RFC 5987 filename*=
    m = re.search(r'filename\*\s*=\s*[^\'"]*\'[^\'"]*\'([^;]+)', content_disposition, flags=re.I)
    if m:
        return unquote(m.group(1).strip())
    # Fallback filename=
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


def ensure_ok(resp: requests.Response, label: str):
    if 200 <= resp.status_code < 300:
        return
    # Try to include any JSON error details
    details = ""
    try:
        details_json = resp.json()
        details = f" | error: {json.dumps(details_json, ensure_ascii=False)}"
    except Exception:
        if resp.text:
            details = f" | error: {resp.text[:500]}"
    raise SystemExit(f"{label} failed: HTTP {resp.status_code}{details}")


def request_signed_url(session: requests.Session, api_key: str, media_id: str,
                       use_statement: str, use_categories: list[str] | None,
                       use_category_other: str | None) -> str:
    url = f"{BASE}/download/{media_id}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        # MorphoSource expects the raw key (no Bearer)
        "Authorization": api_key,
    }
    payload: dict = {"use_statement": use_statement, "agree_to_terms": True}
    if use_categories:
        payload["use_categories"] = use_categories
    elif use_category_other:
        payload["use_category_other"] = use_category_other

    resp = session.post(url, headers=headers, data=json.dumps(payload), timeout=60)
    ensure_ok(resp, "Requesting signed download URL")

    data = resp.json()
    # The URL may be at response.url or url
    signed = (data.get("response") or {}).get("url") or data.get("url")
    if not signed:
        raise SystemExit(f"Download URL not found in response: {json.dumps(data)[:600]}")
    return signed


def auth_check(session: requests.Session, api_key: str, media_id: str):
    url = f"{BASE}/media/{media_id}"
    resp = session.get(url, headers={
        "Accept": "application/json",
        "Authorization": api_key,
    }, timeout=30)
    ensure_ok(resp, "API key check (GET /media/{id})")


def download_file(session: requests.Session, signed_url: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    with session.get(signed_url, stream=True, allow_redirects=True, timeout=300) as r:
        ensure_ok(r, "Downloading file")
        fname = header_filename(r.headers.get("Content-Disposition")) or derive_filename_from_url(signed_url)
        # Make sure we don't escape out_dir
        fname = Path(Path(fname).name)
        dest = out_dir / fname
        # Stream to disk
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        return dest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--media-id", required=True, help="MorphoSource media ID (e.g., 000788351)")
    p.add_argument("--use-statement", required=True, help="Use statement to include in the request")
    p.add_argument("--use-category", action="append", default=None,
                   help="Enumerated category. May be repeated. Example: --use-category Research")
    p.add_argument("--category-other", default="", help="Free-text category if not using enumerated list")
    p.add_argument("--out-dir", default="downloads", help="Directory to save the downloaded file")
    args = p.parse_args()

    api_key = os.environ.get("MORPHOSOURCE_API_KEY")
    if not api_key:
        raise SystemExit("MORPHOSOURCE_API_KEY is not set in the environment")

    # Clean up categories
    use_categories = None
    if args.use_category:
        use_categories = [c.strip() for c in args.use_category if c and c.strip()]
    category_other = args.category_other.strip() or None

    with requests.Session() as s:
        # 1) quick auth check
        eprint("Checking API key …")
        auth_check(s, api_key, args.media_id)
        eprint("Auth OK.")

        # 2) request signed URL
        eprint("Requesting signed download URL …")
        signed_url = request_signed_url(
            s, api_key, args.media_id,
            args.use_statement, use_categories, category_other
        )
        eprint(f"Signed URL received.")

        # 3) download
        eprint("Downloading file … (this may take a while)")
        dest = download_file(s, signed_url, Path(args.out_dir))
        print(f"Saved: {dest}")

        # 4) Make it available as a GitHub Actions output
        gh_out = os.environ.get("GITHUB_OUTPUT")
        if gh_out:
            with open(gh_out, "a", encoding="utf-8") as fh:
                fh.write(f"file={dest}\n")


if __name__ == "__main__":
    main()
