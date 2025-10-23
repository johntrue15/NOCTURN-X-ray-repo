#!/usr/bin/env python3
"""
Fetch a single MorphoSource media by ID, decide Mesh vs CTImageSeries, then:
- Mesh: POST /api/download/{id} to get a download_url, download it, and save as artifact
- CTImageSeries: GET /api/media/{id}/iiif/manifest and save JSON as artifact

Env (set in workflow or locally):
  BASE_URL (default https://www.morphosource.org)
  MEDIA_ID (required)
  MORPHOSOURCE_API_KEY (required for protected endpoints)
  USE_STATEMENT, USE_CATEGORIES (pipe-separated), USE_CATEGORY_OTHER, AGREEMENTS_ACCEPTED
  ARTIFACT_DIR (default artifacts)

Outputs (GITHUB_OUTPUT):
  media_type, action, result, artifact_dir, notes
"""

import os, sys, json, time, re
from typing import Any, Dict, Optional, Tuple, List
import requests
from urllib.parse import urlparse, unquote

BASE_URL = os.getenv("BASE_URL", "https://www.morphosource.org").rstrip("/")
MEDIA_ID = os.getenv("MEDIA_ID", "").strip()
API_KEY = os.getenv("MORPHOSOURCE_API_KEY", "").strip()

USE_STATEMENT = os.getenv("USE_STATEMENT", "I will use this data for research and educational purposes.").strip()
USE_CATEGORIES_RAW = os.getenv("USE_CATEGORIES", "Research").strip()
USE_CATEGORY_OTHER = os.getenv("USE_CATEGORY_OTHER", "").strip()
AGREEMENTS_ACCEPTED = os.getenv("AGREEMENTS_ACCEPTED", "true").lower() == "true"

ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", "artifacts").strip()

TIMEOUT = (5, 60)
MAX_TRIES = 4
RETRY_STATUS = {429, 500, 502, 503, 504}

def gh_set_outputs(**kv):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        for k, v in kv.items():
            s = "" if v is None else str(v)
            if "\n" in s:
                fh.write(f"{k}<<EOF\n{s}\nEOF\n")
            else:
                fh.write(f"{k}={s}\n")

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def bearer_headers() -> Dict[str, str]:
    h = {"Accept": "application/json"}
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    return h

def raw_headers() -> Dict[str, str]:
    h = {"Accept": "application/json"}
    if API_KEY:
        h["Authorization"] = API_KEY
    return h

def with_json(h: Dict[str, str]) -> Dict[str, str]:
    h = dict(h)
    h["Content-Type"] = "application/json"
    return h

def backoff_request(method: str, url: str, **kwargs) -> Optional[requests.Response]:
    tries = 0
    while tries < MAX_TRIES:
        tries += 1
        try:
            r = requests.request(method, url, timeout=TIMEOUT, **kwargs)
        except requests.RequestException as e:
            if tries >= MAX_TRIES:
                print(f"[error] network error: {e}", file=sys.stderr)
                return None
            sleep = min(60, 2 ** tries)
            print(f"[warn] network error (try {tries}/{MAX_TRIES}); sleeping {sleep}s", file=sys.stderr)
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
            print(f"[warn] HTTP {r.status_code} (try {tries}/{MAX_TRIES}); sleeping {sleep}s", file=sys.stderr)
            time.sleep(sleep)
            continue
        # Non-retryable error
        return r
    return None

def unwrap_media(obj: Any) -> Optional[Dict[str, Any]]:
    """
    Accepts shapes like:
      { "response": { "media": {...} } }
      { "response": { "media": [...] } }
      { "response": { "docs":  [...] } }   # some endpoints return 'docs'
      { "id": "...", "has_model_ssim": [...] }  # direct media doc
    """
    if not isinstance(obj, dict):
        return None
    r = obj.get("response")
    if isinstance(r, dict):
        if "media" in r:
            m = r["media"]
            if isinstance(m, dict):
                return m
            if isinstance(m, list) and m:
                return m[0]
        if "docs" in r and isinstance(r["docs"], list) and r["docs"]:
            return r["docs"][0]
    # Direct doc?
    if obj.get("id") and (obj.get("has_model_ssim") or obj.get("human_readable_type_ssi") == "Media"):
        return obj
    return None

# --- classification helpers ---------------------------------------------------

TYPE_FIELDS = [
    # canonical + common variants
    "media_type_ssim", "media_type_tesim", "media_type_ssi",
    "human_readable_media_type_ssim", "human_readable_media_type_tesim", "human_readable_media_type_ssi",
    # useful hints/fallbacks
    "title_ssi", "title_tesim",
    "modality_ssim", "human_readable_modality_tesim", "human_readable_modality_ssi",
    "number_of_images_in_set_tesim", "slice_thickness_tesim", "x_spacing_tesim", "y_spacing_tesim", "z_spacing_tesim",
]

def listify(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]

def collect_values(record: Dict[str, Any], keys: List[str]) -> List[str]:
    vals: List[str] = []
    for k in keys:
        if k in record:
            vals += [s.strip() for s in listify(record[k]) if str(s).strip()]
    return vals

def classify_media_type(record: Dict[str, Any]) -> Tuple[str, str]:
    """
    Returns (normalized, raw_hint)
    normalized in {"mesh", "ctimageseries", "other"}
    Heuristics:
      - explicit media_type/human_readable_media_type fields
      - title tags like [Mesh], [CTImageSeries], [CT]
      - CT-specific hints (IIIF + slice/spacing + modality)
    """
    vals = [s.lower() for s in collect_values(record, TYPE_FIELDS)]
    raw_hint = ", ".join(sorted(set(vals))) if vals else "unknown"

    # Explicit labels
    if any(v == "mesh" for v in vals) or any("mesh" == v.strip() for v in vals) or any("[mesh]" in v for v in vals):
        return "mesh", raw_hint

    if any(v == "ctimageseries" for v in vals) or \
       any("volumetric image series" in v for v in vals) or \
       any("[ctimageseries]" in v for v in vals) or \
       any(re.search(r"\[ct\]", v) for v in vals):
        return "ctimageseries", raw_hint

    # CT hints: modality mentions CT + has slice/spacing/num images
    has_ct_modality = any("computed tomography" in v or v == "ct" for v in vals)
    has_slice_or_spacing = any(k in record for k in ["slice_thickness_tesim", "x_spacing_tesim", "y_spacing_tesim", "z_spacing_tesim"])
    has_count = bool(record.get("number_of_images_in_set_tesim"))
    if has_ct_modality and (has_slice_or_spacing or has_count):
        return "ctimageseries", raw_hint

    return "other", raw_hint

def parse_filename_from_headers(resp: requests.Response, fallback: str) -> str:
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", cd, flags=re.IGNORECASE)
    if m:
        return unquote(m.group(1))
    m = re.search(r'filename\s*=\s*"([^"]+)"', cd, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'filename\s*=\s*([^;]+)', cd, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    try:
        path = urlparse(resp.url).path
        base = os.path.basename(path)
        if base:
            return base
    except Exception:
        pass
    return fallback

# --- main ---------------------------------------------------------------------

def main():
    ensure_dir(ARTIFACT_DIR)
    if not MEDIA_ID:
        msg = "MEDIA_ID is required."
        print("[error]", msg, file=sys.stderr)
        gh_set_outputs(media_type="unknown", action="none", result="failed", artifact_dir=ARTIFACT_DIR, notes=msg)
        with open(os.path.join(ARTIFACT_DIR, "README.txt"), "w", encoding="utf-8") as fh:
            fh.write(msg + "\n")
        sys.exit(1)

    media_url = f"{BASE_URL}/api/media/{MEDIA_ID}"
    print(f"[info] GET {media_url}", file=sys.stderr)
    r = backoff_request("GET", media_url, headers=bearer_headers())
    if r is not None and r.status_code in (401, 403):
        print("[warn] bearer auth rejected; retrying with raw token", file=sys.stderr)
        r = backoff_request("GET", media_url, headers=raw_headers())
    if not r or r.status_code >= 400:
        status = r.status_code if r else "no-response"
        text_preview = (r.text[:300] if r and r.text else "")
        msg = f"Failed to fetch media record {MEDIA_ID} (status={status}). {text_preview}"
        print("[error]", msg, file=sys.stderr)
        with open(os.path.join(ARTIFACT_DIR, "error.json"), "w", encoding="utf-8") as fh:
            json.dump({"error": msg}, fh, indent=2)
        gh_set_outputs(media_type="unknown", action="lookup", result="failed", artifact_dir=ARTIFACT_DIR, notes=msg)
        return

    # Save raw payload for inspection
    try:
        payload = r.json()
    except Exception as e:
        msg = f"Bad JSON from media record endpoint: {e}"
        print("[error]", msg, file=sys.stderr)
        with open(os.path.join(ARTIFACT_DIR, "media_raw.txt"), "w", encoding="utf-8") as fh:
            fh.write(r.text[:4000] if r and r.text else msg)
        gh_set_outputs(media_type="unknown", action="lookup", result="failed", artifact_dir=ARTIFACT_DIR, notes=msg)
        return

    media = unwrap_media(payload) or {}
    with open(os.path.join(ARTIFACT_DIR, f"media_{MEDIA_ID}_raw.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    mtype, raw_hint = classify_media_type(media)
    print(f"[info] Classified media_type={mtype} ({raw_hint})", file=sys.stderr)

    # If still unknown, dump the exact type-related fields for debugging
    if mtype == "other":
        snap = {k: media.get(k) for k in TYPE_FIELDS if k in media}
        snap["_keys_present"] = sorted(list(media.keys()))
        with open(os.path.join(ARTIFACT_DIR, f"media_{MEDIA_ID}_type_snapshot.json"), "w", encoding="utf-8") as fh:
            json.dump(snap, fh, indent=2, ensure_ascii=False)

    # --- Branch by type -------------------------------------------------------
    if mtype == "mesh":
        post_url = f"{BASE_URL}/api/download/{MEDIA_ID}"
        body = {
            "use_statement": USE_STATEMENT,
            "use_categories": [c.strip() for c in USE_CATEGORIES_RAW.split("|") if c.strip()],
            "use_category_other": USE_CATEGORY_OTHER,
            "agreements_accepted": AGREEMENTS_ACCEPTED,
        }
        print(f"[info] POST {post_url} (requesting download_url)", file=sys.stderr)

        pr = backoff_request("POST", post_url, headers=with_json(bearer_headers()), json=body)
        if pr is not None and pr.status_code in (401, 403):
            print("[warn] bearer auth rejected on download; retrying with raw token", file=sys.stderr)
            pr = backoff_request("POST", post_url, headers=with_json(raw_headers()), json=body)

        if not pr or pr.status_code >= 400:
            status = pr.status_code if pr else "no-response"
            msg = f"Download request failed (status={status})."
            print("[error]", msg, file=sys.stderr)
            with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_error.txt"), "w", encoding="utf-8") as fh:
                fh.write(msg + "\n" + (pr.text[:4000] if pr and pr.text else ""))
            gh_set_outputs(media_type="mesh", action="download", result="failed", artifact_dir=ARTIFACT_DIR, notes="download request failed")
            return

        try:
            dl_payload = pr.json()
        except Exception as e:
            msg = f"Bad JSON in download response: {e}"
            print("[error]", msg, file=sys.stderr)
            with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_response.txt"), "w", encoding="utf-8") as fh:
                fh.write(pr.text[:4000] if pr and pr.text else "")
            gh_set_outputs(media_type="mesh", action="download", result="failed", artifact_dir=ARTIFACT_DIR, notes="parse download response failed")
            return

        # Extract download_url
        download_url = None
        try:
            media_node = dl_payload.get("response", {}).get("media", {})
            if isinstance(media_node, dict):
                urls = media_node.get("download_url")
                if isinstance(urls, list) and urls:
                    download_url = urls[0]
                elif isinstance(urls, str):
                    download_url = urls
        except Exception:
            pass

        if not download_url:
            msg = "No download_url returned (may require approval or restricted access)."
            print("[warn]", msg, file=sys.stderr)
            with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_no_download_url.json"), "w", encoding="utf-8") as fh:
                json.dump(dl_payload, fh, indent=2, ensure_ascii=False)
            gh_set_outputs(media_type="mesh", action="download", result="no-url", artifact_dir=ARTIFACT_DIR, notes="no download_url")
            return

        print(f"[info] GET {download_url}", file=sys.stderr)
        dr = backoff_request("GET", download_url, stream=True)
        if not dr or dr.status_code >= 400:
            status = dr.status_code if dr else "no-response"
            msg = f"Failed to download file from pre-signed URL (status={status})."
            print("[error]", msg, file=sys.stderr)
            with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_url.txt"), "w", encoding="utf-8") as fh:
                fh.write(download_url + "\n")
            gh_set_outputs(media_type="mesh", action="download", result="failed", artifact_dir=ARTIFACT_DIR, notes="presigned download failed")
            return

        fname = parse_filename_from_headers(dr, f"media_{MEDIA_ID}.bin")
        out_path = os.path.join(ARTIFACT_DIR, fname)
        size = 0
        with open(out_path, "wb") as fh:
            for chunk in dr.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)
                    size += len(chunk)

        with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_info.json"), "w", encoding="utf-8") as fh:
            json.dump({"media_id": MEDIA_ID, "download_url": download_url, "filename": fname, "size_bytes": size}, fh, indent=2)

        gh_set_outputs(media_type="mesh", action="download", result="success", artifact_dir=ARTIFACT_DIR, notes=f"saved={fname}")
        print(f"[info] Downloaded {size} bytes to {out_path}", file=sys.stderr)
        return

    elif mtype == "ctimageseries":
        iiif_url = f"{BASE_URL}/api/media/{MEDIA_ID}/iiif/manifest"
        print(f"[info] GET {iiif_url} (IIIF manifest)", file=sys.stderr)
        ir = backoff_request("GET", iiif_url, headers=bearer_headers())
        if ir is not None and ir.status_code in (401, 403):
            print("[warn] bearer auth rejected on IIIF; retrying with raw token", file=sys.stderr)
            ir = backoff_request("GET", iiif_url, headers=raw_headers())

        if not ir or ir.status_code >= 400:
            status = ir.status_code if ir else "no-response"
            msg = f"Failed to fetch IIIF manifest (status={status})."
            print("[error]", msg, file=sys.stderr)
            with open(os.path.join(ARTIFACT_DIR, f"ct_{MEDIA_ID}_iiif_error.txt"), "w", encoding="utf-8") as fh:
                fh.write(msg + "\n" + (ir.text[:4000] if ir and ir.text else ""))
            gh_set_outputs(media_type="ctimageseries", action="iiif", result="failed", artifact_dir=ARTIFACT_DIR, notes="iiif fetch failed")
            return

        try:
            manifest = ir.json()
        except Exception as e:
            msg = f"Bad JSON in IIIF manifest response: {e}"
            print("[error]", msg, file=sys.stderr)
            with open(os.path.join(ARTIFACT_DIR, f"ct_{MEDIA_ID}_iiif_response.txt"), "w", encoding="utf-8") as fh:
                fh.write(ir.text[:4000] if ir and ir.text else "")
            gh_set_outputs(media_type="ctimageseries", action="iiif", result="failed", artifact_dir=ARTIFACT_DIR, notes="iiif parse failed")
            return

        out_path = os.path.join(ARTIFACT_DIR, f"iiif_manifest_{MEDIA_ID}.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)

        gh_set_outputs(media_type="ctimageseries", action="iiif", result="success", artifact_dir=ARTIFACT_DIR, notes=f"saved=iiif_manifest_{MEDIA_ID}.json")
        print(f"[info] Saved IIIF manifest to {out_path}", file=sys.stderr)
        return

    # Unknown
    msg = f"Unhandled media type. ({raw_hint})"
    print("[warn]", msg, file=sys.stderr)
    with open(os.path.join(ARTIFACT_DIR, f"media_{MEDIA_ID}_unhandled.txt"), "w", encoding="utf-8") as fh:
        fh.write(msg + "\n")
    gh_set_outputs(media_type="other", action="none", result="skipped", artifact_dir=ARTIFACT_DIR, notes=msg)

if __name__ == "__main__":
    main()
