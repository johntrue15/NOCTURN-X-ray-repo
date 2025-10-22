import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import Iterable, List, Tuple

import requests


API_BASE_URL = "https://www.morphosource.org/api/media"
USER_AGENT = "NOCTURN-2D3D-Check/1.0"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def extract_id_from_url(url: str) -> str:
    match = re.search(r"(\d+)$", url)
    return match.group(1) if match else "unknown"


def create_status_file(status_data: dict) -> None:
    try:
        with open("url_check_status.json", "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2)
        logging.info("Status file saved")
    except Exception as exc:  # pragma: no cover - best-effort logging
        logging.error(f"Failed to save status file: {exc}")


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
    )
    return session


def flatten_metadata_values(record: dict, keys: Iterable[str]) -> List[str]:
    values: List[str] = []
    for key in keys:
        value = record.get(key)
        if isinstance(value, list):
            values.extend(str(item).lower() for item in value if item)
        elif isinstance(value, str):
            values.append(value.lower())
    return values


MEDIA_TYPE_KEYS: Tuple[str, ...] = (
    "media_type_ssim",
    "media_type_ssi",
    "media_type_tesim",
    "human_readable_media_type_ssim",
    "modality_ssim",
    "human_readable_modality_tesim",
    "file_type_ssim",
)


def derive_media_flags(record: dict) -> Tuple[bool, bool]:
    tokens = flatten_metadata_values(record, MEDIA_TYPE_KEYS)

    has_mesh = any("mesh" in token for token in tokens)
    volumetric_keywords = (
        "volumetric",
        "ct image series",
        "ctimage series",
        "ctimageseries",
        "ct image",
        "ct data",
        "ct scan",
        "computed tomography",
    )
    has_volumetric = any(
        any(keyword in token for keyword in volumetric_keywords) for token in tokens
    )

    return has_mesh, has_volumetric


def search_media_by_id(session: requests.Session, media_id: str) -> dict:
    params = {
        "utf8": "✓",
        "search_field": "media_id_ssi",
        "q": media_id,
        "per_page": 1,
        "page": 1,
    }
    response = session.get(API_BASE_URL, params=params, timeout=(10, 60))
    response.raise_for_status()
    payload = response.json()
    media_items = payload.get("response", {}).get("media", [])
    if not media_items:
        raise LookupError(f"No media found for ID {media_id}")
    return media_items[0]


def record_status(
    *,
    status: str,
    url: str,
    media_id: str,
    has_mesh: bool,
    has_volumetric: bool,
) -> None:
    status_data = {
        "status": status,
        "url": url,
        "file_id": media_id,
        "timestamp": datetime.now().isoformat(),
        "has_mesh": has_mesh,
        "has_volumetric_images": has_volumetric,
    }
    create_status_file(status_data)

    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"has_mesh={str(has_mesh).lower()}\n")
            f.write(f"has_volumetric_images={str(has_volumetric).lower()}\n")
            f.write(f"has_media_error={str(status == 'media_error').lower()}\n")
            f.write(f"has_server_error={str(status == 'server_error').lower()}\n")


def check_media_types(url: str) -> bool:
    media_id = extract_id_from_url(url)
    if media_id == "unknown":
        logging.error("Could not extract media ID from URL")
        record_status(
            status="media_error",
            url=url,
            media_id=media_id,
            has_mesh=False,
            has_volumetric=False,
        )
        return False

    session = create_session()
    try:
        record = search_media_by_id(session, media_id)
        has_mesh, has_volumetric = derive_media_flags(record)
        record_status(
            status="success",
            url=url,
            media_id=media_id,
            has_mesh=has_mesh,
            has_volumetric=has_volumetric,
        )
        return True
    except requests.HTTPError as exc:
        status = "server_error" if exc.response is not None and exc.response.status_code >= 500 else "media_error"
        logging.error(f"HTTP error retrieving media {media_id}: {exc}")
        record_status(
            status=status,
            url=url,
            media_id=media_id,
            has_mesh=False,
            has_volumetric=False,
        )
        return False
    except (LookupError, requests.RequestException) as exc:
        logging.error(f"Failed to retrieve media metadata for {media_id}: {exc}")
        record_status(
            status="media_error",
            url=url,
            media_id=media_id,
            has_mesh=False,
            has_volumetric=False,
        )
        return False

def process_urls_from_file(input_file):
    try:
        with open(input_file, 'r') as f:
            content = f.read().strip()

        urls = re.findall(r'https://www\.morphosource\.org/concern/media/\d+', content)
        if not urls:
            logging.error("No valid MorphoSource URLs found in file")
            return

        logging.info(f"Found {len(urls)} MorphoSource URLs in file")
        
        # Process only the first URL as we only need type information
        if urls:
            check_media_types(urls[0])

    except Exception as e:
        logging.error(f"Error processing file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        logging.error("Usage: python script.py <input_file>")
        sys.exit(1)

    process_urls_from_file(sys.argv[1])
