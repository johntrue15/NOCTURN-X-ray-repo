#!/usr/bin/env python3
"""
Query MorphoSource /api/media for a free-text search (default: "X-ray"),
extract the total number of matching Media records, and integrate with the repo:
 - Writes/updates `.github/last_count.txt` for state
 - Writes `morphosource_xray_count.txt` with the latest total
 - Emits GitHub Actions outputs: new_data, details, count, old_count, delta

Env vars (all optional except defaults provided):
  BASE_URL         default https://www.morphosource.org/api/media
  QUERY            default "X-ray"
  MORPHOSOURCE_API_KEY  optional Bearer token
  LAST_COUNT_FILE  default .github/last_count.txt
  COUNT_OUTFILE    default morphosource_xray_count.txt
"""

import os
import sys
import time
import json
import math
import requests
from typing import Optional, Tuple

BASE_URL       = os.getenv("BASE_URL", "https://www.morphosource.org/api/media")
QUERY          = os.getenv("QUERY", "X-ray")
API_KEY        = os.getenv("MORPHOSOURCE_API_KEY", "").strip()
LAST_COUNT_FILE= os.getenv("LAST_COUNT_FILE", ".github/last_count.txt")
COUNT_OUTFILE  = os.getenv("COUNT_OUTFILE", "morphosource_xray_count.txt")

# Conservative retry settings
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_TRIES    = 4
TIMEOUT      = (5, 30)  # (connect, read)

def write_github_output(**kv):
    """Append key=value lines to $GITHUB_OUTPUT for step outputs."""
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if not gh_out:
        return
    with open(gh_out, "a") as fh:
        for k, v in kv.items():
            if isinstance(v, str) and "\n" in v:
                fh.write(f"{k}<<EOF\n{v}\nEOF\n")
            else:
                fh.write(f"{k}={v}\n")

def load_last_count() -> int:
    if not os.path.exists(LAST_COUNT_FILE):
        return 0
    try:
        with open(LAST_COUNT_FILE, "r") as f:
            return int(f.read().strip())
    except Exception:
        return 0

def save_last_count(n: int) -> None:
    os.makedirs(os.path.dirname(LAST_COUNT_FILE), exist_ok=True)
    with open(LAST_COUNT_FILE, "w") as f:
        f.write(str(int(n)))

def save_count_txt(n: int) -> None:
    with open(COUNT_OUTFILE, "w") as f:
        f.write(str(int(n)))

def build_headers():
    h = {"Accept": "application/json"}
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    return h

def request_with_retries(url: str, params: dict) -> requests.Response:
    """GET with basic backoff + Retry-After support; never raises for status."""
    tries = 0
    while True:
        tries += 1
        try:
            resp = requests.get(url, headers=build_headers(), params=params, timeout=TIMEOUT)
        except requests.RequestException as e:
            if tries >= MAX_TRIES:
                return make_failed_response(str(e))
            sleep = min(60, 2 ** tries)
            print(f"[warn] request error (try {tries}/{MAX_TRIES}): {e}; sleeping {sleep}s", file=sys.stderr)
            time.sleep(sleep)
            continue

        # OK?
        if resp.status_code < 400:
            return resp

        # Retryable?
        if resp.status_code in RETRY_STATUS and tries < MAX_TRIES:
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    sleep = max(1, int(retry_after))
                except ValueError:
                    sleep = min(60, 2 ** tries)
            else:
                sleep = min(60, 2 ** tries)
            print(f"[warn] HTTP {resp.status_code} (try {tries}/{MAX_TRIES}); sleeping {sleep}s", file=sys.stderr)
            time.sleep(sleep)
            continue

        # Non-retryable or ran out of tries
        return resp

def make_failed_response(msg: str) -> requests.Response:
    r = requests.Response()
    r.status_code = 599
    r._content = msg.encode("utf-8")
    r.url = BASE_URL
    return r

def extract_total_from_json(data: dict) -> Optional[int]:
    """
    MorphoSource Stoplight docs say /api/media supports free-text search;
    results are paged and typically include total in metadata.
    Try common shapes, then fall back gracefully. 
    """
    # Common meta keys
    for path in [
        ("meta", "total"),
        ("meta", "totalResults"),
        ("meta", "total_count"),
        ("pagination", "total"),
    ]:
        cur = data
        ok = True
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok:
            try:
                return int(cur)
            except (TypeError, ValueError):
                pass

    # Some APIs put counts alongside data arrays
    if isinstance(data, dict):
        for k in ("total", "totalResults", "count"):
            if k in data:
                try:
                    return int(data[k])
                except (TypeError, ValueError):
                    pass

    # Last resort: length of 'data' array (NOT a true total)
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return len(data["data"])

    return None

def build_search_params(query: str) -> list[dict]:
    """
    Try likely param names: 'q' (most common), then 'query', then 'search'.
    Use per_page=1 to minimize payload.
    """
    base = {"per_page": 1, "page": 1}
    return [
        dict(base, q=query),
        dict(base, query=query),
        dict(base, search=query),
    ]

def get_total_for_query(query: str) -> Tuple[Optional[int], Optional[str]]:
    last_error = None
    for params in build_search_params(query):
        resp = request_with_retries(BASE_URL, params)
        print(f"[debug] GET {resp.url} -> {resp.status_code}", file=sys.stderr)
        if resp.status_code >= 400:
            last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
            continue
        try:
            data = resp.json()
        except Exception as e:
            last_error = f"Bad JSON: {e}"
            continue

        total = extract_total_from_json(data)
        if isinstance(total, int) and total >= 0:
            return total, None

        last_error = "Could not locate 'total' in response JSON."
    return None, last_error

def main():
    total, err = get_total_for_query(QUERY)
    if total is None:
        msg = f"Error querying MorphoSource API for '{QUERY}': {err or 'Unknown error'}"
        print("[error]", msg, file=sys.stderr)
        write_github_output(new_data="false", details=msg)
        # Exit 0 to avoid failing scheduled runs
        sys.exit(0)

    print(f"[info] Total for '{QUERY}': {total}", file=sys.stderr)
    save_count_txt(total)

    old = load_last_count()
    delta = total - old
    print(f"[info] Previous: {old} -> Delta: {delta}", file=sys.stderr)

    # Always update the last_count file (so manual runs sync state)
    save_last_count(total)

    # Build release/message body (mirrors your scraper’s style)
    body_lines = [
        f"Queried MorphoSource API `/api/media` for: **{QUERY}**",
        f"Total matching media: **{total}**",
        "",
        f"Previous recorded total: {old}",
        f"New records since last run: **{delta}**",
        "",
        "This run used the API (not HTML scraping) and wrote:",
        f"- `{LAST_COUNT_FILE}` (state)",
        f"- `{COUNT_OUTFILE}` (plain-text total)",
    ]
    body = "\n".join(body_lines)

    is_new = "true" if delta > 0 else "false"
    write_github_output(
        new_data=is_new,
        details=body,
        count=str(total),
        old_count=str(old),
        delta=str(delta),
    )

if __name__ == "__main__":
    main()
