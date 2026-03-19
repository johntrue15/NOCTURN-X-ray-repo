#!/usr/bin/env python3
"""
Compare a freshly deep-analyzed specimen to similar records in the dataset.

Uses OpenAI to generate a comparative summary based on taxonomy and body
region matches found in recent CT-to-Text releases.

Inputs (env vars):
  MEDIA_ID      - media ID of today's deep-analysed record
  SOURCE_TAG    - ct_to_text_analysis tag used for this record
  GH_TOKEN      - GitHub token
  OPENAI_API_KEY

Outputs:
  comparison_report.md  in cwd
  GITHUB_OUTPUT: report_file, similar_count
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "johntrue15/NOCTURN-X-ray-repo")
MEDIA_ID = os.environ.get("MEDIA_ID", "")
SOURCE_TAG = os.environ.get("SOURCE_TAG", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


def gh_api(endpoint: str):
    result = subprocess.run(
        ["gh", "api", "-H", "Accept: application/vnd.github+json", endpoint],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


def extract_taxonomy(body: str) -> list[str]:
    """Extract taxonomy keywords for similarity matching."""
    terms = []
    patterns = [
        r"(?:species|Species):\s*([A-Z][a-z]+ [a-z]+)",
        r"(?:genus|Genus):\s*([A-Z][a-z]+)",
        r"(?:family|Family):\s*([A-Z][a-z]+idae)",
        r"(?:order|Order):\s*([A-Z][a-z]+)",
        r"(?:class|Class):\s*([A-Z][a-z]+)",
    ]
    for pat in patterns:
        for m in re.finditer(pat, body):
            terms.append(m.group(1).strip())

    binomials = re.findall(r"\b([A-Z][a-z]{2,} [a-z]{3,})\b", body)
    terms.extend(binomials[:3])
    return list(set(terms))


def extract_body_region(body: str) -> list[str]:
    regions = []
    keywords = [
        "skull", "cranium", "mandible", "femur", "humerus", "vertebra",
        "pelvis", "endocast", "brain", "tooth", "shell", "wing",
        "thorax", "abdomen", "whole body", "skeleton",
    ]
    body_lower = body.lower()
    for kw in keywords:
        if kw in body_lower:
            regions.append(kw)
    return regions


def find_similar_releases(target_body: str, all_ct_releases: list[dict]) -> list[dict]:
    """Find releases that share taxonomy or body region with the target."""
    target_taxa = set(t.lower() for t in extract_taxonomy(target_body))
    target_regions = set(extract_body_region(target_body))

    similar = []
    for r in all_ct_releases:
        tag = r.get("tag_name", "")
        if tag == SOURCE_TAG:
            continue
        body = r.get("body", "") or ""
        taxa = set(t.lower() for t in extract_taxonomy(body))
        regions = set(extract_body_region(body))

        taxonomy_overlap = target_taxa & taxa
        region_overlap = target_regions & regions

        if taxonomy_overlap or region_overlap:
            similar.append({
                "tag": tag,
                "body": body[:2000],
                "taxonomy_overlap": list(taxonomy_overlap),
                "region_overlap": list(region_overlap),
                "score": len(taxonomy_overlap) * 2 + len(region_overlap),
            })

    similar.sort(key=lambda x: x["score"], reverse=True)
    return similar[:5]


def generate_comparison(target_body: str, similar: list[dict]) -> str:
    """Use OpenAI to generate a comparative analysis."""
    if not OPENAI_API_KEY:
        return _fallback_comparison(target_body, similar)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        similar_summaries = ""
        for i, s in enumerate(similar, 1):
            similar_summaries += (
                f"\n### Similar Record {i} ({s['tag']})\n"
                f"Taxonomy overlap: {', '.join(s['taxonomy_overlap']) or 'none'}\n"
                f"Body region overlap: {', '.join(s['region_overlap']) or 'none'}\n"
                f"Description excerpt: {s['body'][:800]}\n"
            )

        prompt = (
            "You are a comparative morphology analyst. Given a target CT scan "
            "analysis and several similar records, write a concise comparative "
            "report highlighting:\n"
            "1. How the target specimen compares to similar ones\n"
            "2. Unique features of the target\n"
            "3. Common patterns across similar specimens\n"
            "4. Research significance\n\n"
            f"## Target Specimen (media {MEDIA_ID})\n{target_body[:2000]}\n\n"
            f"## Similar Records\n{similar_summaries}\n\n"
            "Write a Markdown report with clear sections."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"OpenAI error: {e}", file=sys.stderr)
        return _fallback_comparison(target_body, similar)


def _fallback_comparison(target_body: str, similar: list[dict]) -> str:
    """Fallback when OpenAI is unavailable."""
    target_taxa = extract_taxonomy(target_body)
    target_regions = extract_body_region(target_body)

    lines = [
        "## Cross-Specimen Comparison",
        "",
        f"**Target media**: `{MEDIA_ID}`",
        f"**Taxonomy**: {', '.join(target_taxa) or 'Unknown'}",
        f"**Body regions**: {', '.join(target_regions) or 'Unknown'}",
        "",
        f"### Similar Records Found: {len(similar)}",
        "",
    ]

    for i, s in enumerate(similar, 1):
        lines.append(f"**{i}. {s['tag']}**")
        if s["taxonomy_overlap"]:
            lines.append(f"  - Shared taxonomy: {', '.join(s['taxonomy_overlap'])}")
        if s["region_overlap"]:
            lines.append(f"  - Shared body regions: {', '.join(s['region_overlap'])}")
        lines.append("")

    return "\n".join(lines)


def main():
    if not MEDIA_ID or not SOURCE_TAG:
        print("MEDIA_ID and SOURCE_TAG are required", file=sys.stderr)
        sys.exit(1)

    releases = gh_api(f"/repos/{REPO}/releases?per_page=100") or []
    ct_releases = [
        r for r in releases
        if r.get("tag_name", "").startswith("ct_to_text_analysis-")
    ]

    target_release = next(
        (r for r in ct_releases if r.get("tag_name") == SOURCE_TAG),
        None,
    )
    if not target_release:
        print(f"Source release {SOURCE_TAG} not found among CT releases")
        target_body = f"Media ID: {MEDIA_ID}"
    else:
        target_body = target_release.get("body", "") or ""

    similar = find_similar_releases(target_body, ct_releases)
    print(f"Found {len(similar)} similar records")

    report = generate_comparison(target_body, similar)

    header = (
        f"# Cross-Specimen Comparison Report\n\n"
        f"**Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"**Media ID**: `{MEDIA_ID}`\n"
        f"**Source**: {SOURCE_TAG}\n\n"
    )

    with open("comparison_report.md", "w") as f:
        f.write(header + report)

    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"report_file=comparison_report.md\n")
            f.write(f"similar_count={len(similar)}\n")

    print(f"Report written to comparison_report.md")


if __name__ == "__main__":
    main()
