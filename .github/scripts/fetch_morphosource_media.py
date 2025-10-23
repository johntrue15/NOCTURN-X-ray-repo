#!/usr/bin/env python3
"""
Fetch a MorphoSource media by ID, decide Mesh vs CTImageSeries, then:
- Mesh -> POST /api/download/{id} to obtain a presigned download_url; download & save.
- CTImageSeries -> GET /api/media/{id}/iiif/manifest; save JSON.

Hardened debug + retries:
- Logs every request/response (sanitized headers), elapsed, and raw body previews.
- Tries multiple auth variants in order (AUTH_ORDER env): raw,bearer,token,token_noquotes.
- Optional SSL verification toggle (VERIFY_SSL) for diagnosing TLS issues.
- If 400 due to invalid use_categories, auto-retry with use_category_other only.
- Saves exceptions (trace/message) as files so "no-response" is explained.

Env:
  BASE_URL (default https://www.morphosource.org)
  MEDIA_ID (required)
  MORPHOSOURCE_API_KEY (recommended)
  AUTH_ORDER (default "raw,bearer,token,token_noquotes")
  VERIFY_SSL ("true" | "false", default "true")
  EXTRA_HEADERS_JSON (optional JSON -> merged into request headers)

  USE_STATEMENT, USE_CATEGORIES, USE_CATEGORY_OTHER, AGREEMENTS_ACCEPTED
  ARTIFACT_DIR (default "artifacts")
  DEBUG (default "1"), RAW_MAX_BYTES (default "262144")
  FALLBACK_TO_OTHER (default "1")
"""

import os, sys, json, time, re, traceback
from typing import Any, Dict, Optional, Tuple, List
import requests
from urllib.parse import urlparse, unquote

# -------------------- config --------------------
BASE_URL = os.getenv("BASE_URL", "https://www.morphosource.org").rstrip("/")
MEDIA_ID = os.getenv("MEDIA_ID", "").strip()
API_KEY = os.getenv("MORPHOSOURCE_API_KEY", "").strip()

AUTH_ORDER = [s.strip().lower() for s in (os.getenv("AUTH_ORDER", "raw,bearer,token,token_noquotes")).split(",") if s.strip()]
VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() in ("1","true","yes","on")
EXTRA_HEADERS_JSON = os.getenv("EXTRA_HEADERS_JSON", "").strip()

USE_STATEMENT = os.getenv("USE_STATEMENT", "Downloading this data as part of a research project.").strip()
USE_CATEGORIES_RAW = os.getenv("USE_CATEGORIES", "Research").strip()
USE_CATEGORY_OTHER = os.getenv("USE_CATEGORY_OTHER", "").strip()
AGREEMENTS_ACCEPTED = os.getenv("AGREEMENTS_ACCEPTED", "true").lower() == "true"

ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", "artifacts").strip()
DEBUG = os.getenv("DEBUG", "1").lower() in ("1", "true", "yes", "y", "on")
RAW_MAX = int(os.getenv("RAW_MAX_BYTES", "262144"))
FALLBACK_TO_OTHER = os.getenv("FALLBACK_TO_OTHER", "1").lower() in ("1", "true", "yes", "y", "on")

TIMEOUT = (5, 60)
MAX_TRIES = 4
RETRY_STATUS = {429, 500, 502, 503, 504}

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

def write_exception(base_name: str, err: Exception):
    info = {
        "type": type(err).__name__,
        "message": str(err),
        "traceback": traceback.format_exc(),
    }
    with open(os.path.join(ARTIFACT_DIR, f"{base_name}_exception.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=2, ensure_ascii=False)

def dump_http_debug(resp: Optional[requests.Response], base_name: str):
    """Write request/response meta + raw preview to artifact dir."""
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

        if resp is not None:
            try:
                preview = resp.text[:RAW_MAX]
            except Exception:
                preview = ""
            with open(os.path.join(ARTIFACT_DIR, f"{base_name}_raw.txt"), "w", encoding="utf-8", errors="ignore") as fh:
                fh.write(preview)
    except Exception as e:
        dbg(f"dump_http_debug failed: {e}")

def merge_extra_headers(h: Dict[str,str]) -> Dict[str,str]:
    if not EXTRA_HEADERS_JSON:
        return h
    try:
        extra = json.loads(EXTRA_HEADERS_JSON)
        if isinstance(extra, dict):
            merged = dict(h)
            for k,v in extra.items():
                if isinstance(v, str):
                    merged[k] = v
            return merged
    except Exception as e:
        dbg(f"EXTRA_HEADERS_JSON parse error: {e}")
    return h

def base_headers(accept_json=True) -> Dict[str,str]:
    h = {"Accept": "application/json" if accept_json else "*/*"}
    return merge_extra_headers(h)

def headers_for_auth(mode: str, accept_json=True) -> Dict[str,str]:
    h = base_headers(accept_json=accept_json)
    if mode == "bearer" and API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    elif mode == "raw" and API_KEY:
        h["Authorization"] = API_KEY
    elif mode == "token" and API_KEY:
        h["Authorization"] = f'Token token="{API_KEY}"'
    elif mode == "token_noquotes" and API_KEY:
        h["Authorization"] = f"Token token={API_KEY}"
    return h

def with_json(h: Dict[str,str]) -> Dict[str,str]:
    h = dict(h)
    h["Content-Type"] = "application/json"
    return h

def backoff_request(method: str, url: str, **kwargs) -> Tuple[Optional[requests.Response], Optional[Exception]]:
    tries = 0
    last_exc: Optional[Exception] = None
    while tries < MAX_TRIES:
        tries += 1
        try:
            r = requests.request(method, url, timeout=TIMEOUT, verify=VERIFY_SSL, **kwargs)
        except requests.RequestException as e:
            last_exc = e
            dbg(f"{method} {url} network error (try {tries}/{MAX_TRIES}): {e}")
            if tries >= MAX_TRIES:
                return None, e
            sleep = min(60, 2 ** tries)
            print(f"[warn] network error (try {tries}/{MAX_TRIES}); sleeping {sleep}s", file=sys.stderr)
            time.sleep(sleep)
            continue
        if r.status_code < 400:
            return r, None
        if r.status_code in RETRY_STATUS and tries < MAX_TRIES:
            ra = r.headers.get("Retry-After")
            try:
                sleep = max(1, int(ra)) if ra else min(60, 2 ** tries)
            except ValueError:
                sleep = min(60, 2 ** tries)
            print(f"[warn] HTTP {r.status_code} on {method} {url} (try {tries}/{MAX_TRIES}); sleeping {sleep}s", file=sys.stderr)
            time.sleep(sleep)
            continue
        return r, None
    return None, last_exc

# ---------- classification helpers ----------
TYPE_FIELDS = [
    # Solr-style
    "media_type_ssim", "media_type_tesim", "media_type_ssi",
    "human_readable_media_type_ssim", "human_readable_media_type_tesim", "human_readable_media_type_ssi",
    "title_ssi", "title_tesim",
    "modality_ssim", "human_readable_modality_tesim", "human_readable_modality_ssi",
    "number_of_images_in_set_tesim", "slice_thickness_tesim", "x_spacing_tesim", "y_spacing_tesim", "z_spacing_tesim",
    # Simplified (as seen in /api/media/{id})
    "media_type", "human_readable_media_type", "title", "modality",
    "number_of_images_in_set", "slice_thickness", "x_pixel_spacing", "y_pixel_spacing", "z_pixel_spacing",
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

def any_contains(values: List[str], needles: List[str]) -> bool:
    return any(any(n in v for n in needles) for v in values)

def classify_media_type(record: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    vals = [s.lower() for s in collect_values(record, TYPE_FIELDS)]
    raw_hint = ", ".join(sorted(set(vals))) if vals else "unknown"
    present = [k for k in TYPE_FIELDS if k in record]
    detail = {"fields_checked": TYPE_FIELDS, "type_fields_present": present, "values_collected": vals}

    if "mesh" in vals or any_contains(vals, ["[mesh]"]):
        return "mesh", raw_hint, detail
    if "ctimageseries" in vals or "volumetric image series" in vals or any_contains(vals, ["[ctimageseries]", "[ct]"]):
        return "ctimageseries", raw_hint, detail

    has_ct_modality = any_contains(vals, ["computed tomography"]) or "ct" in vals
    has_slice_or_spacing = any(k in record for k in [
        "slice_thickness_tesim", "x_spacing_tesim", "y_spacing_tesim", "z_spacing_tesim",
        "slice_thickness", "x_pixel_spacing", "y_pixel_spacing", "z_pixel_spacing"
    ])
    has_count = bool(record.get("number_of_images_in_set_tesim") or record.get("number_of_images_in_set"))
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

# ---------------- download body helpers ----------------
def split_categories(raw: str) -> List[str]:
    parts = [p.strip() for p in re.split(r"[|,]", raw or "") if p.strip()]
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out

def body_use_categories(categories: List[str]) -> Dict[str, Any]:
    return {"use_statement": USE_STATEMENT, "use_categories": categories, "agreements_accepted": AGREEMENTS_ACCEPTED}

def body_use_other(text: str) -> Dict[str, Any]:
    return {"use_statement": USE_STATEMENT, "use_category_other": text, "agreements_accepted": AGREEMENTS_ACCEPTED}

# ---------------- main logic ----------------
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

    r, err = backoff_request("GET", media_url, headers=headers_for_auth("bearer"))
    if r is not None and r.status_code in (401, 403):
        print("[warn] bearer auth rejected; retrying with raw token for GET", file=sys.stderr)
        r, err = backoff_request("GET", media_url, headers=headers_for_auth("raw"))
    dump_http_debug(r, f"media_{MEDIA_ID}")
    if err:
        write_exception(f"media_{MEDIA_ID}", err)

    if not r or r.status_code >= 400:
        status = r.status_code if r else "no-response"
        msg = f"Failed to fetch media record {MEDIA_ID} (status={status})."
        print("[error]", msg, file=sys.stderr)
        with open(os.path.join(ARTIFACT_DIR, "error.json"), "w", encoding="utf-8") as fh:
            json.dump({"error": msg}, fh, indent=2)
        gh_set_outputs(media_type="unknown", action="lookup", result="failed", artifact_dir=ARTIFACT_DIR, notes=msg)
        return

    try:
        payload = r.json()
    except Exception as e:
        msg = f"Bad JSON from media record endpoint: {e}"
        print("[error]", msg, file=sys.stderr)
        with open(os.path.join(ARTIFACT_DIR, "media_raw.txt"), "w", encoding="utf-8") as fh:
            fh.write(r.text[:RAW_MAX] if r and r.text else msg)
        gh_set_outputs(media_type="unknown", action="lookup", result="failed", artifact_dir=ARTIFACT_DIR, notes=msg)
        return

    # Save full payload
    with open(os.path.join(ARTIFACT_DIR, f"media_{MEDIA_ID}_raw.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    media = unwrap_media(payload) or {}
    found_id = media.get("id")
    if isinstance(found_id, list) and found_id:
        found_id = found_id[0]
    id_match = (str(found_id) == MEDIA_ID)
    print(f"[info] Media ID in record: {found_id} | requested: {MEDIA_ID} | match={id_match}", file=sys.stderr)

    mtype, raw_hint, detail = classify_media_type(media)
    detail.update({"media_id_reported": found_id, "media_id_requested": MEDIA_ID, "id_match": id_match, "raw_hint": raw_hint})
    with open(os.path.join(ARTIFACT_DIR, f"classification_{MEDIA_ID}.json"), "w", encoding="utf-8") as fh:
        json.dump(detail, fh, indent=2, ensure_ascii=False)

    print(f"[info] Classified media_type={mtype} ({raw_hint})", file=sys.stderr)

    # ---------- Mesh branch ----------
    if mtype == "mesh":
        post_url = f"{BASE_URL}/api/download/{MEDIA_ID}"

        # Construct initial body
        cat_list = split_categories(USE_CATEGORIES_RAW)
        if USE_CATEGORY_OTHER and not cat_list:
            initial_body = body_use_other(USE_CATEGORY_OTHER)
            initial_label = "use_other_initial"
        else:
            if not cat_list:
                cat_list = ["Research"]
            initial_body = body_use_categories(cat_list)
            initial_label = "use_categories_initial"

        # Save request body for reproducibility
        with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_request_{initial_label}.json"), "w", encoding="utf-8") as fh:
            json.dump(initial_body, fh, indent=2, ensure_ascii=False)

        # Try multiple auth variants
        pr, pr_err = None, None
        auth_attempts = []
        for idx, mode in enumerate(AUTH_ORDER, start=1):
            label = f"{initial_label}_auth{idx}_{mode}"
            print(f"[info] POST {post_url} ({label})", file=sys.stderr)
            h = with_json(headers_for_auth(mode))
            pr, pr_err = backoff_request("POST", post_url, headers=h, json=initial_body)
            dump_http_debug(pr, f"mesh_{MEDIA_ID}_download_resp_{label}")
            if pr_err:
                write_exception(f"mesh_{MEDIA_ID}_download_resp_{label}", pr_err)
            auth_attempts.append({"label": label, "mode": mode, "status": (None if pr is None else pr.status_code)})

            # Stop when we have a non-retryable answer (any response, even 4xx), or success
            if pr is not None:
                break

        # If we have a response and it's 400 for invalid categories, optionally fallback
        fallback_tried = False
        if pr is not None and pr.status_code == 400 and FALLBACK_TO_OTHER:
            try:
                err_json = pr.json()
                err_txt = json.dumps(err_json)
            except Exception:
                err_txt = pr.text or ""
            if "use_categories" in (err_txt or "").lower() and "not valid" in (err_txt or "").lower():
                fallback_body = body_use_other(USE_CATEGORY_OTHER or ("Other: " + " | ".join(cat_list) if cat_list else "Other"))
                with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_request_fallback_use_other.json"), "w", encoding="utf-8") as fh:
                    json.dump(fallback_body, fh, indent=2, ensure_ascii=False)

                pr, pr_err = None, None
                for idx, mode in enumerate(AUTH_ORDER, start=1):
                    label = f"fallback_use_other_auth{idx}_{mode}"
                    print(f"[info] POST {post_url} ({label})", file=sys.stderr)
                    h = with_json(headers_for_auth(mode))
                    pr, pr_err = backoff_request("POST", post_url, headers=h, json=fallback_body)
                    dump_http_debug(pr, f"mesh_{MEDIA_ID}_download_resp_{label}")
                    if pr_err:
                        write_exception(f"mesh_{MEDIA_ID}_download_resp_{label}", pr_err)
                    if pr is not None:
                        break
                fallback_tried = True

        # If still no response, fail and include attempt summary
        if pr is None:
            with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_attempts.json"), "w", encoding="utf-8") as fh:
                json.dump({"attempts": auth_attempts}, fh, indent=2, ensure_ascii=False)
            msg = "Download request failed (status=no-response)."
            print("[error]", msg, file=sys.stderr)
            gh_set_outputs(media_type="mesh", action="download", result="failed", artifact_dir=ARTIFACT_DIR,
                           notes=f"id_match={id_match}; {'fallback tried' if fallback_tried else 'no fallback'}; see *_exception.json / *_http_debug.json")
            return

        # If response is error
        if pr.status_code >= 400:
            with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_attempts.json"), "w", encoding="utf-8") as fh:
                json.dump({"status": pr.status_code}, fh, indent=2, ensure_ascii=False)
            msg = f"Download request failed (status={pr.status_code})."
            print("[error]", msg, file=sys.stderr)
            gh_set_outputs(media_type="mesh", action="download", result="failed", artifact_dir=ARTIFACT_DIR,
                           notes=f"id_match={id_match}; {'fallback tried' if fallback_tried else 'no fallback'}")
            return

        # Parse for download_url
        try:
            dl_payload = pr.json()
        except Exception as e:
            msg = f"Bad JSON in download response: {e}"
            print("[error]", msg, file=sys.stderr)
            with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_response.txt"), "w", encoding="utf-8") as fh:
                fh.write(pr.text[:RAW_MAX] if pr and pr.text else "")
            gh_set_outputs(media_type="mesh", action="download", result="failed", artifact_dir=ARTIFACT_DIR,
                           notes=f"id_match={id_match}; parse download response failed")
            return

        with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_response.json"), "w", encoding="utf-8") as fh:
            json.dump(dl_payload, fh, indent=2, ensure_ascii=False)

        download_url = None
        try:
            node = dl_payload.get("response", {}).get("media", {})
            if isinstance(node, dict):
                urls = node.get("download_url")
                if isinstance(urls, list) and urls:
                    download_url = urls[0]
                elif isinstance(urls, str):
                    download_url = urls
        except Exception:
            pass

        if not download_url:
            msg = "No download_url returned (may require approval or restricted access)."
            print("[warn]", msg, file=sys.stderr)
            gh_set_outputs(media_type="mesh", action="download", result="no-url", artifact_dir=ARTIFACT_DIR,
                           notes=f"id_match={id_match}; request accepted but no presigned URL")
            return

        # Download the asset (headers accept */* to avoid content-type skirmishes)
        print(f"[info] GET presigned {download_url}", file=sys.stderr)
        dr, dr_err = backoff_request("GET", download_url, headers=base_headers(accept_json=False), stream=True)
        dump_http_debug(dr, f"mesh_{MEDIA_ID}_download_file_headers")
        if dr_err:
            write_exception(f"mesh_{MEDIA_ID}_download_file_headers", dr_err)

        if not dr or dr.status_code >= 400:
            status = dr.status_code if dr else "no-response"
            msg = f"Failed to download file from pre-signed URL (status={status})."
            print("[error]", msg, file=sys.stderr)
            gh_set_outputs(media_type="mesh", action="download", result="failed", artifact_dir=ARTIFACT_DIR,
                           notes=f"id_match={id_match}; presigned download failed")
            return

        fname = parse_filename_from_headers(dr, f"media_{MEDIA_ID}.bin")
        out_path = os.path.join(ARTIFACT_DIR, fname)
        size = 0
        for chunk in dr.iter_content(chunk_size=1024 * 1024):
            if chunk:
                with open(out_path, "ab") as fh:
                    fh.write(chunk)
                size += len(chunk)

        with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_info.json"), "w", encoding="utf-8") as fh:
            json.dump({"media_id": MEDIA_ID, "download_url": download_url, "filename": fname, "size_bytes": size}, fh, indent=2)

        gh_set_outputs(media_type="mesh", action="download", result="success", artifact_dir=ARTIFACT_DIR,
                       notes=f"id_match={id_match}; saved={fname}")
        print(f"[info] Downloaded {size} bytes to {out_path}", file=sys.stderr)
        return

    # ---------- CTImageSeries branch ----------
    if mtype == "ctimageseries":
        iiif_url = f"{BASE_URL}/api/media/{MEDIA_ID}/iiif/manifest"
        print(f"[info] GET {iiif_url} (IIIF manifest)", file=sys.stderr)

        ir, ir_err = backoff_request("GET", iiif_url, headers=headers_for_auth("bearer"))
        if ir is not None and ir.status_code in (401, 403):
            print("[warn] bearer auth rejected on IIIF; retrying with raw token", file=sys.stderr)
            ir, ir_err = backoff_request("GET", iiif_url, headers=headers_for_auth("raw"))
        dump_http_debug(ir, f"ct_{MEDIA_ID}_iiif")
        if ir_err:
            write_exception(f"ct_{MEDIA_ID}_iiif", ir_err)

        if not ir or ir.status_code >= 400:
            status = ir.status_code if ir else "no-response"
            msg = f"Failed to fetch IIIF manifest (status={status})."
            print("[error]", msg, file=sys.stderr)
            gh_set_outputs(media_type="ctimageseries", action="iiif", result="failed", artifact_dir=ARTIFACT_DIR,
                           notes=f"id_match={id_match}; iiif fetch failed")
            return

        try:
            manifest = ir.json()
        except Exception as e:
            msg = f"Bad JSON in IIIF manifest response: {e}"
            print("[error]", msg, file=sys.stderr)
            gh_set_outputs(media_type="ctimageseries", action="iiif", result="failed", artifact_dir=ARTIFACT_DIR,
                           notes=f"id_match={id_match}; iiif parse failed")
            return

        out_path = os.path.join(ARTIFACT_DIR, f"iiif_manifest_{MEDIA_ID}.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)

        gh_set_outputs(media_type="ctimageseries", action="iiif", result="success", artifact_dir=ARTIFACT_DIR,
                       notes=f"id_match={id_match}; saved=iiif_manifest_{MEDIA_ID}.json")
        print(f"[info] Saved IIIF manifest to {out_path}", file=sys.stderr)
        return

    # ---------- Unknown ----------
    msg = f"Unhandled media type. (hint: {raw_hint})"
    print("[warn]", msg, file=sys.stderr)
    with open(os.path.join(ARTIFACT_DIR, f"media_{MEDIA_ID}_unhandled.txt"), "w", encoding="utf-8") as fh:
        fh.write(msg + "\n")
    gh_set_outputs(media_type="other", action="none", result="skipped", artifact_dir=ARTIFACT_DIR,
                   notes=f"id_match={id_match}; {msg}")

if __name__ == "__main__":
    main()
