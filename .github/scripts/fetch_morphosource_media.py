#!/usr/bin/env python3
"""
Fetch a MorphoSource media by ID and:
- If Mesh: POST /api/download/{id} (or /api/media/{id}/download) with your API key in Authorization header to obtain a presigned URL; download & save.
- If CTImageSeries: GET /api/media/{id}/iiif/manifest; save JSON.

Auth per docs:
- Primary: Authorization: <API_KEY>
- Defensive: also send X-API-KEY / Api-Key and optionally append ?api_key=<KEY>
Docs say this endpoint returns a download URL if the user (key) is authorized. (See “Download media file”.)
"""

import os, sys, json, time, re, traceback
from typing import Any, Dict, Optional, Tuple, List
import requests
from urllib.parse import urlparse, unquote, urlencode

# ---------- Config from environment ----------
BASE_URL = os.getenv("BASE_URL", "https://www.morphosource.org").rstrip("/")
MEDIA_ID = os.getenv("MEDIA_ID", "").strip()
API_KEY = (os.getenv("MORPHOSOURCE_API_KEY") or "").strip()

# Sanitize commonly pasted prefixes
for prefix in ("Bearer ", "bearer ", "Token token=", "Token token=\""):
    if API_KEY.startswith(prefix):
        API_KEY = API_KEY[len(prefix):].strip().strip('"')

AUTH_ORDER = [s.strip().lower() for s in (os.getenv("AUTH_ORDER", "raw")).split(",") if s.strip()]
EXTRA_KEY_HEADERS = [s.strip() for s in (os.getenv("EXTRA_KEY_HEADERS", "x-api-key,api-key")).split(",") if s.strip()]
APPEND_API_KEY_PARAM = os.getenv("APPEND_API_KEY_PARAM", "1").lower() in ("1","true","yes","on")

VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() in ("1","true","yes","on")
EXTRA_HEADERS_JSON = os.getenv("EXTRA_HEADERS_JSON", "").strip()

USE_STATEMENT = os.getenv("USE_STATEMENT", "Downloading this data as part of a research project.").strip()
USE_CATEGORIES_RAW = os.getenv("USE_CATEGORIES", "Research").strip()
USE_CATEGORY_OTHER = os.getenv("USE_CATEGORY_OTHER", "").strip()
AGREEMENTS_ACCEPTED = os.getenv("AGREEMENTS_ACCEPTED", "true").lower() == "true"

ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", "artifacts").strip()
DEBUG = os.getenv("DEBUG", "1").lower() in ("1","true","yes","on")
RAW_MAX = int(os.getenv("RAW_MAX_BYTES", "262144"))
FALLBACK_TO_OTHER = os.getenv("FALLBACK_TO_OTHER", "1").lower() in ("1","true","yes","on")

TIMEOUT = (5, 60)
MAX_TRIES = 4
RETRY_STATUS = {429, 500, 502, 503, 504}

# ---------- Logging / helpers ----------
def dbg(msg: str):
    if DEBUG:
        print(f"[debug] {msg}", file=sys.stderr)

def mask_key(k: str) -> str:
    if not k: return "(empty)"
    return f"len={len(k)} last4={k[-4:]}"

def gh_set_outputs(**kv):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path: return
    with open(path, "a", encoding="utf-8") as fh:
        for k, v in kv.items():
            s = "" if v is None else str(v)
            if "\n" in s:
                fh.write(f"{k}<<EOF\n{s}\nEOF\n")
            else:
                fh.write(f"{k}={s}\n")

def ensure_dir(p: str): os.makedirs(p, exist_ok=True)

def scrub_headers(h: Dict[str, str]) -> Dict[str, str]:
    red = {}
    for k, v in (h or {}).items():
        if k.lower() in ("authorization", "cookie", "x-api-key", "api-key"):
            red[k] = "***REDACTED***"
        else:
            red[k] = v
    return red

def write_exception(base: str, err: Exception):
    with open(os.path.join(ARTIFACT_DIR, f"{base}_exception.json"), "w", encoding="utf-8") as fh:
        json.dump({"type": type(err).__name__, "message": str(err), "traceback": traceback.format_exc()}, fh, indent=2)

def dump_http_debug(resp: Optional[requests.Response], base: str):
    try:
        info = {
            "request": {
                "method": getattr(resp.request, "method", None) if resp else None,
                "url": getattr(resp.request, "url", None) if resp else None,
                "headers": scrub_headers(dict(getattr(resp.request, "headers", {}) or {})) if resp else {},
            },
            "response": {
                "url": getattr(resp, "url", None) if resp else None,
                "status_code": getattr(resp, "status_code", None) if resp else None,
                "reason": getattr(resp, "reason", None) if resp else None,
                "headers": scrub_headers(dict(getattr(resp, "headers", {}) or {})) if resp else {},
                "elapsed_seconds": (resp.elapsed.total_seconds() if (resp and resp.elapsed) else None),
            }
        }
        with open(os.path.join(ARTIFACT_DIR, f"{base}_http_debug.json"), "w", encoding="utf-8") as fh:
            json.dump(info, fh, indent=2, ensure_ascii=False)
        if resp is not None:
            with open(os.path.join(ARTIFACT_DIR, f"{base}_raw.txt"), "w", encoding="utf-8", errors="ignore") as fh:
                fh.write(resp.text[:RAW_MAX])
    except Exception as e:
        dbg(f"dump_http_debug failed: {e}")

def merge_extra_headers(h: Dict[str,str]) -> Dict[str,str]:
    if not EXTRA_HEADERS_JSON: return h
    try:
        extra = json.loads(EXTRA_HEADERS_JSON)
        if isinstance(extra, dict):
            merged = dict(h); merged.update({k:str(v) for k,v in extra.items()})
            return merged
    except Exception as e:
        dbg(f"EXTRA_HEADERS_JSON parse error: {e}")
    return h

def base_headers(accept_json=True) -> Dict[str,str]:
    h = {"Accept": "application/json" if accept_json else "*/*"}
    return merge_extra_headers(h)

def headers_for_auth(mode: str, accept_json=True) -> Dict[str,str]:
    h = base_headers(accept_json=accept_json)
    if API_KEY:
        if mode == "raw":
            h["Authorization"] = API_KEY                   # doc-aligned
        elif mode == "bearer":
            h["Authorization"] = f"Bearer {API_KEY}"
        elif mode == "token":
            h["Authorization"] = f'Token token="{API_KEY}"'
        elif mode == "token_noquotes":
            h["Authorization"] = f"Token token={API_KEY}"
        # always also send these, harmless if ignored
        for hn in EXTRA_KEY_HEADERS:
            if hn: h[hn] = API_KEY
    return h

def with_json(h: Dict[str,str]) -> Dict[str,str]:
    h = dict(h); h["Content-Type"] = "application/json"; return h

def append_api_key_param(url: str) -> str:
    if not API_KEY: return url
    return f"{url}{'&' if '?' in url else '?'}{urlencode({'api_key': API_KEY})}"

def backoff_request(method: str, url: str, **kwargs) -> Tuple[Optional[requests.Response], Optional[Exception]]:
    tries, last_exc = 0, None
    while tries < MAX_TRIES:
        tries += 1
        try:
            r = requests.request(method, url, timeout=TIMEOUT, verify=VERIFY_SSL, **kwargs)
        except requests.RequestException as e:
            last_exc = e
            print(f"[warn] network error (try {tries}/{MAX_TRIES}): {e}", file=sys.stderr)
            time.sleep(min(60, 2 ** tries))
            continue
        if r.status_code < 400: return r, None
        if r.status_code in RETRY_STATUS and tries < MAX_TRIES:
            ra = r.headers.get("Retry-After")
            sleep = max(1, int(ra)) if (ra and ra.isdigit()) else min(60, 2 ** tries)
            print(f"[warn] HTTP {r.status_code} (try {tries}/{MAX_TRIES}); sleeping {sleep}s", file=sys.stderr)
            time.sleep(sleep); continue
        return r, None
    return None, last_exc

# ---------- Classification ----------
TYPE_FIELDS = [
    # Solr-style
    "media_type_ssim", "media_type_tesim", "media_type_ssi",
    "human_readable_media_type_ssim", "human_readable_media_type_tesim", "human_readable_media_type_ssi",
    "title_ssi", "title_tesim",
    "modality_ssim", "human_readable_modality_tesim", "human_readable_modality_ssi",
    "number_of_images_in_set_tesim", "slice_thickness_tesim", "x_spacing_tesim", "y_spacing_tesim", "z_spacing_tesim",
    # simplified
    "media_type", "human_readable_media_type", "title", "modality",
    "number_of_images_in_set", "slice_thickness", "x_pixel_spacing", "y_pixel_spacing", "z_pixel_spacing",
]

def listify(v: Any) -> List[str]:
    if v is None: return []
    return v if isinstance(v, list) else [str(v)]

def collect_values(record: Dict[str, Any], keys: List[str]) -> List[str]:
    vals = []
    for k in keys:
        if k in record:
            vals += [str(s).strip() for s in listify(record[k]) if str(s).strip()]
    return vals

def unwrap_media(obj: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(obj, dict): return None
    r = obj.get("response")
    if isinstance(r, dict):
        m = r.get("media")
        if isinstance(m, dict): return m
        if isinstance(m, list) and m: return m[0]
        docs = r.get("docs")
        if isinstance(docs, list) and docs: return docs[0]
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
    if "mesh" in vals or any_contains(vals, ["[mesh]"]): return "mesh", raw_hint, detail
    if "ctimageseries" in vals or "volumetric image series" in vals or any_contains(vals, ["[ctimageseries]", "[ct]"]):
        return "ctimageseries", raw_hint, detail
    has_ct_modality = any_contains(vals, ["computed tomography"]) or "ct" in vals
    has_slice_or_spacing = any(k in record for k in ["slice_thickness_tesim","x_spacing_tesim","y_spacing_tesim","z_spacing_tesim","slice_thickness","x_pixel_spacing","y_pixel_spacing","z_pixel_spacing"])
    has_count = bool(record.get("number_of_images_in_set_tesim") or record.get("number_of_images_in_set"))
    if has_ct_modality and (has_slice_or_spacing or has_count): return "ctimageseries", raw_hint, detail
    return "other", raw_hint, detail

def parse_filename_from_headers(resp: requests.Response, fallback: str) -> str:
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", cd, flags=re.IGNORECASE)
    if m: return unquote(m.group(1))
    m = re.search(r'filename\s*=\s*"([^"]+)"', cd, flags=re.IGNORECASE)
    if m: return m.group(1)
    m = re.search(r'filename\s*=\s*([^;]+)', cd, flags=re.IGNORECASE)
    if m: return m.group(1).strip()
    base = os.path.basename(urlparse(resp.url).path)
    return base or fallback

# ---------- Download helpers ----------
def split_categories(raw: str) -> List[str]:
    parts = [p.strip() for p in re.split(r"[|,]", raw or "") if p.strip()]
    seen, out = set(), []
    for p in parts:
        if p not in seen: seen.add(p); out.append(p)
    return out

def body_use_categories(categories: List[str]) -> Dict[str, Any]:
    return {"use_statement": USE_STATEMENT, "use_categories": categories, "agreements_accepted": AGREEMENTS_ACCEPTED}

def body_use_other(text: str) -> Dict[str, Any]:
    return {"use_statement": USE_STATEMENT, "use_category_other": text, "agreements_accepted": AGREEMENTS_ACCEPTED}

def post_with_auth_modes(url: str, body: Dict[str, Any], label_root: str) -> Tuple[Optional[requests.Response], list]:
    attempts, final_resp = [], None
    for idx, mode in enumerate(AUTH_ORDER, start=1):
        label = f"{label_root}_auth{idx}_{mode}"
        h = with_json(headers_for_auth(mode))
        print(f"[info] POST {url} ({label})", file=sys.stderr)
        pr, pr_err = backoff_request("POST", url, headers=h, json=body)
        dump_http_debug(pr, f"mesh_{MEDIA_ID}_download_resp_{label}")
        if pr_err: write_exception(f"mesh_{MEDIA_ID}_download_resp_{label}", pr_err)
        attempts.append({"label": label, "mode": mode, "status": (None if pr is None else pr.status_code)})
        if pr is None: continue
        if pr.status_code < 400: return pr, attempts
        if pr.status_code in (401,403,404,405):
            final_resp = pr; continue
        return pr, attempts
    return final_resp, attempts

def post_try_all(url: str, body: Dict[str, Any], label: str, attempts_summary: list) -> Optional[requests.Response]:
    pr, att = post_with_auth_modes(url, body, label); attempts_summary.append({"path": url, "attempts": att})
    if pr is not None and pr.status_code < 400: return pr
    if APPEND_API_KEY_PARAM and API_KEY:
        url_param = append_api_key_param(url)
        pr2, att2 = post_with_auth_modes(url_param, body, label + "_param")
        attempts_summary.append({"path": url_param, "attempts": att2})
        if pr2 is not None and pr2.status_code < 400: return pr2
    return pr

# ---------- Main ----------
def main():
    ensure_dir(ARTIFACT_DIR)

    print(f"[info] Using API key: {mask_key(API_KEY)}", file=sys.stderr)

    if not MEDIA_ID:
        msg = "MEDIA_ID is required."
        print("[error]", msg, file=sys.stderr)
        gh_set_outputs(media_type="unknown", action="none", result="failed", artifact_dir=ARTIFACT_DIR, notes=msg)
        with open(os.path.join(ARTIFACT_DIR, "README.txt"), "w", encoding="utf-8") as fh: fh.write(msg + "\n")
        sys.exit(1)

    if not API_KEY:
        msg = "MORPHOSOURCE_API_KEY is empty; cannot authorize download."
        print("[error]", msg, file=sys.stderr)
        gh_set_outputs(media_type="unknown", action="none", result="failed", artifact_dir=ARTIFACT_DIR, notes=msg)
        with open(os.path.join(ARTIFACT_DIR, "error.json"), "w", encoding="utf-8") as fh:
            json.dump({"error": msg}, fh, indent=2)
        sys.exit(1)

    # Fetch media (auth optional)
    media_url = f"{BASE_URL}/api/media/{MEDIA_ID}"
    print(f"[info] GET {media_url}", file=sys.stderr)
    r, err = backoff_request("GET", media_url, headers=headers_for_auth("raw"))
    if r is not None and r.status_code in (401,403):
        r, err = backoff_request("GET", media_url, headers=headers_for_auth("bearer"))
    dump_http_debug(r, f"media_{MEDIA_ID}")
    if err: write_exception(f"media_{MEDIA_ID}", err)

    if not r or r.status_code >= 400:
        status = r.status_code if r else "no-response"
        msg = f"Failed to fetch media record {MEDIA_ID} (status={status})."
        print("[error]", msg, file=sys.stderr)
        with open(os.path.join(ARTIFACT_DIR, "error.json"), "w", encoding="utf-8") as fh: json.dump({"error": msg}, fh, indent=2)
        gh_set_outputs(media_type="unknown", action="lookup", result="failed", artifact_dir=ARTIFACT_DIR, notes=msg)
        return

    try:
        payload = r.json()
    except Exception as e:
        msg = f"Bad JSON from media record endpoint: {e}"
        print("[error]", msg, file=sys.stderr)
        with open(os.path.join(ARTIFACT_DIR, "media_raw.txt"), "w", encoding="utf-8") as fh: fh.write(r.text[:RAW_MAX] if r and r.text else msg)
        gh_set_outputs(media_type="unknown", action="lookup", result="failed", artifact_dir=ARTIFACT_DIR, notes=msg)
        return

    with open(os.path.join(ARTIFACT_DIR, f"media_{MEDIA_ID}_raw.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    media = unwrap_media(payload) or {}
    found_id = media.get("id")
    if isinstance(found_id, list) and found_id: found_id = found_id[0]
    id_match = (str(found_id) == MEDIA_ID)
    print(f"[info] Media ID in record: {found_id} | requested: {MEDIA_ID} | match={id_match}", file=sys.stderr)

    mtype, raw_hint, detail = classify_media_type(media)
    detail.update({"media_id_reported": found_id, "media_id_requested": MEDIA_ID, "id_match": id_match, "raw_hint": raw_hint})
    with open(os.path.join(ARTIFACT_DIR, f"classification_{MEDIA_ID}.json"), "w", encoding="utf-8") as fh:
        json.dump(detail, fh, indent=2, ensure_ascii=False)
    print(f"[info] Classified media_type={mtype} ({raw_hint})", file=sys.stderr)

    # Mesh branch
    if mtype == "mesh":
        cat_list = split_categories(USE_CATEGORIES_RAW)
        if USE_CATEGORY_OTHER and not cat_list:
            initial_body = body_use_other(USE_CATEGORY_OTHER); initial_label = "use_other_initial"
        else:
            if not cat_list: cat_list = ["Research"]
            initial_body = body_use_categories(cat_list); initial_label = "use_categories_initial"

        with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_request_{initial_label}.json"), "w", encoding="utf-8") as fh:
            json.dump(initial_body, fh, indent=2, ensure_ascii=False)

        attempts_summary = []
        url1 = f"{BASE_URL}/api/download/{MEDIA_ID}"
        pr = post_try_all(url1, initial_body, initial_label + "_p1", attempts_summary)

        if not pr or pr.status_code >= 400:
            url2 = f"{BASE_URL}/api/media/{MEDIA_ID}/download"
            pr2 = post_try_all(url2, initial_body, initial_label + "_p2", attempts_summary)
            if pr is None or (pr2 is not None and pr2.status_code < 400): pr = pr2

        # 400 invalid categories -> fallback to 'use_category_other'
        fallback_tried = False
        if pr is not None and pr.status_code == 400 and FALLBACK_TO_OTHER:
            try:
                err_json = pr.json(); err_txt = json.dumps(err_json)
            except Exception:
                err_txt = pr.text or ""
            if "use_categories" in (err_txt or "").lower() and "not valid" in (err_txt or "").lower():
                fb_body = body_use_other(USE_CATEGORY_OTHER or ("Other: " + " | ".join(cat_list) if cat_list else "Other"))
                with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_request_fallback_use_other.json"), "w", encoding="utf-8") as fh:
                    json.dump(fb_body, fh, indent=2, ensure_ascii=False)
                pr_fb1 = post_try_all(url1, fb_body, "fallback_use_other_p1", attempts_summary)
                pr_fb2 = None
                if not pr_fb1 or pr_fb1.status_code >= 400:
                    pr_fb2 = post_try_all(url2, fb_body, "fallback_use_other_p2", attempts_summary)
                pr = pr_fb1 if (pr_fb1 and pr_fb1.status_code < 400) else pr_fb2
                fallback_tried = True

        with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_attempts.json"), "w", encoding="utf-8") as fh:
            json.dump(attempts_summary, fh, indent=2, ensure_ascii=False)

        if pr is None:
            msg = "Download request failed (status=no-response)."
            print("[error]", msg, file=sys.stderr)
            gh_set_outputs(media_type="mesh", action="download", result="failed", artifact_dir=ARTIFACT_DIR,
                           notes=f"id_match={id_match}; {'fallback tried' if fallback_tried else 'no fallback'}; see *_attempts.json")
            return

        if pr.status_code >= 400:
            msg = f"Download request failed (status={pr.status_code})."
            print("[error]", msg, file=sys.stderr)
            gh_set_outputs(media_type="mesh", action="download", result="failed", artifact_dir=ARTIFACT_DIR,
                           notes=f"id_match={id_match}; {'fallback tried' if fallback_tried else 'no fallback'}; see *_attempts.json")
            return

        # Parse presigned URL
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
            urls = node.get("download_url") if isinstance(node, dict) else None
            if isinstance(urls, list) and urls: download_url = urls[0]
            elif isinstance(urls, str): download_url = urls
        except Exception:
            pass

        if not download_url:
            msg = "No download_url returned (may require approval or restricted access)."
            print("[warn]", msg, file=sys.stderr)
            gh_set_outputs(media_type="mesh", action="download", result="no-url", artifact_dir=ARTIFACT_DIR,
                           notes=f"id_match={id_match}; request accepted but no presigned URL")
            return

        # Download the asset
        print(f"[info] GET presigned {download_url}", file=sys.stderr)
        dr, dr_err = backoff_request("GET", download_url, headers=base_headers(accept_json=False), stream=True)
        dump_http_debug(dr, f"mesh_{MEDIA_ID}_download_file_headers")
        if dr_err: write_exception(f"mesh_{MEDIA_ID}_download_file_headers", dr_err)

        if not dr or dr.status_code >= 400:
            status = dr.status_code if dr else "no-response"
            msg = f"Failed to download file from presigned URL (status={status})."
            print("[error]", msg, file=sys.stderr)
            gh_set_outputs(media_type="mesh", action="download", result="failed", artifact_dir=ARTIFACT_DIR,
                           notes=f"id_match={id_match}; presigned download failed")
            return

        fname = parse_filename_from_headers(dr, f"media_{MEDIA_ID}.bin")
        out_path, size = os.path.join(ARTIFACT_DIR, fname), 0
        for chunk in dr.iter_content(chunk_size=1024*1024):
            if chunk:
                with open(out_path, "ab") as fh: fh.write(chunk)
                size += len(chunk)

        with open(os.path.join(ARTIFACT_DIR, f"mesh_{MEDIA_ID}_download_info.json"), "w", encoding="utf-8") as fh:
            json.dump({"media_id": MEDIA_ID, "download_url": download_url, "filename": fname, "size_bytes": size}, fh, indent=2)

        gh_set_outputs(media_type="mesh", action="download", result="success", artifact_dir=ARTIFACT_DIR,
                       notes=f"id_match={id_match}; saved={fname}")
        print(f"[info] Downloaded {size} bytes to {out_path}", file=sys.stderr)
        return

    # CT branch
    if mtype == "ctimageseries":
        iiif_url = f"{BASE_URL}/api/media/{MEDIA_ID}/iiif/manifest"
        print(f"[info] GET {iiif_url} (IIIF manifest)", file=sys.stderr)
        ir, ir_err = backoff_request("GET", iiif_url, headers=headers_for_auth("raw"))
        if ir is not None and ir.status_code in (401,403):
            ir, ir_err = backoff_request("GET", iiif_url, headers=headers_for_auth("bearer"))
        dump_http_debug(ir, f"ct_{MEDIA_ID}_iiif")
        if ir_err: write_exception(f"ct_{MEDIA_ID}_iiif", ir_err)
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
        with open(out_path, "w", encoding="utf-8") as fh: json.dump(manifest, fh, indent=2, ensure_ascii=False)
        gh_set_outputs(media_type="ctimageseries", action="iiif", result="success", artifact_dir=ARTIFACT_DIR,
                       notes=f"id_match={id_match}; saved=iiif_manifest_{MEDIA_ID}.json")
        print(f"[info] Saved IIIF manifest to {out_path}", file=sys.stderr)
        return

    # Unknown type
    msg = f"Unhandled media type. (hint: {raw_hint})"
    print("[warn]", msg, file=sys.stderr)
    with open(os.path.join(ARTIFACT_DIR, f"media_{MEDIA_ID}_unhandled.txt"), "w", encoding="utf-8") as fh: fh.write(msg + "\n")
    gh_set_outputs(media_type="other", action="none", result="skipped", artifact_dir=ARTIFACT_DIR, notes=f"id_match={id_match}; {msg}")

if __name__ == "__main__":
    ensure_dir(ARTIFACT_DIR)
    main()
