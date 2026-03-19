#!/usr/bin/env python3
"""
Generate an interactive taxonomy explorer page for GitHub Pages.

Reads all ct_to_text_analysis releases, extracts taxonomy information, and
builds a collapsible tree view with links back to the source releases.

Outputs:
  docs/taxonomy.html         - the explorer page
  docs/assets/data/taxonomy.json - taxonomy data for JS consumption
"""

import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone


REPO = os.environ.get("GITHUB_REPOSITORY", "johntrue15/NOCTURN-X-ray-repo")


def gh_api(endpoint: str):
    result = subprocess.run(
        ["gh", "api", "-H", "Accept: application/vnd.github+json", endpoint],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


RANK_ORDER = ["phylum", "class", "order", "family", "genus", "species"]


def extract_hierarchy(body: str) -> dict:
    """Extract taxonomic hierarchy from a release body."""
    hierarchy = {}

    rank_patterns = {
        "phylum": [r"(?:phylum|Phylum):\s*([A-Z][a-z]+)"],
        "class": [
            r"(?:class|Class):\s*([A-Z][a-z]+)",
            r"\b(Mammalia|Reptilia|Aves|Amphibia|Actinopterygii|Insecta|Arachnida)\b",
        ],
        "order": [r"(?:order|Order):\s*([A-Z][a-z]+)"],
        "family": [
            r"(?:family|Family):\s*([A-Z][a-z]+idae)",
            r"\b([A-Z][a-z]+idae)\b",
        ],
        "genus": [r"(?:genus|Genus):\s*([A-Z][a-z]+)"],
        "species": [
            r"(?:species|Species):\s*([A-Z][a-z]+ [a-z]+)",
            r"\b([A-Z][a-z]{2,} [a-z]{3,})\b",
        ],
    }

    for rank, patterns in rank_patterns.items():
        for pat in patterns:
            m = re.search(pat, body)
            if m:
                hierarchy[rank] = m.group(1).strip()
                break

    return hierarchy


def build_tree(records: list[dict]) -> dict:
    """
    Build a nested taxonomy tree from extracted records.

    Returns a dict like:
    {
      "name": "All Taxa",
      "children": [
        {
          "name": "Mammalia",
          "rank": "class",
          "children": [...],
          "records": [...]
        }
      ]
    }
    """
    root = {"name": "All Taxa", "rank": "root", "children": [], "count": 0}

    for rec in records:
        hierarchy = rec["hierarchy"]
        if not hierarchy:
            continue

        node = root
        for rank in RANK_ORDER:
            taxon = hierarchy.get(rank)
            if not taxon:
                continue

            child = next(
                (c for c in node["children"] if c["name"] == taxon), None
            )
            if not child:
                child = {
                    "name": taxon,
                    "rank": rank,
                    "children": [],
                    "records": [],
                    "count": 0,
                }
                node["children"].append(child)

            node = child

        node["records"] = node.get("records", [])
        node["records"].append({
            "tag": rec["tag"],
            "media_id": rec.get("media_id", ""),
            "date": rec.get("date", ""),
        })
        node["count"] = node.get("count", 0) + 1

    def propagate_counts(n):
        total = n.get("count", 0)
        for c in n.get("children", []):
            total += propagate_counts(c)
        n["count"] = total
        n["children"].sort(key=lambda x: x["count"], reverse=True)
        return total

    propagate_counts(root)
    return root


def generate_html(tree: dict, timestamp: str) -> str:
    """Generate a self-contained HTML taxonomy explorer page."""
    tree_json = json.dumps(tree)

    return f"""---
layout: default
title: Taxonomy Explorer
---

<link rel="stylesheet" href="assets/css/style.css">
<style>
  .taxonomy-tree {{ font-family: monospace; font-size: 14px; }}
  .tax-node {{ cursor: pointer; padding: 4px 8px; border-radius: 4px; margin: 2px 0; display: inline-block; }}
  .tax-node:hover {{ background: #f1f8ff; }}
  .tax-node .toggle {{ display: inline-block; width: 16px; text-align: center; color: #586069; }}
  .tax-node .name {{ font-weight: 600; }}
  .tax-node .rank {{ color: #6a737d; font-size: 12px; margin-left: 4px; }}
  .tax-node .count {{ color: #0366d6; font-size: 12px; margin-left: 4px; }}
  .tax-children {{ margin-left: 24px; display: none; }}
  .tax-children.expanded {{ display: block; }}
  .tax-records {{ margin-left: 40px; font-size: 12px; color: #586069; }}
  .tax-records a {{ color: #0366d6; text-decoration: none; }}
  .tax-records a:hover {{ text-decoration: underline; }}
  .search-box {{ width: 100%; max-width: 400px; padding: 8px 12px; border: 1px solid #e1e4e8; border-radius: 6px; margin-bottom: 16px; font-size: 14px; }}
  .stats-bar {{ display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }}
  .stat {{ background: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 6px; padding: 12px 16px; text-align: center; }}
  .stat .value {{ font-size: 20px; font-weight: bold; color: #0366d6; }}
  .stat .label {{ font-size: 12px; color: #586069; }}
  .highlight {{ background: #fff3cd; }}
</style>

<h1>Taxonomy Explorer</h1>
<p>Interactive taxonomy tree built from all CT-to-Text analyses.</p>
<p><strong>Last updated:</strong> {timestamp}</p>

<div class="stats-bar" id="stats-bar"></div>

<input type="text" class="search-box" id="search" placeholder="Search for a taxon (e.g., Mammalia, Canis)...">

<div class="taxonomy-tree" id="tree"></div>

<script>
const TREE_DATA = {tree_json};
const REPO_URL = "https://github.com/johntrue15/NOCTURN-X-ray-repo/releases/tag/";

function renderStats(tree) {{
  const bar = document.getElementById('stats-bar');
  const ranks = {{}};
  function walk(node) {{
    if (node.rank && node.rank !== 'root') {{
      ranks[node.rank] = (ranks[node.rank] || 0) + 1;
    }}
    (node.children || []).forEach(walk);
  }}
  walk(tree);

  bar.innerHTML = '<div class="stat"><div class="value">' + tree.count +
    '</div><div class="label">Total Records</div></div>';
  ['class','order','family','genus','species'].forEach(r => {{
    if (ranks[r]) {{
      bar.innerHTML += '<div class="stat"><div class="value">' + ranks[r] +
        '</div><div class="label">' + r.charAt(0).toUpperCase() + r.slice(1) + ' taxa</div></div>';
    }}
  }});
}}

function renderNode(node, container, depth) {{
  if (node.rank === 'root') {{
    (node.children || []).forEach(c => renderNode(c, container, 0));
    return;
  }}

  const wrapper = document.createElement('div');

  const el = document.createElement('div');
  el.className = 'tax-node';
  el.dataset.name = node.name.toLowerCase();

  const hasChildren = (node.children && node.children.length > 0);
  const toggle = hasChildren ? '\\u25B6' : '\\u2022';

  el.innerHTML = '<span class="toggle">' + toggle + '</span>' +
    '<span class="name">' + node.name + '</span>' +
    '<span class="rank">(' + node.rank + ')</span>' +
    '<span class="count">[' + node.count + ']</span>';

  wrapper.appendChild(el);

  const childrenDiv = document.createElement('div');
  childrenDiv.className = 'tax-children';

  if (node.records && node.records.length > 0) {{
    const recDiv = document.createElement('div');
    recDiv.className = 'tax-records';
    node.records.slice(0, 5).forEach(r => {{
      const a = document.createElement('a');
      a.href = REPO_URL + r.tag;
      a.textContent = r.tag.replace('ct_to_text_analysis-', '');
      if (r.media_id) a.textContent += ' (media ' + r.media_id + ')';
      recDiv.appendChild(a);
      recDiv.appendChild(document.createElement('br'));
    }});
    if (node.records.length > 5) {{
      const more = document.createElement('span');
      more.textContent = '... and ' + (node.records.length - 5) + ' more';
      recDiv.appendChild(more);
    }}
    childrenDiv.appendChild(recDiv);
  }}

  (node.children || []).forEach(c => renderNode(c, childrenDiv, depth + 1));
  wrapper.appendChild(childrenDiv);

  el.addEventListener('click', function(e) {{
    e.stopPropagation();
    if (hasChildren || (node.records && node.records.length > 0)) {{
      childrenDiv.classList.toggle('expanded');
      el.querySelector('.toggle').textContent =
        childrenDiv.classList.contains('expanded') ? '\\u25BC' : '\\u25B6';
    }}
  }});

  container.appendChild(wrapper);
}}

function initSearch() {{
  const input = document.getElementById('search');
  input.addEventListener('input', function() {{
    const q = this.value.toLowerCase().trim();
    document.querySelectorAll('.tax-node').forEach(el => {{
      el.classList.remove('highlight');
    }});
    if (!q) return;
    document.querySelectorAll('.tax-node').forEach(el => {{
      if (el.dataset.name.includes(q)) {{
        el.classList.add('highlight');
        let parent = el.parentElement;
        while (parent) {{
          if (parent.classList && parent.classList.contains('tax-children')) {{
            parent.classList.add('expanded');
            const prev = parent.previousElementSibling;
            if (prev && prev.querySelector('.toggle')) {{
              prev.querySelector('.toggle').textContent = '\\u25BC';
            }}
          }}
          parent = parent.parentElement;
        }}
      }}
    }});
  }});
}}

document.addEventListener('DOMContentLoaded', function() {{
  renderStats(TREE_DATA);
  renderNode(TREE_DATA, document.getElementById('tree'), 0);
  initSearch();
}});
</script>

<div class="footer">
  <p>Return to <a href="index.html">main dashboard</a>.</p>
</div>
"""


def main():
    os.makedirs("docs/assets/data", exist_ok=True)

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

    ct_releases = [
        r for r in all_releases
        if r.get("tag_name", "").startswith("ct_to_text_analysis-")
    ]
    print(f"Processing {len(ct_releases)} CT-to-Text releases")

    records = []
    for r in ct_releases:
        body = r.get("body", "") or ""
        hierarchy = extract_hierarchy(body)

        media_match = re.search(r'"media_id"\s*:\s*"?(\d+)"?|Record #(\d+)|media/(\d+)', body)
        media_id = ""
        if media_match:
            media_id = media_match.group(1) or media_match.group(2) or media_match.group(3) or ""

        created = r.get("created_at", "")[:10]

        records.append({
            "tag": r["tag_name"],
            "hierarchy": hierarchy,
            "media_id": media_id,
            "date": created,
        })

    tree = build_tree(records)

    with open("docs/assets/data/taxonomy.json", "w") as f:
        json.dump(tree, f, indent=2)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = generate_html(tree, timestamp)

    with open("docs/taxonomy.html", "w") as f:
        f.write(html)

    print(f"Taxonomy explorer generated: {tree['count']} records, "
          f"{len(tree['children'])} top-level taxa")
    print("Output: docs/taxonomy.html, docs/assets/data/taxonomy.json")


if __name__ == "__main__":
    main()
