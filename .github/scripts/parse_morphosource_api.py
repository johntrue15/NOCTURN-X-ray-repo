#!/usr/bin/env python3
"""
Hits: https://www.morphosource.org/api/media?utf8=✓&search_field=all_fields&q=<QUERY>
Parses: response.pages.total_count
Writes:
 - .github/last_count.txt (state)
 - morphosource_xray_count.txt (plain text total)
Emits step outputs (new_data, details, count, old_count, delta) via GITHUB_OUTPUT.
"""

import os, sys, time, json, requests
from typing import Optional

BASE_URL        = os.getenv("BASE_URL", "https://www.morphosource.org/api/media").strip()
QUERY           = os.getenv("QUERY", "X-ray")
UTF8_CHK        = os.getenv("UTF8_CHK", "✓")  # must be the checkmark
SEARCH_FIELD    = os.getenv("SEARCH_FIELD", "all_fields")
LAST_COUNT_FILE = os.getenv("LAST_COUNT_FILE", ".github/last_count.txt")
COUNT_OUTFILE   = os.getenv("COUNT_OUTFILE", "morphosource_xray_count.txt")
API_KEY         = os.getenv("MORPHOSOURCE_API_KEY", "").strip()

TIMEOUT = (5, 30)
MAX_TRIES = 4
RETRY_STATUS = {429, 500, 502, 503, 504}

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

def headers():
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

def extract_total_count(payload: dict) -> Optional[int]:
    """
    Expecting:
      {
        "response": {
          "media": [...],
          "pages": {
            "total_count": 116589,
            ...
          }
        }
      }
    """
    try:
        resp = payload.get("response") if isinstance(payload, dict) else None
        pages = resp.get("pages") if isinstance(resp, dict) else None
        tc = pages.get("total_count") if isinstance(pages, dict) else None
        if tc is None:
            return None
        return int(tc)
    except Exception:
        return None

def main():
    params = {
        "utf8": UTF8_CHK,
        "search_field": SEARCH_FIELD,
        "q": QUERY,
        # keep payload small; API defaults are fine, but we can set limit via "limit_value" if needed
    }

    r = request_with_backoff(BASE_URL, params)
    if not r:
        msg = f"Failed to query MorphoSource API at {BASE_URL}"
        print("[error]", msg, file=sys.stderr)
        gh_set_outputs(new_data="false", details=msg)
        sys.exit(0)

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
        print("[error]", msg, file=sys.stderr)
        # Include a short preview to help debug
        preview = json.dumps(data, indent=2)[:1000]
        gh_set_outputs(new_data="false", details=f"{msg}\n\nPreview:\n{preview}")
        sys.exit(0)

    # Persist files
    save_count_txt(total)
    old = load_last_count()
    delta = total - old

    # Always update local state file
    save_last_count(total)

    body = "\n".join([
        f"Queried **/api/media** with: `utf8=✓&search_field={SEARCH_FIELD}&q={QUERY}`",
        f"**total_count**: **{total}**",
        "",
        f"Previous recorded total: {old}",
        f"New records since last run: **{delta}**",
        "",
        f"Wrote `{LAST_COUNT_FILE}` (state) and `{COUNT_OUTFILE}` (plain-text total).",
    ])

    is_new = "true" if delta > 0 else "false"
    gh_set_outputs(
        new_data=is_new,
        details=body,
        count=str(total),
        old_count=str(old),
        delta=str(delta),
    )

if __name__ == "__main__":
    main()
