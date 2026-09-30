"""Check generated links, metadata, and review isolation before deployment."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links, self.ids, self.meta = [], set(), {}
        self.title = False
        self.lang = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "title":
            self.title = True
        if tag == "meta":
            self.meta[a.get("name")] = a.get("content", "")
        if tag in ("a", "link") and a.get("href"):
            self.links.append(a["href"])
        if tag in ("img", "script", "audio", "source") and a.get("src"):
            self.links.append(a["src"])


def check(root, prefix="", allow_preview=False):
    root = Path(root).resolve()
    manifest = json.loads((root / "build.json").read_text())
    if manifest["preview"] and not allow_preview:
        raise ValueError("Refusing to deploy a review preview")
    pages = {p.resolve(): Page(p.read_text()) for p in root.rglob("*.html")}
    for path, page in pages.items():
        if not page.title or page.lang != "zh-Hant-TW" or not page.meta.get("description") or "viewport" not in page.meta:
            raise ValueError(f"Missing page metadata: {path}")
        if manifest["preview"] and "noindex" not in page.meta.get("robots", ""):
            raise ValueError("Preview is missing noindex")
        for href in page.links:
            url = urlsplit(href)
            if url.scheme or url.netloc:
                continue
            local = unquote(url.path)
            if local.startswith("/"):
                if prefix and not local.startswith(prefix + "/"):
                    raise ValueError(f"Missing project path prefix: {href}")
                target = root / local[len(prefix):].lstrip("/")
            else:
                target = path.parent / local if local else path
            if target.is_dir():
                target = target / "index.html"
            target = target.resolve()
            if not target.is_relative_to(root) or not target.is_file():
                raise ValueError(f"Broken link in {path.name}: {href}")
            if url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                raise ValueError(f"Broken fragment: {href}")
    for name in ("feed.xml", "sitemap.xml"):
        ET.parse(root / name)
    print(f"Checked {len(pages)} pages: internal links, fragments, metadata, XML, review isolation")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("--prefix", default="")
    parser.add_argument("--allow-preview", action="store_true")
    args = parser.parse_args()
    check(args.root, args.prefix, args.allow_preview)
