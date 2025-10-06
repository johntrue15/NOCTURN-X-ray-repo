#!/usr/bin/env python3
"""
Queries:
  https://www.morphosource.org/api/media?utf8=✓&search_field=all_fields&q=<QUERY>

Parses:
  response.pages.total_count
  response.media[0] (latest record from this page)

Writes:
  - .github/last_count.txt (state)
  - morphosource_xray_count.txt (plain-text total)

Exports step outputs to GITHUB_OUTPUT:
  new_data, details, count, old_count, delta, latest_id, latest_title

Release body (details) includes:
  - Summary (query, counts)
  - Link to the media detail page
  - A pretty JSON dump of the latest record (truncated if necessary)
"""

import os
import sys
import time
import json
import requests
from typing import Optional, Dict, Any

BASE_URL        = os.getenv("BASE_URL", "https://www.morphosource.org/api/media").strip()
QUERY           = os.getenv("QUERY", "X-ray")
UTF8_CHK        = os.getenv("UTF8_CHK", "✓")
SEARCH_FIELD    = os.getenv("SEARCH_FIELD", "all_fields")
LAST_COUNT_FILE = os.getenv("LAST_COUNT_FILE", ".github/last_count.txt")
COUNT_OUTFILE   = os.getenv("COUNT_OUTFILE", "morphosource_xray_count.txt")
API_KEY         = os.getenv("MORPHOSOURCE_API_KEY", "").strip()

TIMEOUT = (5, 30)
MAX_TRIES = 4
RETRY_STATUS = {429, 500, 502, 503, 504}

MAX_JSON_CHARS = 60000  # keep GH release under limits

def gh_set_outputs(**kv):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a") as fh:
        for k, v in kv.items():
            if isinstance(v, str) and "\n" in v:
                fh.write(f"{k}<<EOF\n{v}\nEOF\n")
            else:
                fh.write(f"{k}={v}\n")

def load_last_count() -> int:
    try:
        with open(LAST_COUNT_FILE, "r") as f:
            return int(f.read().strip())
    except Exception:
        return 0

def save_last_count(n: int):
    os.makedirs(os.path.dirname(LAST_COUNT_FILE), exist_ok=True)
    with open(LAST_COUNT_FILE, "w") as f:
        f.write(str(int(n)))

def save_count_txt(n: int):
    with open(COUNT_OUTFILE, "w") as f:
        f.write(str(int(n)))

def headers() -> Dict[str, str]:
    h = {"Accept": "application/json"}
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    return h

def request_with_backoff(url: str, params: dict) -> Optional[requests.Response]:
    tries = 0
    while tries < MAX_TRIES:
        tries += 1
        try:
            r = requests.get(url, headers=headers(), params=params, timeout=TIMEOUT)
        except requests.RequestException as e:
            if tries >= MAX_TRIES:
                print(f"[error] network error: {e}", file=sys.stderr)
                return None
            sleep = min(60, 2 ** tries)
            print(f"[warn] network error (try {tries}/{MAX_TRIES}), sleeping {sleep}s", file=sys.stderr)
            time.sleep(sleep)
            continue

        if r.status_code < 400:
            return r

        if r.status_code in RETRY_STATUS and tries < MAX_TRIES:
            ra = r.headers.get("Retry-After")
            try:
                sleep = max(1, int(ra)) if ra else min(60, 2 ** tries)
            except ValueError:
                sleep = min(60, 2 ** tries)
            print(f"[warn] HTTP {r.status_code} (try {tries}/{MAX_TRIES}) sleeping {sleep}s", file=sys.stderr)
            time.sleep(sleep)
            continue

        print(f"[error] HTTP {r.status_code}: {r.text[:300]}", file=sys.stderr)
        return None
    return None

def extract_total_count(payload: Dict[str, Any]) -> Optional[int]:
    try:
        resp = payload.get("response") if isinstance(payload, dict) else None
        pages = resp.get("pages") if isinstance(resp, dict) else None
        tc = pages.get("total_count") if isinstance(pages, dict) else None
        return int(tc) if tc is not None else None
    except Exception:
        return None

def get_first_media(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        media = payload.get("response", {}).get("media", [])
        if isinstance(media, list) and media:
            # Take the first item from this page (page 1)
            return media[0]
        return None
    except Exception:
        return None

def first_text(record: Dict[str, Any], *keys):
    """
    Convenience: return first string for any *_tesim fields (list) or direct string field.
    """
    for k in keys:
        if k in record:
            v = record[k]
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, str) and item.strip():
                        return item.strip()
            elif isinstance(v, str) and v.strip():
                return v.strip()
    return ""

def main():
    params = {
        "utf8": UTF8_CHK,          # must be ✓
        "search_field": SEARCH_FIELD,
        "q": QUERY,
        # NOTE: we rely on page=1 default; if API adds paging params later, we can set them here.
    }

    r = request_with_backoff(BASE_URL, params)
    if not r:
        msg = f"Failed to query MorphoSource API at {BASE_URL}"
        print("[error]", msg, file=sys.stderr)
        gh_set_outputs(new_data="false", details=msg)
        sys.exit(0)  # don't fail cron

    print(f"[debug] GET {r.url} -> {r.status_code}", file=sys.stderr)
    try:
        data = r.json()
    except Exception as e:
        msg = f"Bad JSON from API: {e}"
        print("[error]", msg, file=sys.stderr)
        gh_set_outputs(new_data="false", details=msg)
        sys.exit(0)

    total = extract_total_count(data)
    if total is None:
        msg = "Could not find response.pages.total_count in API response."
        preview = json.dumps(data, indent=2)[:1000]
        print("[error]", msg, file=sys.stderr)
        gh_set_outputs(new_data="false", details=f"{msg}\n\nPreview:\n{preview}")
        sys.exit(0)

    latest = get_first_media(data)
    latest_id = latest.get("id") if isinstance(latest, dict) else None
    latest_title = ""
    if latest:
        # Try a few common title fields
        latest_title = (first_text(latest, "title_ssi", "title_tesim") or
                        first_text(latest, "short_title_tesim") or
                        f"Media {latest_id or ''}").strip()

    # Persist count files
    save_count_txt(total)
    old = load_last_count()
    delta = total - old

    # Always update local state (keeps manual dispatch in sync)
    save_last_count(total)

    # Build a pretty JSON block for the latest record
    latest_json_block = ""
    if latest:
        raw = json.dumps(latest, indent=2, ensure_ascii=False)
        if len(raw) > MAX_JSON_CHARS:
            raw = raw[:MAX_JSON_CHARS] + "\n... [truncated]"
        latest_json_block = f"```json\n{raw}\n```"
    else:
        latest_json_block = "_No media records returned on page 1._"

    # Detail page URL (public UI)
    detail_url = f"https://www.morphosource.org/concern/media/{latest_id}" if latest_id else "(unknown)"

    body = "\n".join([
        f"Queried **/api/media** with: `utf8=✓&search_field={SEARCH_FIELD}&q={QUERY}`",
        f"**total_count**: **{total}**",
        "",
        f"Previous recorded total: {old}",
        f"New records since last run: **{delta}**",
        "",
        "## Latest record (from this API page)",
        f"- **id:** `{latest_id}`",
        f"- **title:** {latest_title or '(none)'}",
        f"- **detail page:** {detail_url}",
        "",
        "### Full API JSON for latest record",
        latest_json_block,
    ])

    gh_set_outputs(
        new_data="true" if delta > 0 else "false",
        details=body,
        count=str(total),
        old_count=str(old),
        delta=str(delta),
        latest_id=str(latest_id or ""),
        latest_title=latest_title,
    )

if __name__ == "__main__":
    main()
