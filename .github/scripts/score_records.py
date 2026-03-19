#!/usr/bin/env python3
"""
Score recent CT-to-Text analysis releases and pick the most interesting
record for daily deep analysis (MorphoSource download + SlicerMorph).

Only records with **open** visibility on MorphoSource are eligible.
The script walks the ranked candidate list and verifies each against the
MorphoSource API until it finds one that is confirmed downloadable.

Outputs GitHub Actions outputs:
  - best_media_id:   MorphoSource media ID of the top record
  - best_tag:        release tag of the corresponding ct_to_text_analysis
  - best_score:      numeric score
  - has_candidate:   "true" / "false"
  - candidates_json: JSON array of all scored candidates (for debugging)
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]


REPO = os.environ.get("GITHUB_REPOSITORY", "johntrue15/NOCTURN-X-ray-repo")
GH_TOKEN = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
ANALYZED_FILE = os.environ.get("ANALYZED_FILE", ".github/analyzed_records.txt")
BLACKLIST_FILE = os.environ.get("BLACKLIST_FILE", ".github/blacklist.txt")
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "48"))
MORPHOSOURCE_API_KEY = os.environ.get("MORPHOSOURCE_API_KEY", "").strip()
MAX_API_CHECKS = int(os.environ.get("MAX_API_CHECKS", "10"))

MORPHOSOURCE_BASE = "https://www.morphosource.org/api"


# ──────────────────────────── helpers ────────────────────────────────

def gh_api(endpoint: str):
    """Call GitHub API via the gh CLI and return parsed JSON."""
    cmd = [
        "gh", "api",
        "-H", "Accept: application/vnd.github+json",
        endpoint,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"gh api error: {result.stderr}", file=sys.stderr)
        return None
    return json.loads(result.stdout)


def load_analyzed_ids() -> set:
    ids = set()
    if os.path.exists(ANALYZED_FILE):
        with open(ANALYZED_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    ids.add(line)
    return ids


def load_blacklist() -> list[str]:
    names = []
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    names.append(line)
    return names


def set_output(name: str, value: str):
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{name}={value}\n")
    print(f"  OUTPUT {name}={value}")


# ──────────────────── visibility from release body ──────────────────

def extract_visibility_from_body(body: str) -> str | None:
    """
    Pull the visibility value out of a release body.  Works for both the
    ct_to_text_analysis body and the morphosource-api release body which
    embeds the full API JSON.
    """
    patterns = [
        r'"visibility"\s*:\s*\[\s*"([^"]+)"\s*\]',  # "visibility": ["open"]
        r'"visibility"\s*:\s*"([^"]+)"',              # "visibility": "open"
        r'"visibility_ssi"\s*:\s*\[\s*"([^"]+)"\s*\]',
        r'"visibility_ssi"\s*:\s*"([^"]+)"',
        r'(?:Visibility|visibility):\s*(\w+)',         # plain text
    ]
    for pat in patterns:
        m = re.search(pat, body)
        if m:
            return m.group(1).strip().lower()
    return None


def extract_media_id_from_tag(tag: str) -> str | None:
    m = re.search(r"morphosource-api-(\d{6,12})-", tag)
    return m.group(1) if m else None


def extract_media_id_from_body(body: str) -> str | None:
    patterns = [
        r'"id"\s*:\s*\[\s*"(\d{6,12})"\s*\]',       # "id": ["000791519"]
        r'"id"\s*:\s*"(\d{6,12})"',                   # "id": "000791519"
        r'"media_id"\s*:\s*"?(\d{6,12})"?',
        r"Media ID:\s*(\d{6,12})",
        r"Record #(\d{4,12})",
        r"media/(\d{6,12})",
    ]
    for pat in patterns:
        m = re.search(pat, body)
        if m:
            return m.group(1)
    return None


# ──────────────────── MorphoSource API verification ─────────────────

def verify_open_on_morphosource(media_id: str) -> tuple[bool, str]:
    """
    Call GET /api/media/{id} to verify the record exists and is open.

    Returns (is_open, reason).
    """
    if requests is None:
        return True, "requests not installed; skipping API check"

    url = f"{MORPHOSOURCE_BASE}/media/{media_id}"
    headers = {"Accept": "application/json"}
    if MORPHOSOURCE_API_KEY:
        headers["Authorization"] = MORPHOSOURCE_API_KEY

    try:
        resp = requests.get(url, headers=headers, timeout=(10, 30))
    except requests.RequestException as e:
        return False, f"API request failed: {e}"

    if resp.status_code == 404:
        return False, "record not found (404)"
    if resp.status_code != 200:
        return False, f"API returned HTTP {resp.status_code}"

    try:
        data = resp.json()
    except ValueError:
        return False, "invalid JSON from API"

    response_obj = data.get("response", data)
    if isinstance(response_obj, dict):
        vis_raw = response_obj.get("visibility_ssi") or response_obj.get("visibility")
        if isinstance(vis_raw, list):
            vis = vis_raw[0].lower() if vis_raw else ""
        elif isinstance(vis_raw, str):
            vis = vis_raw.lower()
        else:
            vis = ""
    else:
        vis = ""

    if not vis:
        return False, "could not determine visibility from API"

    if vis == "open":
        return True, "open"

    return False, f"visibility is '{vis}' (not open)"


# ──────────────────── scoring ───────────────────────────────────────

def score_record(release: dict, blacklist: list[str]) -> float:
    """
    Score a ct_to_text_analysis release on 0-100 scale.

    Dimensions:
      - body_length      (0-25): longer analysis = richer content
      - field_count       (0-25): more metadata fields mentioned
      - taxonomy_present  (0-20): has taxonomic identification
      - not_blacklisted   (0-15): passes blacklist check
      - has_media_id      (0-15): can be downloaded
    """
    body = release.get("body", "") or ""
    score = 0.0

    length = len(body)
    if length > 3000:
        score += 25
    elif length > 1500:
        score += 20
    elif length > 500:
        score += 12
    elif length > 100:
        score += 5

    metadata_keywords = [
        "specimen", "taxonomy", "modality", "voxel", "resolution",
        "institution", "scan", "element", "body region", "ct",
        "species", "genus", "family", "order", "class",
    ]
    found = sum(1 for kw in metadata_keywords if kw.lower() in body.lower())
    score += min(25, found * 2.5)

    taxonomy_indicators = [
        r"[A-Z][a-z]+ [a-z]+",
        r"(?:species|genus|family|order):\s*\S+",
    ]
    for pat in taxonomy_indicators:
        if re.search(pat, body):
            score += 10
            break

    if re.search(
        r"(?:Animalia|Vertebrata|Mammalia|Reptilia|Aves|Amphibia|Insecta|Plantae)",
        body,
        re.IGNORECASE,
    ):
        score += 10

    is_blacklisted = any(bl.lower() in body.lower() for bl in blacklist)
    if not is_blacklisted:
        score += 15

    media_id = extract_media_id_from_body(body)
    if not media_id:
        tag = release.get("tag_name", "")
        media_id = extract_media_id_from_tag(tag)
    if media_id:
        score += 15

    return score


def find_source_morphosource_tag(ct_release: dict) -> str | None:
    ct_tag = ct_release.get("tag_name", "")
    m = re.search(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})", ct_tag)
    return m.group(1) if m else None


# ──────────────────── main ──────────────────────────────────────────

def main():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    analyzed_ids = load_analyzed_ids()
    blacklist = load_blacklist()

    print(f"Looking back {LOOKBACK_HOURS}h (since {cutoff.isoformat()})")
    print(f"Already analyzed: {len(analyzed_ids)} records")

    releases = gh_api(f"/repos/{REPO}/releases?per_page=100")
    if not releases:
        print("No releases found")
        set_output("has_candidate", "false")
        return

    # ── collect CT-to-Text releases in the lookback window ──────────
    ct_releases = []
    for r in releases:
        tag = r.get("tag_name", "")
        if not tag.startswith("ct_to_text_analysis-"):
            continue
        created = r.get("created_at", "")
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if created_dt >= cutoff:
            ct_releases.append(r)

    print(f"Found {len(ct_releases)} CT-to-Text releases in lookback window")

    if not ct_releases:
        all_ct = [
            r for r in releases
            if r.get("tag_name", "").startswith("ct_to_text_analysis-")
        ]
        ct_releases = sorted(
            all_ct, key=lambda r: r.get("created_at", ""), reverse=True
        )[:10]
        print(f"No recent releases; falling back to {len(ct_releases)} most recent")

    ms_releases = [
        rel for rel in releases
        if rel.get("tag_name", "").startswith("morphosource-api-")
    ]

    # ── score and filter candidates ─────────────────────────────────
    candidates = []
    for r in ct_releases:
        body = r.get("body", "") or ""
        media_id = extract_media_id_from_body(body)

        # try to resolve media_id from the source morphosource-api release
        source_ms_body = ""
        if not media_id:
            ts = find_source_morphosource_tag(r)
            if ts:
                for ms in ms_releases:
                    if ts in ms.get("tag_name", ""):
                        source_ms_body = ms.get("body", "") or ""
                        media_id = extract_media_id_from_body(source_ms_body)
                        if media_id:
                            break

        if not media_id:
            print(f"  Skip {r['tag_name']}: no media ID found")
            continue

        if media_id in analyzed_ids:
            print(f"  Skip {r['tag_name']}: media {media_id} already analyzed")
            continue

        # ── fast visibility check from release body text ────────────
        vis = extract_visibility_from_body(body)
        if vis is None and source_ms_body:
            vis = extract_visibility_from_body(source_ms_body)
        if vis is None:
            # look in the matching morphosource-api release if we haven't yet
            for ms in ms_releases:
                if media_id in ms.get("tag_name", ""):
                    vis = extract_visibility_from_body(ms.get("body", "") or "")
                    if vis:
                        break

        if vis and vis != "open":
            print(f"  Skip {r['tag_name']}: media {media_id} visibility='{vis}' (not open)")
            continue

        s = score_record(r, blacklist)
        candidates.append({
            "tag": r["tag_name"],
            "media_id": media_id,
            "score": s,
            "created_at": r.get("created_at", ""),
            "body_visibility": vis or "unknown",
        })
        print(f"  Candidate: {r['tag_name']} media={media_id} vis={vis or '?'} score={s:.1f}")

    if not candidates:
        print("No viable candidates found")
        set_output("has_candidate", "false")
        return

    # sort by score descending
    candidates.sort(key=lambda c: c["score"], reverse=True)

    # ── verify candidates against MorphoSource API ──────────────────
    print(f"\nVerifying top {min(MAX_API_CHECKS, len(candidates))} candidates via MorphoSource API...")
    best = None
    for i, c in enumerate(candidates[:MAX_API_CHECKS]):
        is_open, reason = verify_open_on_morphosource(c["media_id"])
        print(f"  [{i+1}] media {c['media_id']} -> {reason}")

        if is_open:
            best = c
            break

        # brief pause between API calls to be polite
        if i < MAX_API_CHECKS - 1:
            time.sleep(1)

    if not best:
        print("No candidates passed MorphoSource API open-download verification")
        set_output("has_candidate", "false")
        # still emit the full list for debugging
        set_output("candidates_json", json.dumps(
            [{"media_id": c["media_id"], "score": c["score"], "vis": c["body_visibility"]}
             for c in candidates[:10]],
        ))
        return

    print(f"\nSelected: {best['tag']} (media {best['media_id']}, score {best['score']:.1f})")

    set_output("has_candidate", "true")
    set_output("best_media_id", best["media_id"])
    set_output("best_tag", best["tag"])
    set_output("best_score", str(best["score"]))
    set_output("candidates_json", json.dumps(
        [{"media_id": c["media_id"], "score": c["score"], "vis": c["body_visibility"]}
         for c in candidates[:10]],
    ))


if __name__ == "__main__":
    main()
