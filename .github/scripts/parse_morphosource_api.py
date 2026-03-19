#!/usr/bin/env python3
"""
Queries:
  https://www.morphosource.org/api/media?utf8=✓&search_field=all_fields&q=<QUERY>&sort=system_create_dtsi+desc

When new records are detected (total_count > baseline), fetches ALL new
records across multiple API pages and includes their full JSON in the
release body so downstream CT-to-Text can analyse every one.

Outputs:
  - count (current total_count)
  - old_count (baseline)
  - delta (count - old_count, or =count if baseline missing)
  - new_data ("true" if delta>0 OR first run; else "false")
  - latest_id, latest_title
  - baseline_source ("last_count.txt" | "count_outfile" | "missing")
  - records_fetched (number of new record JSONs included in release body)

Writes:
  - .github/last_count.txt (state)
  - morphosource_xray_count.txt (current count)
  - Rich release body with ALL new records' JSON
"""

import os, sys, time, json, requests
from typing import Optional, Dict, Any, Tuple, List

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
MAX_RECORDS_TO_FETCH = 50   # safety cap per run

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
    if os.path.exists(LAST_COUNT_FILE):
        try:
            with open(LAST_COUNT_FILE, "r") as f:
                return int(f.read().strip()), "last_count.txt"
        except Exception:
            pass
    if os.path.exists(COUNT_OUTFILE):
        try:
            with open(COUNT_OUTFILE, "r") as f:
                return int(f.read().strip()), "count_outfile"
        except Exception:
            pass
    return None, "missing"

def save_last_count(n: int):
    os.makedirs(os.path.dirname(LAST_COUNT_FILE), exist_ok=True)
    with open(LAST_COUNT_FILE, "w") as f:
        f.write(str(int(n)))

def save_count_txt(n: int):
    with open(COUNT_OUTFILE, "w") as f:
        f.write(str(int(n)))

def api_headers() -> Dict[str, str]:
    h = {"Accept": "application/json"}
    if API_KEY: h["Authorization"] = f"Bearer {API_KEY}"
    return h

def request_with_backoff(url: str, params: dict) -> Optional[requests.Response]:
    tries = 0
    while tries < MAX_TRIES:
        tries += 1
        try:
            r = requests.get(url, headers=api_headers(), params=params, timeout=TIMEOUT)
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

def get_media_list(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        media = payload.get("response", {}).get("media", [])
        return media if isinstance(media, list) else []
    except Exception:
        return []

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

def extract_id(record: Dict[str, Any]) -> str:
    id_value = record.get("id", "")
    if isinstance(id_value, list):
        return str(id_value[0]) if id_value else ""
    return str(id_value) if id_value else ""


def fetch_new_records(delta: int) -> List[Dict[str, Any]]:
    """
    Fetch up to `delta` new records from the API (sorted newest-first).
    Pages through results if needed.
    """
    to_fetch = min(delta, MAX_RECORDS_TO_FETCH)
    collected: List[Dict[str, Any]] = []
    page = 1
    per_page = min(to_fetch, 20)  # MorphoSource typical page size

    while len(collected) < to_fetch:
        params = {
            "utf8": UTF8_CHK,
            "search_field": SEARCH_FIELD,
            "q": QUERY,
            "sort": "system_create_dtsi desc",
            "page": str(page),
        }
        r = request_with_backoff(BASE_URL, params)
        if not r:
            print(f"[warn] Failed to fetch page {page}, stopping", file=sys.stderr)
            break
        try:
            data = r.json()
        except Exception:
            break

        media = get_media_list(data)
        if not media:
            break

        for record in media:
            collected.append(record)
            if len(collected) >= to_fetch:
                break

        page += 1
        time.sleep(0.5)  # polite pause between pages

    print(f"[info] Fetched {len(collected)} new record(s) across {page - 1} page(s)", file=sys.stderr)
    return collected


def build_record_section(record: Dict[str, Any], index: int) -> str:
    """Build a markdown section for a single record with its full JSON."""
    rec_id = extract_id(record)
    title = (first_text(record, "title_ssi", "title_tesim") or
             first_text(record, "short_title_tesim") or
             f"Media {rec_id}")

    vis_raw = record.get("visibility_ssi") or record.get("visibility")
    if isinstance(vis_raw, list):
        visibility = vis_raw[0] if vis_raw else "unknown"
    elif isinstance(vis_raw, str):
        visibility = vis_raw
    else:
        visibility = "unknown"

    detail_url = f"https://www.morphosource.org/concern/media/{rec_id}" if rec_id else "(unknown)"

    raw_json = json.dumps(record, indent=2, ensure_ascii=False)
    if len(raw_json) > MAX_JSON_CHARS:
        raw_json = raw_json[:MAX_JSON_CHARS] + "\n... [truncated]"

    return "\n".join([
        f"## Record {index}: `{rec_id}`",
        f"- **id:** `{rec_id}`",
        f"- **title:** {title}",
        f"- **visibility:** {visibility}",
        f"- **detail page:** {detail_url}",
        "",
        f"### Full API JSON for record {rec_id}",
        f"```json\n{raw_json}\n```",
        "",
    ])


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

    # Get the first page of media for the latest record info
    first_page_media = get_media_list(data)

    # Persist current count to file
    save_count_txt(total)

    # Load baseline
    old, baseline_source = load_baseline()
    if old is None:
        delta = total
        new_data = True
        old_count_out = "0"
    else:
        delta = total - old
        new_data = delta > 0
        old_count_out = str(old)

    # Update baseline
    save_last_count(total)

    # ── Determine latest_id for tag naming ──────────────────────────
    latest_id = ""
    latest_title = ""
    if first_page_media:
        latest = first_page_media[0]
        latest_id = extract_id(latest)
        latest_title = (first_text(latest, "title_ssi", "title_tesim") or
                        first_text(latest, "short_title_tesim") or
                        f"Media {latest_id}").strip()

    if not latest_id or latest_id == "None":
        latest_id = f"unknown-{int(time.time())}"
        print(f"[warn] No valid media ID found, using fallback: {latest_id}", file=sys.stderr)

    print(f"[debug] latest_id: '{latest_id}', latest_title: '{latest_title}'", file=sys.stderr)

    # ── Build the release body ──────────────────────────────────────
    if new_data and delta > 0:
        # Fetch ALL new records (across pages if needed)
        if delta <= len(first_page_media):
            # All new records are on the first page we already fetched
            new_records = first_page_media[:delta]
            print(f"[info] All {delta} new records found on first page", file=sys.stderr)
        else:
            # Need to page through the API
            new_records = fetch_new_records(delta)

        records_fetched = len(new_records)
        print(f"[info] Including {records_fetched} record(s) in release body", file=sys.stderr)

        record_sections = []
        for i, rec in enumerate(new_records, 1):
            record_sections.append(build_record_section(rec, i))

        body = "\n".join([
            f"Queried **/api/media** with: `utf8=✓&search_field={SEARCH_FIELD}&q={QUERY}&sort=system_create_dtsi desc`",
            f"**total_count**: **{total}**",
            "",
            f"Baseline source: _{baseline_source}_",
            f"Previous recorded total: {old_count_out}",
            f"New records since baseline: **{delta}**",
            f"Records included in this release: **{records_fetched}**",
            "",
            "---",
            "",
            *record_sections,
        ])
    else:
        # No new data — still include latest record for reference
        if first_page_media:
            latest = first_page_media[0]
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
        records_fetched = 0

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
        records_fetched=str(records_fetched),
    )

    print(f"[info] Current total_count: {total} | Baseline: {old_count_out} ({baseline_source}) | Δ: {delta} | Records: {records_fetched}", file=sys.stderr)

if __name__ == "__main__":
    main()
