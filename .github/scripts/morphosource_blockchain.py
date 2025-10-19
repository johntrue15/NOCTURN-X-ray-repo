#!/usr/bin/env python3
"""Create blockchain-style daily snapshots of MorphoSource records."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from morphosource_api import (
    MorphoSourceAPI,
    MorphoSourceAPIError,
    MorphoSourceTemporarilyUnavailable,
)


ISO_TIMESTAMP_FORMAT = "%Y-%m-%dT%H-%M-%SZ"
DEFAULT_QUERY = "X-Ray Computed Tomography"
DEFAULT_SORT = "system_create_dtsi desc"
PER_PAGE = 100
RATE_LIMIT_DELAY = 1.0


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def canonical_dumps(data: object) -> str:
    """Serialize data to canonical JSON for hashing/comparison."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def compute_hash(data: object) -> str:
    return hashlib.sha256(canonical_dumps(data).encode("utf-8")).hexdigest()


@dataclass
class SnapshotChanges:
    added: List[str]
    removed: List[str]
    updated: List[str]

    def to_dict(self) -> Dict[str, Sequence[str]]:
        return {
            "added": self.added,
            "removed": self.removed,
            "updated": self.updated,
        }


@dataclass
class SnapshotBlock:
    index: int
    timestamp: str
    snapshot_file: str
    record_count: int
    records_hash: str
    previous_hash: Optional[str]
    changes: SnapshotChanges

    def to_dict(self) -> Dict[str, object]:
        data = {
            "index": self.index,
            "timestamp": self.timestamp,
            "snapshot_file": self.snapshot_file,
            "record_count": self.record_count,
            "records_hash": self.records_hash,
            "previous_hash": self.previous_hash,
            "changes": self.changes.to_dict(),
        }
        data["block_hash"] = compute_hash(data)
        return data


class BlockchainSnapshot:
    """Manage blockchain-style snapshots of MorphoSource records."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.blockchain_path = output_dir / "morphosource_blockchain.json"
        self.latest_snapshot_path = output_dir / "latest_snapshot.json"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.chain = self._load_chain()

    def _load_chain(self) -> List[Dict[str, object]]:
        if not self.blockchain_path.exists():
            return []
        with self.blockchain_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and "blocks" in data:
            return list(data["blocks"])
        if isinstance(data, list):
            return data
        raise ValueError("Invalid blockchain file format")

    def _write_chain(self) -> None:
        payload = {"blocks": self.chain}
        with self.blockchain_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)

    def _load_snapshot(self, snapshot_file: str) -> List[Dict[str, object]]:
        path = self.output_dir / snapshot_file
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _sanitize_records(self, records: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
        sanitized: List[Dict[str, object]] = []
        for record in records:
            sanitized.append(
                {
                    "id": record.get("id"),
                    "title": record.get("title"),
                    "url": record.get("url"),
                    "metadata": record.get("metadata", {}),
                }
            )
        sanitized.sort(key=lambda item: str(item.get("id", "")))
        return sanitized

    def record_changes(
        self,
        records: Sequence[Dict[str, object]],
        timestamp: datetime,
    ) -> Dict[str, object]:
        sanitized_records = self._sanitize_records(records)
        snapshot_filename = f"morphosource_records_{timestamp.strftime(ISO_TIMESTAMP_FORMAT)}.json"
        snapshot_path = self.output_dir / snapshot_filename

        # Save current snapshot
        with snapshot_path.open("w", encoding="utf-8") as fh:
            json.dump(sanitized_records, fh, indent=2, sort_keys=True)

        # Update latest snapshot alias
        with self.latest_snapshot_path.open("w", encoding="utf-8") as latest:
            json.dump(sanitized_records, latest, indent=2, sort_keys=True)

        previous_hash = None
        previous_records: List[Dict[str, object]] = []
        if self.chain:
            previous_block = self.chain[-1]
            previous_hash = previous_block.get("block_hash")
            prev_snapshot_file = previous_block.get("snapshot_file")
            if isinstance(prev_snapshot_file, str):
                previous_records = self._load_snapshot(prev_snapshot_file)

        changes = self._calculate_changes(previous_records, sanitized_records)
        block = SnapshotBlock(
            index=len(self.chain) + 1,
            timestamp=timestamp.isoformat(),
            snapshot_file=snapshot_filename,
            record_count=len(sanitized_records),
            records_hash=compute_hash(sanitized_records),
            previous_hash=previous_hash,
            changes=changes,
        )

        block_dict = block.to_dict()
        self.chain.append(block_dict)
        self._write_chain()
        return block_dict

    def _calculate_changes(
        self,
        previous_records: Sequence[Dict[str, object]],
        current_records: Sequence[Dict[str, object]],
    ) -> SnapshotChanges:
        previous_map = {str(item.get("id")): item for item in previous_records}
        current_map = {str(item.get("id")): item for item in current_records}

        added = sorted([rid for rid in current_map.keys() if rid not in previous_map])
        removed = sorted([rid for rid in previous_map.keys() if rid not in current_map])

        updated = []
        for rid in previous_map.keys() & current_map.keys():
            if canonical_dumps(previous_map[rid]) != canonical_dumps(current_map[rid]):
                updated.append(rid)
        updated.sort()

        return SnapshotChanges(added=added, removed=removed, updated=updated)


def fetch_all_records(api: MorphoSourceAPI) -> List[Dict[str, object]]:
    records: List[Dict[str, object]] = []
    page = 1

    while True:
        try:
            result = api.search_media(
                query=DEFAULT_QUERY,
                sort=DEFAULT_SORT,
                page=page,
                per_page=PER_PAGE,
            )
        except MorphoSourceTemporarilyUnavailable:
            time.sleep(10)
            continue
        except MorphoSourceAPIError as exc:
            raise RuntimeError(f"MorphoSource API error on page {page}: {exc}") from exc

        documents = result.get("data", [])
        if not documents:
            break

        for record in documents:
            normalized = api.normalize_record(record)
            records.append(
                {
                    "id": normalized.get("id"),
                    "title": normalized.get("title"),
                    "url": normalized.get("url"),
                    "metadata": normalized.get("metadata", {}),
                }
            )

        total_pages = result.get("meta", {}).get("total_pages", page)
        if page >= total_pages:
            break
        page += 1
        time.sleep(RATE_LIMIT_DELAY)

    return records


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create blockchain-style MorphoSource snapshots")
    parser.add_argument(
        "--output-dir",
        default="data/morphosource_chain",
        help="Directory to store blockchain snapshots and metadata",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)

    try:
        api = MorphoSourceAPI()
        records = fetch_all_records(api)

        if not records:
            print("No records retrieved from MorphoSource API")
            return 1

        blockchain = BlockchainSnapshot(output_dir)
        block = blockchain.record_changes(records, utc_now())

        summary_path = output_dir / "summary.json"
        with summary_path.open("w", encoding="utf-8") as summary:
            json.dump(block, summary, indent=2, sort_keys=True)

        print(
            "Snapshot complete: "
            f"{len(records)} records | "
            f"added={len(block['changes']['added'])} "
            f"removed={len(block['changes']['removed'])} "
            f"updated={len(block['changes']['updated'])}"
        )
        return 0

    except Exception as exc:  # pragma: no cover - defensive logging for workflow
        print(f"Error creating snapshot: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
