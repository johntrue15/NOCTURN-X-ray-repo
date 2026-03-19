#!/usr/bin/env python3
"""
Compute dataset quality metrics across all MorphoSource releases.

Metrics tracked:
  - Total records ingested
  - CT-to-Text coverage (% of records with AI analysis)
  - Deep analysis coverage (% with download + SlicerMorph)
  - Metadata completeness (avg fields per record)
  - Error rate (ct_analysis_error count)

Writes metrics JSON to data/quality_metrics.json and a Markdown summary.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "johntrue15/NOCTURN-X-ray-repo")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "data")


def gh_api(endpoint: str):
    result = subprocess.run(
        ["gh", "api", "-H", "Accept: application/vnd.github+json", endpoint],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"gh api error: {result.stderr}", file=sys.stderr)
        return None
    return json.loads(result.stdout)


def count_metadata_fields(body: str) -> int:
    """Count the number of distinct metadata fields mentioned in the body."""
    fields = [
        "species", "genus", "family", "order", "class", "phylum",
        "institution", "repository", "modality", "voxel", "resolution",
        "element", "body region", "specimen", "scan", "media_id",
        "taxonomy", "data manager",
    ]
    return sum(1 for f in fields if f.lower() in body.lower())


def load_previous_metrics(path: str) -> list[dict]:
    """Load historical metrics for time-series tracking."""
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
                return data.get("history", [])
        except (json.JSONDecodeError, KeyError):
            pass
    return []


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    metrics_path = os.path.join(OUTPUT_DIR, "quality_metrics.json")
    report_path = os.path.join(OUTPUT_DIR, "quality_report.md")

    page = 1
    all_releases = []
    while True:
        batch = gh_api(f"/repos/{REPO}/releases?per_page=100&page={page}")
        if not batch:
            break
        all_releases.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    print(f"Total releases fetched: {len(all_releases)}")

    ms_api = [r for r in all_releases if r["tag_name"].startswith("morphosource-api-")]
    ct_text = [r for r in all_releases if r["tag_name"].startswith("ct_to_text_analysis-")]
    ct_errors = [r for r in all_releases if r["tag_name"].startswith("ct_analysis_error-")]
    deep = [r for r in all_releases if r["tag_name"].startswith("daily-deep-analysis-")]
    daily = [r for r in all_releases if r["tag_name"].startswith("daily-")]
    monthly = [r for r in all_releases if r["tag_name"].startswith("monthly-")]

    total_records = len(ms_api)
    ct_text_count = len(ct_text)
    deep_count = len(deep)
    error_count = len(ct_errors)

    ct_coverage = (ct_text_count / total_records * 100) if total_records > 0 else 0
    deep_coverage = (deep_count / total_records * 100) if total_records > 0 else 0
    error_rate = (error_count / (ct_text_count + error_count) * 100) if (ct_text_count + error_count) > 0 else 0

    avg_fields = 0
    if ct_text:
        field_counts = [count_metadata_fields(r.get("body", "") or "") for r in ct_text]
        avg_fields = sum(field_counts) / len(field_counts)

    now = datetime.now(timezone.utc)
    snapshot = {
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.isoformat(),
        "total_morphosource_records": total_records,
        "ct_to_text_analyses": ct_text_count,
        "deep_analyses": deep_count,
        "ct_errors": error_count,
        "daily_runs": len(daily),
        "monthly_runs": len(monthly),
        "ct_coverage_pct": round(ct_coverage, 1),
        "deep_coverage_pct": round(deep_coverage, 1),
        "error_rate_pct": round(error_rate, 1),
        "avg_metadata_fields": round(avg_fields, 1),
    }

    history = load_previous_metrics(metrics_path)
    if history and history[-1].get("date") == snapshot["date"]:
        history[-1] = snapshot
    else:
        history.append(snapshot)

    with open(metrics_path, "w") as f:
        json.dump({"current": snapshot, "history": history}, f, indent=2)

    report = [
        "# Dataset Quality Report",
        "",
        f"**Generated**: {now.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Current Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total MorphoSource records | {total_records} |",
        f"| CT-to-Text analyses | {ct_text_count} |",
        f"| Deep analyses (download + SlicerMorph) | {deep_count} |",
        f"| CT-to-Text coverage | {ct_coverage:.1f}% |",
        f"| Deep analysis coverage | {deep_coverage:.1f}% |",
        f"| Analysis error rate | {error_rate:.1f}% |",
        f"| Avg metadata fields per analysis | {avg_fields:.1f} |",
        f"| Daily runs | {len(daily)} |",
        f"| Monthly runs | {len(monthly)} |",
        "",
    ]

    if len(history) > 1:
        report += [
            "## Trend (last 4 snapshots)",
            "",
            "| Date | Records | CT Coverage | Deep Coverage | Error Rate |",
            "|------|---------|-------------|---------------|------------|",
        ]
        for h in history[-4:]:
            report.append(
                f"| {h['date']} | {h['total_morphosource_records']} "
                f"| {h['ct_coverage_pct']}% | {h['deep_coverage_pct']}% "
                f"| {h['error_rate_pct']}% |"
            )
        report.append("")

    report += [
        "---",
        "*Generated by the Quality Metrics workflow.*",
    ]

    with open(report_path, "w") as f:
        f.write("\n".join(report))

    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"metrics_file={metrics_path}\n")
            f.write(f"report_file={report_path}\n")
            f.write(f"total_records={total_records}\n")
            f.write(f"ct_coverage={ct_coverage:.1f}\n")

    print(f"Metrics written to {metrics_path}")
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
