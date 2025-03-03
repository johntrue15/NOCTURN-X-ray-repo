#!/usr/bin/env python3

import os
import json
import glob
import random

def is_valid_entry(entry):
    """Check if the entry is valid for fine-tuning"""
    if not isinstance(entry, dict):
        return False
    
    # Check required fields
    if "input" not in entry or "preferred_output" not in entry or "non_preferred_output" not in entry:
        return False
    
    # Check input structure
    if "messages" not in entry["input"] or not entry["input"]["messages"]:
        return False
    
    # Check output structure
    if not entry["preferred_output"] or not entry["non_preferred_output"]:
        return False
    
    return True

def classify_entry_type(filename, entry):
    """Classify the entry as 2D or 3D based on the release ID"""
    # Extract release ID from filename
    release_id = os.path.basename(filename).replace("release-", "").replace(".jsonl", "")
    
    # Check if we can determine the type from the cached releases file
    if os.path.exists("data/releases_cache.json"):
        with open("data/releases_cache.json", "r") as f:
            try:
                releases = json.load(f)
                if release_id in releases:
                    return releases[release_id]["type"]
            except:
                pass
    
    # If we can't determine, use a heuristic:
    # Look for keywords in the content that might indicate 2D vs 3D
    messages = entry["input"]["messages"]
    content = " ".join([m.get("content", "") for m in messages if isinstance(m, dict)])
    
    if "slice" in content.lower() or "2d" in content.lower():
        return "2d"
    elif "mesh" in content.lower() or "3d" in content.lower():
        return "3d"
    
    # Default to 3D if we can't determine
    return "3d"

# Ensure directories exist
os.makedirs("data/finetune/2d", exist_ok=True)
os.makedirs("data/finetune/3d", exist_ok=True)

# Find all reaction data files
data_files = glob.glob("data/reactions/jsonl/release-*.jsonl")
print(f"Found {len(data_files)} reaction data files")

# Process each file and categorize entries
entries_2d = []
entries_3d = []

for file_path in data_files:
    with open(file_path, "r") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if is_valid_entry(entry):
                    entry_type = classify_entry_type(file_path, entry)
                    if entry_type == "2d":
                        entries_2d.append(entry)
                    else:
                        entries_3d.append(entry)
            except json.JSONDecodeError:
                print(f"Invalid JSON in {file_path}")

print(f"Collected {len(entries_2d)} 2D entries and {len(entries_3d)} 3D entries")

# Shuffle entries
random.shuffle(entries_2d)
random.shuffle(entries_3d)

# Split into training and validation sets (90/10 split)
train_2d = entries_2d[:int(0.9 * len(entries_2d))] if entries_2d else []
val_2d = entries_2d[int(0.9 * len(entries_2d)):] if entries_2d else []

train_3d = entries_3d[:int(0.9 * len(entries_3d))] if entries_3d else []
val_3d = entries_3d[int(0.9 * len(entries_3d)):] if entries_3d else []

# Write to files
if train_2d:
    with open("data/finetune/2d/training.jsonl", "w") as f:
        for entry in train_2d:
            f.write(json.dumps(entry) + "\n")

if val_2d:
    with open("data/finetune/2d/validation.jsonl", "w") as f:
        for entry in val_2d:
            f.write(json.dumps(entry) + "\n")

if train_3d:
    with open("data/finetune/3d/training.jsonl", "w") as f:
        for entry in train_3d:
            f.write(json.dumps(entry) + "\n")

if val_3d:
    with open("data/finetune/3d/validation.jsonl", "w") as f:
        for entry in val_3d:
            f.write(json.dumps(entry) + "\n")

print(f"Wrote {len(train_2d)} training and {len(val_2d)} validation entries for 2D")
print(f"Wrote {len(train_3d)} training and {len(val_3d)} validation entries for 3D") 