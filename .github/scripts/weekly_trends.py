#!/usr/bin/env python3
"""
Analyse trends in MorphoSource additions over the past week.

Reads recent releases via the GitHub API, classifies them by taxonomy,
institution and scan type, compares counts to the prior week, and writes
a Markdown trend report.

Outputs:
  - weekly_trends.md   in the current working directory
  - GITHUB_OUTPUT vars: report_file, total_new, top_taxonomy
"""

import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone


REPO = os.environ.get("GITHUB_REPOSITORY", "johntrue15/NOCTURN-X-ray-repo")


def gh_api(endpoint: str):
    result = subprocess.run(
        ["gh", "api", "-H", "Accept: application/vnd.github+json", endpoint],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"gh api error: {result.stderr}", file=sys.stderr)
        return None
    return json.loads(result.stdout)


def parse_release_date(release: dict) -> datetime | None:
    created = release.get("created_at", "")
    try:
        return datetime.fromisoformat(created.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def extract_taxonomy(body: str) -> str:
    """Best-effort extraction of the highest taxonomic name mentioned."""
    patterns = [
        r"(?:species|Species):\s*([A-Z][a-z]+ [a-z]+)",
        r"(?:genus|Genus):\s*([A-Z][a-z]+)",
        r"(?:family|Family):\s*([A-Z][a-z]+idae)",
        r"(?:order|Order):\s*([A-Z][a-z]+)",
    ]
    for pat in patterns:
        m = re.search(pat, body)
        if m:
            return m.group(1)

    m = re.search(r"\b([A-Z][a-z]{2,} [a-z]{3,})\b", body)
    if m:
        return m.group(1)
    return "Unknown"


def extract_institution(body: str) -> str:
    patterns = [
        r"(?:institution|Institution):\s*(.+?)(?:\n|$)",
        r"(?:repository|Repository):\s*(.+?)(?:\n|$)",
    ]
    for pat in patterns:
        m = re.search(pat, body)
        if m:
            return m.group(1).strip()[:60]
    return "Unknown"


def extract_modality(body: str) -> str:
    body_lower = body.lower()
    if "micro-ct" in body_lower or "microct" in body_lower:
        return "Micro-CT"
    if "ct scan" in body_lower or "x-ray ct" in body_lower:
        return "CT"
    if "mri" in body_lower:
        return "MRI"
    if "surface scan" in body_lower:
        return "Surface Scan"
    return "Other"


def bucket_releases(releases: list[dict], start: datetime, end: datetime) -> list[dict]:
    """Filter releases to those created between start and end."""
    out = []
    for r in releases:
        dt = parse_release_date(r)
        if dt and start <= dt < end:
            out.append(r)
    return out


def build_report(
    this_week: list[dict],
    last_week: list[dict],
    week_start: datetime,
    week_end: datetime,
) -> str:
    """Generate Markdown trend report."""
    tw_taxonomy = Counter()
    tw_institution = Counter()
    tw_modality = Counter()

    for r in this_week:
        body = r.get("body", "") or ""
        tw_taxonomy[extract_taxonomy(body)] += 1
        tw_institution[extract_institution(body)] += 1
        tw_modality[extract_modality(body)] += 1

    lw_taxonomy = Counter()
    for r in last_week:
        body = r.get("body", "") or ""
        lw_taxonomy[extract_taxonomy(body)] += 1

    delta = len(this_week) - len(last_week)
    direction = "up" if delta > 0 else ("down" if delta < 0 else "flat")

    lines = [
        f"# Weekly MorphoSource Trend Report",
        f"",
        f"**Period**: {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}",
        f"",
        f"## Summary",
        f"",
        f"| Metric | This Week | Last Week | Change |",
        f"|--------|-----------|-----------|--------|",
        f"| New CT-to-Text analyses | {len(this_week)} | {len(last_week)} | {'+' if delta > 0 else ''}{delta} ({direction}) |",
        f"",
        f"## Taxonomy Breakdown",
        f"",
        f"| Taxon | Count | Change vs Last Week |",
        f"|-------|-------|---------------------|",
    ]

    all_taxa = set(tw_taxonomy) | set(lw_taxonomy)
    for taxon in sorted(all_taxa, key=lambda t: tw_taxonomy.get(t, 0), reverse=True):
        tw = tw_taxonomy.get(taxon, 0)
        lw = lw_taxonomy.get(taxon, 0)
        d = tw - lw
        lines.append(f"| {taxon} | {tw} | {'+' if d > 0 else ''}{d} |")

    lines += [
        f"",
        f"## Institution Breakdown",
        f"",
        f"| Institution | Count |",
        f"|-------------|-------|",
    ]
    for inst, count in tw_institution.most_common(15):
        lines.append(f"| {inst} | {count} |")

    lines += [
        f"",
        f"## Scan Modality",
        f"",
        f"| Modality | Count |",
        f"|----------|-------|",
    ]
    for mod, count in tw_modality.most_common():
        lines.append(f"| {mod} | {count} |")

    emerging = [
        t for t in tw_taxonomy
        if tw_taxonomy[t] >= 2 and t not in lw_taxonomy
    ]
    if emerging:
        lines += [
            f"",
            f"## Emerging Research Areas",
            f"",
            f"The following taxa appeared multiple times this week but not last week:",
            f"",
        ]
        for t in emerging:
            lines.append(f"- **{t}** ({tw_taxonomy[t]} records)")

    lines += [
        f"",
        f"---",
        f"*Generated automatically by the Weekly Trend Report workflow.*",
    ]

    return "\n".join(lines)


def main():
    now = datetime.now(timezone.utc)
    week_end = now
    week_start = now - timedelta(days=7)
    prev_week_start = week_start - timedelta(days=7)

    print(f"This week:  {week_start.isoformat()} .. {week_end.isoformat()}")
    print(f"Last week:  {prev_week_start.isoformat()} .. {week_start.isoformat()}")

    all_releases = gh_api(f"/repos/{REPO}/releases?per_page=100") or []

    ct_releases = [
        r for r in all_releases
        if r.get("tag_name", "").startswith("ct_to_text_analysis-")
    ]
    ms_releases = [
        r for r in all_releases
        if r.get("tag_name", "").startswith("morphosource-api-")
    ]
    combined = ct_releases + ms_releases

    this_week = bucket_releases(combined, week_start, week_end)
    last_week = bucket_releases(combined, prev_week_start, week_start)

    print(f"This week: {len(this_week)} releases")
    print(f"Last week: {len(last_week)} releases")

    report = build_report(this_week, last_week, week_start, week_end)

    with open("weekly_trends.md", "w") as f:
        f.write(report)

    top_taxonomy = "N/A"
    if this_week:
        taxa = Counter()
        for r in this_week:
            taxa[extract_taxonomy(r.get("body", "") or "")] += 1
        top_taxonomy = taxa.most_common(1)[0][0] if taxa else "N/A"

    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"report_file=weekly_trends.md\n")
            f.write(f"total_new={len(this_week)}\n")
            f.write(f"top_taxonomy={top_taxonomy}\n")

    print(f"\nReport written to weekly_trends.md")
    print(f"Top taxonomy: {top_taxonomy}")


if __name__ == "__main__":
    main()
