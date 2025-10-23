#!/usr/bin/env python3
"""
Fetch a single MorphoSource media by ID, decide Mesh vs CTImageSeries, then:
- Mesh: POST /api/download/{id} to get a download_url, download it, and save as artifact
- CTImageSeries: GET /api/media/{id}/iiif/manifest and save JSON as artifact

Extra debugging:
- Confirms valid HTTP/JSON for the given MEDIA_ID
- Saves request/response metadata (sanitized) and raw body preview
- Dumps full JSON payload & classification snapshot

Env:
  BASE_URL (default https://www.morphosource.org)
  MEDIA_ID (required)
  MORPHOSOURCE_API_KEY (required for protected endpoints)
  USE_STATEMENT, USE_CATEGORIES (pipe-separated), USE_CATEGORY_OTHER, AGREEMENTS_ACCEPTED
  ARTIFACT_DIR (default artifacts)
  DEBUG (default "1") -> verbose stderr + more files
  RAW_MAX_BYTES (default "262144") -> preview bytes for *_raw.txt files

Outputs (GITHUB_OUTPUT):
  media_type, action, result, artifact_dir, notes
"""

import os, sys, json, time, re
from typing import Any, Dict, Optional, Tuple, List
import requests
from urllib.parse import urlparse, unquote

# -------------------- config --------------------
BASE_URL = os.getenv("BASE_URL", "https://www.morphosource.org").rstrip("/")
MEDIA_ID = os.getenv("MEDIA_ID", "").strip()
API_KEY = os.getenv("MORPHOSOURCE_API_KEY", "").strip()

USE_STATEMENT = os.getenv("USE_STATEMENT", "I will use this data for research and educational purposes.").strip()
USE_CATEGORIES_RAW = os.getenv("USE_CATEGORIES", "Research").strip()
USE_CATEGORY_OTHER = os.getenv("USE_CATEGORY_OTHER", "").strip()
AGREEMENTS_ACCEPTED = os.getenv("AGREEMENTS_ACCEPTED", "true").lower() == "true"

ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", "artifacts").strip()
DEBUG = os.getenv("DEBUG", "1").lower() in ("1", "true", "yes", "y", "on")
RAW_MAX = int(os.getenv("RAW_MAX_BYTES", "262144"))

TIMEOUT = (5, 60)
MAX_TRIES = 4
RETRY_STATUS = {429, 500, 502, 503, 504}

# -------------------- utils --------------------
def dbg(msg: str):
    if DEBUG:
        print(f"[debug] {msg}", file=sys.stderr)

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

def scrub_headers(h: Dict[str, str]) -> Dict[str, str]:
    if not isinstance(h, dict):
        return {}
    redacted = {}
    for k, v in h.items():
        if k.lower() in ("authorization", "cookie", "proxy-authorization", "x-api-key"):
            redacted[k] = "***REDACTED***"
        else:
            redacted[k] = v
    return redacted

def dump_http_debug(resp: Optional[requests.Response], base_name: str):
    """Write request/response meta + a raw text preview to artifact dir."""
    try:
        info = {
            "request": {
                "method": getattr(resp.request, "method", None) if resp is not None else None,
                "url": getattr(resp.request, "url", None) if resp is not None else None,
                "headers": scrub_headers(dict(getattr(resp.request, "headers", {}) or {})) if resp is not None else {},
            },
            "response": {
                "url": getattr(resp, "url", None) if resp is not None else None,
                "status_code": getattr(resp, "status_code", None) if resp is not None else None,
                "reason": getattr(resp, "reason", None) if resp is not None else None,
                "headers": scrub_headers(dict(getattr(resp, "headers", {}) or {})) if resp is not None else {},
                "elapsed_seconds": (resp.elapsed.total_seconds() if (resp is not None and resp.elapsed) else None),
            }
        }
        with open(os.path.join(ARTIFACT_DIR, f"{base_name}_http_debug.json"), "w", encoding="utf-8") as fh:
            json.dump(info, fh, indent=2, ensure_ascii=False)

        # Raw body preview (text mode; OK for JSON & errors; binary downloads will look garbled but safe)
        if resp is not None:
            try:
                preview = resp.text[:RAW_MAX]
            except Exception:
                preview = ""
            with open(os.path.join(ARTIFACT_DIR, f"{base_name}_raw.txt"), "w", encoding="utf-8", errors="ignore") as fh:
                fh.write(preview)
    except Exception as e:
        dbg(f"dump_http_debug failed: {e}")

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
            dbg(f"network error on {method} {url}: {e}")
            if tries >= MAX_TRIES:
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
            print(f"[warn] HTTP {r.status_code} on {method} {url} (try {tries}/{MAX_TRIES}); sleeping {sleep}s", file=sys.stderr)
            time.sleep(sleep)
            continue
        return r
    return None

# ---------------- classification helpers ----------------
TYPE_FIELDS = [
    "media_type_ssim", "media_type_tesim", "media_type_ssi",
    "human_readable_media_type_ssim", "human_readable_media_type_tesim", "human_readable_media_type_ssi",
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

def unwrap_media(obj: Any) -> Optional[Dict[str, Any]]:
    """
    Accepts:
      { "response": { "media": {...} } }
      { "response": { "media": [...] } }
      { "response": { "docs":  [...] } }
      direct media dict with "id" and "has_model_ssim"
    """
    if not isinstance(obj, dict):
        return None
    r = obj.get("response")
    if isinstance(r, dict):
        if "media" in r:
            m = r["media"]
            if isinstance(m, dict): return m
            if isinstance(m, list) and m: return m[0]
        if "docs" in r and isinstance(r["docs"], list) and r["docs"]:
            return r["docs"][0]
    if obj.get("id") and (obj.get("has_model_ssim") or obj.get("human_readable_type_ssi") == "Media"):
        return obj
    return None

def classify_media_type(record: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    vals = [s.lower() for s in collect_values(record, TYPE_FIELDS)]
    raw_hint = ", ".join(sorted(set(vals))) if vals else "unknown"

    detail = {
        "fields_checked": TYPE_FIELDS,
        "values_collected": vals,
    }

    # Mesh signals
    if any(v == "mesh" for v in vals) or any("[mesh]" in v for v in vals):
        return "mesh", raw_hint, detail

    # CT signals
    if any(v == "ctimageseries" for v in vals) \
       or any("volumetric image series" in v for v in vals) \
       or any("[ctimageseries]" in v for v in vals) \
       or any(re.search(r"\[ct\]", v) for v in vals):
        return "ctimageseries", raw_hint, detail

    has_ct_modality = any("computed tomography" in v or v == "ct" for v in vals)
    has_slice_or_spacing = any(k in record for k in ["slice_thickness_tesim", "x_spacing_tesim", "y_spacing_tesim", "z_spacing_tesim"])
    has_count = bool(record.get("number_of_images_in_set_tesim"))
    if has_ct_modality and (has_slice_or_spacing or has_count):
        return "ctimageseries", raw_hint, detail

    return "other", raw_hint, detail

def parse_filename_from_headers(resp: requests.Response, fallback: str) -> str:
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", cd, flags=re.IGNORECASE)
    if m: return unquote(m.group(1))
    m = re.search(r'filename\s*=\s*"([^"]+)"', cd, flags=re.IGNORECASE)
    if m: return m.group(1)
    m = re.search(r'filename\s*=\s*([^;]+)', cd, flags=re.IGNORECASE)
    if m: return m.group(1).strip()
    try:
        base = os.path.basename(urlparse(resp.url).path)
        if base: return base
    except Exception:
        pass
    return fallback

# ---------------- main ----------------
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

    # Always dump HTTP debug
    dump_http_debug(r, f"media_{MEDIA_ID}")

    if not r or r.status_code >= 400:
        status = r.status_code if r else "no-response"
        msg = f"Failed to fetch media record {MEDIA_ID} (status={status})."
        print("[error]", msg, file=sys.stderr)
        with open(os.path.join(ARTIFACT_DIR, "error.json"), "w", encoding="utf-8") as fh:
            json.dump({"error": msg}, fh, indent=2)
        gh_set_outputs(media_type="unknown", action="lookup", result="failed", artifact_dir=ARTIFACT_DIR, notes=msg)
        return

    # Confirm it's JSON, and save the exact raw JSON too
    try:
        payload = r.json()
    except Exception as e:
        msg = f"Bad JSON from media record endpoint: {e}"
        print("[error]", msg, file=sys.stderr)
        with open(os.path.join(ARTIFACT_DIR, "media_raw.txt"), "w", encoding="utf-8") as fh:
            fh.write(r.text[:RAW_MAX] if r and r.text else msg)
        gh_set_outputs(media_type="unknown", action="lookup", result="failed", artifact_dir=ARTIFACT_DIR, notes=msg)
        return

    media = unwrap_media(payload) or {}
    with open(os.path.join(ARTIFACT_DIR, f"media_{MEDIA_ID}_raw.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    # Validate ID matches (best-effort)
    found_id = media.get("id")
    if isinstance(found_id, list) and found_id:
        found_id = found_id[0]
    id_match = (str(found_id) == MEDIA_ID)
    print(f"[info] Media ID in record: {found_id} | requested: {MEDIA_ID} | match={id_match}", file=sys.stderr)

    # Classify
    mtype, raw_hint, detail = classify_media_type(media)
    print(f"[info] Classified media_type={mtype} ({raw_hint})", file=sys.stderr)
    detail.update({"media_id_reported": found_id, "media_id_requested": MEDIA_ID, "id_match": id_match, "raw_hint": raw_hint})

    with open(os.path.join(ARTIFACT_DIR, f"classification_{MEDIA_ID}.json"), "w", encoding="utf-8") as fh:
        json.dump(detail, fh, indent=2, ensure_ascii=False)

    # ---------- Branch: Mesh ----------
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

        dump_http_debug(pr, f"mesh_{MEDIA_ID}_download_resp")

        if not pr or pr.status_code >= 400:
            status = pr.status_code if pr else "no-response"
            msg = f"Download request failed (status={status})."
            print("[error]", msg, file=sys.stderr)
            gh_set_outputs(media_type="mesh", action="download", result="failed", artifact_dir=ARTIFACT_DIR, notes=f"id_match={id_match}; download request failed")
            return

        try:
            dl_payload = pr.json()
        except Exception as e:
            msg = f"Bad JSON in download response: {e}"
            print("[error]", msg, file=sys.stderr)
            with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_response.txt"), "w", encoding="utf-8") as fh:
                fh.write(pr.text[:RAW_MAX] if pr and pr.text else "")
            gh_set_outputs(media_type="mesh", action="download", result="failed", artifact_dir=ARTIFACT_DIR, notes=f"id_match={id_match}; parse download response failed")
            return

        with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_response.json"), "w", encoding="utf-8") as fh:
            json.dump(dl_payload, fh, indent=2, ensure_ascii=False)

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
            gh_set_outputs(media_type="mesh", action="download", result="no-url", artifact_dir=ARTIFACT_DIR, notes=f"id_match={id_match}; no download_url")
            return

        # Download the asset
        print(f"[info] GET presigned {download_url}", file=sys.stderr)
        dr = backoff_request("GET", download_url, stream=True)
        # Headers only (avoid dumping binary body)
        dump_http_debug(dr, f"mesh_{MEDIA_ID}_download_file_headers")

        if not dr or dr.status_code >= 400:
            status = dr.status_code if dr else "no-response"
            msg = f"Failed to download file from pre-signed URL (status={status})."
            print("[error]", msg, file=sys.stderr)
            gh_set_outputs(media_type="mesh", action="download", result="failed", artifact_dir=ARTIFACT_DIR, notes=f"id_match={id_match}; presigned download failed")
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

        gh_set_outputs(media_type="mesh", action="download", result="success", artifact_dir=ARTIFACT_DIR, notes=f"id_match={id_match}; saved={fname}")
        print(f"[info] Downloaded {size} bytes to {out_path}", file=sys.stderr)
        return

    # ---------- Branch: CTImageSeries ----------
    if mtype == "ctimageseries":
        iiif_url = f"{BASE_URL}/api/media/{MEDIA_ID}/iiif/manifest"
        print(f"[info] GET {iiif_url} (IIIF manifest)", file=sys.stderr)
        ir = backoff_request("GET", iiif_url, headers=bearer_headers())
        if ir is not None and ir.status_code in (401, 403):
            print("[warn] bearer auth rejected on IIIF; retrying with raw token", file=sys.stderr)
            ir = backoff_request("GET", iiif_url, headers=raw_headers())

        dump_http_debug(ir, f"ct_{MEDIA_ID}_iiif")

        if not ir or ir.status_code >= 400:
            status = ir.status_code if ir else "no-response"
            msg = f"Failed to fetch IIIF manifest (status={status})."
            print("[error]", msg, file=sys.stderr)
            gh_set_outputs(media_type="ctimageseries", action="iiif", result="failed", artifact_dir=ARTIFACT_DIR, notes=f"id_match={id_match}; iiif fetch failed")
            return

        try:
            manifest = ir.json()
        except Exception as e:
            msg = f"Bad JSON in IIIF manifest response: {e}"
            print("[error]", msg, file=sys.stderr)
            gh_set_outputs(media_type="ctimageseries", action="iiif", result="failed", artifact_dir=ARTIFACT_DIR, notes=f"id_match={id_match}; iiif parse failed")
            return

        out_path = os.path.join(ARTIFACT_DIR, f"iiif_manifest_{MEDIA_ID}.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)

        gh_set_outputs(media_type="ctimageseries", action="iiif", result="success", artifact_dir=ARTIFACT_DIR, notes=f"id_match={id_match}; saved=iiif_manifest_{MEDIA_ID}.json")
        print(f"[info] Saved IIIF manifest to {out_path}", file=sys.stderr)
        return

    # ---------- Unknown ----------
    msg = f"Unhandled media type. (hint: {raw_hint})"
    print("[warn]", msg, file=sys.stderr)
    with open(os.path.join(ARTIFACT_DIR, f"media_{MEDIA_ID}_unhandled.txt"), "w", encoding="utf-8") as fh:
        fh.write(msg + "\n")
    gh_set_outputs(media_type="other", action="none", result="skipped", artifact_dir=ARTIFACT_DIR, notes=f"id_match={id_match}; {msg}")

if __name__ == "__main__":
    main()
