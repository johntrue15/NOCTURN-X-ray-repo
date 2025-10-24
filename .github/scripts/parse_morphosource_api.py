#!/usr/bin/env python3
"""
Queries:
  https://www.morphosource.org/api/media?utf8=✓&search_field=all_fields&q=<QUERY>&sort=system_create_dtsi+desc

Outputs:
  - count (current total_count)
  - old_count (baseline)
  - delta (count - old_count, or =count if baseline missing)
  - new_data ("true" if delta>0 OR first run; else "false")
  - latest_id, latest_title
  - baseline_source ("last_count.txt" | "count_outfile" | "missing")

Writes:
  - .github/last_count.txt (state)
  - morphosource_xray_count.txt (current count)
  - Rich release body with latest record JSON (truncated)
"""

import os, sys, time, json, requests
from typing import Optional, Dict, Any, Tuple

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
MAX_JSON_CHARS = 60000

def gh_set_outputs(**kv):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path: return
    with open(path, "a") as fh:
        for k, v in kv.items():
            if isinstance(v, str) and "\n" in v:
                fh.write(f"{k}<<EOF\n{v}\nEOF\n")
            else:
                fh.write(f"{k}={v}\n")

def load_baseline() -> Tuple[Optional[int], str]:
    """Return (count, source)."""
    # 1) Prefer last_count.txt
    if os.path.exists(LAST_COUNT_FILE):
        try:
            with open(LAST_COUNT_FILE, "r") as f:
                return int(f.read().strip()), "last_count.txt"
        except Exception:
            pass
    # 2) Fallback to previous plain-text count file
    if os.path.exists(COUNT_OUTFILE):
        try:
            with open(COUNT_OUTFILE, "r") as f:
                return int(f.read().strip()), "count_outfile"
        except Exception:
            pass
    # 3) Missing baseline altogether
    return None, "missing"

def save_last_count(n: int):
    os.makedirs(os.path.dirname(LAST_COUNT_FILE), exist_ok=True)
    with open(LAST_COUNT_FILE, "w") as f:
        f.write(str(int(n)))

def save_count_txt(n: int):
    with open(COUNT_OUTFILE, "w") as f:
        f.write(str(int(n)))

def headers() -> Dict[str, str]:
    h = {"Accept": "application/json"}
    if API_KEY: h["Authorization"] = f"Bearer {API_KEY}"
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
            time.sleep(sleep); continue
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
        return media[0] if isinstance(media, list) and media else None
    except Exception:
        return None

def first_text(record: Dict[str, Any], *keys):
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
    params = {"utf8": UTF8_CHK, "search_field": SEARCH_FIELD, "q": QUERY, "sort": "system_create_dtsi desc"}
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
        preview = json.dumps(data, indent=2)[:1000]
        print("[error]", msg, file=sys.stderr)
        gh_set_outputs(new_data="false", details=f"{msg}\n\nPreview:\n{preview}")
        sys.exit(0)

    latest = get_first_media(data)
    
    # Ensure latest_id is always a string, never None or empty
    if isinstance(latest, dict):
        id_value = latest.get("id", "")
        # Handle case where id is a list (e.g., ['000788438'])
        if isinstance(id_value, list):
            latest_id = str(id_value[0]) if id_value else ""
        else:
            latest_id = str(id_value)
    else:
        latest_id = ""
    
    # If still empty, use a fallback
    if not latest_id or latest_id == "None":
        latest_id = f"unknown-{int(time.time())}"
        print(f"[warn] No valid media ID found, using fallback: {latest_id}", file=sys.stderr)
    
    latest_title = ""
    if latest:
        latest_title = (first_text(latest, "title_ssi", "title_tesim") or
                        first_text(latest, "short_title_tesim") or
                        f"Media {latest_id}").strip()

    # Debug output
    print(f"[debug] latest_id type: {type(latest_id)}, value: '{latest_id}'", file=sys.stderr)
    print(f"[debug] latest_title: '{latest_title}'", file=sys.stderr)

    # Persist current count to file
    save_count_txt(total)

    # Load baseline (handles missing .txt case)
    old, baseline_source = load_baseline()
    if old is None:
        delta = total
        new_data = True  # force a release on missing baseline
        old_count_out = "0"
    else:
        delta = total - old
        new_data = delta > 0
        old_count_out = str(old)

    # Update durable baseline (so next run is differential)
    save_last_count(total)

    # Pretty JSON for latest record (truncated)
    if latest:
        raw = json.dumps(latest, indent=2, ensure_ascii=False)
        if len(raw) > MAX_JSON_CHARS:
            raw = raw[:MAX_JSON_CHARS] + "\n... [truncated]"
        latest_json_block = f"```json\n{raw}\n```"
    else:
        latest_json_block = "_No media records returned on page 1._"

    detail_url = f"https://www.morphosource.org/concern/media/{latest_id}" if latest_id else "(unknown)"

    body = "\n".join([
        f"Queried **/api/media** with: `utf8=✓&search_field={SEARCH_FIELD}&q={QUERY}&sort=system_create_dtsi desc`",
        f"**total_count**: **{total}**",
        "",
        f"Baseline source: _{baseline_source}_",
        f"Previous recorded total: {old_count_out}",
        f"New records since baseline: **{delta}**",
        "",
        "## Latest record (from this API page)",
        f"- **id:** `{latest_id}`",
        f"- **title:** {latest_title or '(none)'}",
        f"- **detail page:** {detail_url}",
        "",
        "### Full API JSON for latest record",
        latest_json_block,
    ])

    # Emit outputs - ensure all values are strings
    gh_set_outputs(
        new_data="true" if new_data else "false",
        details=body,
        count=str(total),
        old_count=old_count_out,
        delta=str(delta),
        latest_id=str(latest_id),
        latest_title=str(latest_title),
        baseline_source=baseline_source,
        first_run="true" if old is None else "false",
    )

    # Log current count for visibility
    print(f"[info] Current total_count: {total} | Baseline: {old_count_out} ({baseline_source}) | Δ: {delta}", file=sys.stderr)

if __name__ == "__main__":
    main()
