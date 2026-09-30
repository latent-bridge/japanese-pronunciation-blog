"""Import an article only after the user has checked the displayed preview."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re

from build import ROOT, read_post


def approve(source, reviewed_on):
    date.fromisoformat(reviewed_on)
    post = read_post(source)
    text = source.read_text(encoding="utf-8")
    header, body = text[4:].split("\n+++\n", 1)
    header, count = re.subn(r'^status\s*=\s*"(?:review|published)"\s*$', 'status = "published"', header, flags=re.M)
    if count != 1:
        raise ValueError('Use a single status = "review" line in the TOML header')
    text = "+++\n" + header + "\n+++\n" + body
    dest = ROOT / "posts" / (post["slug"] + ".md")
    dest.write_text(text, encoding="utf-8")
    receipt = {"sha256": hashlib.sha256(dest.read_bytes()).hexdigest(), "reviewer": "user", "reviewed_on": reviewed_on}
    dest.with_suffix(".approval.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Imported user-reviewed article: {dest.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run only after the user explicitly approves the preview. Does not deploy.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--reviewed-on", required=True)
    parser.add_argument("--user-confirmed", action="store_true", required=True)
    args = parser.parse_args()
    approve(args.source, args.reviewed_on)
