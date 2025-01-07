# .github/scripts/extract_url.py
import sys
import re

def extract_url():
    try:
        content = sys.stdin.read()
        match = re.search(r"https://[^\s\)\"']+", content)
        print(match.group(0) if match else "NO_URL_FOUND")
    except Exception as e:
        print("NO_URL_FOUND")

if __name__ == "__main__":
    extract_url()
