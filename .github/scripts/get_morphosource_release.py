# .github/scripts/get_morphosource_release.py
import sys
import json

def get_latest_morphosource():
    try:
        releases = json.load(sys.stdin)
        morpho_releases = [r for r in releases if r.get("tag_name", "").startswith("morphosource-updates-")]
        
        if morpho_releases:
            latest = morpho_releases[0]
            print(json.dumps({
                "body": latest.get("body", ""),
                "tag_name": latest.get("tag_name", "")
            }))
        else:
            print("{}")
    except Exception as e:
        print("{}")

if __name__ == "__main__":
    get_latest_morphosource()
