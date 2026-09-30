import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build
from check import check

POST = '''+++
title = "長音の確認"
description = "記事の説明"
slug = "long-vowels"
topic = "長音"
date = "2026-09-30"
status = "published"
+++
## 確認

本文
'''


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "posts").mkdir()
        (self.root / "assets").mkdir()
        (self.root / "assets/style.css").touch()
        (self.root / "assets/favicon.svg").touch()
        (self.root / "site.toml").write_text((build.ROOT / "site.toml").read_text())
        self.post = self.root / "posts/long-vowels.md"
        self.post.write_text(POST)
        self.approval = self.post.with_suffix(".approval.json")
        self.approval.write_text(json.dumps({"sha256": hashlib.sha256(self.post.read_bytes()).hexdigest(), "reviewer": "user", "reviewed_on": "2026-09-30"}))

    def tearDown(self):
        self.temp.cleanup()

    def test_changed_article_needs_another_user_review(self):
        self.post.write_text(POST + "未確認の追記")
        with self.assertRaisesRegex(ValueError, "content changed"):
            build.load_posts(self.root / "posts")

    def test_unreviewed_source_cannot_enter_public_posts(self):
        self.post.write_text(POST.replace('status = "published"', 'status = "review"'))
        with self.assertRaisesRegex(ValueError, "outside the public"):
            build.load_posts(self.root / "posts")

    def test_approved_post_builds_for_project_path_and_root(self):
        with patch.object(build, "ROOT", self.root):
            for url, prefix in [("https://example.org/blog", "/blog"), ("https://example.org", "")]:
                out = build.build(url=url)
                check(out, prefix)
                self.assertIn("long-vowels/", (out / "feed.xml").read_text())
                self.assertIn("long-vowels/", (out / "sitemap.xml").read_text())

    def test_private_preview_is_absent_from_production_and_feeds(self):
        draft = self.root / "private-draft.md"
        self.post.rename(draft)
        with patch.object(build, "ROOT", self.root):
            preview = build.build("preview", draft, "https://example.org/blog")
            check(preview, "/blog", allow_preview=True)
            with self.assertRaisesRegex(ValueError, "Refusing"):
                check(preview, "/blog")
            self.assertNotIn("long-vowels", (preview / "feed.xml").read_text())
            out = build.build()
            self.assertFalse((out / "articles/long-vowels/index.html").exists())
            self.assertNotIn("long-vowels", (out / "sitemap.xml").read_text())

    def test_preview_cannot_write_to_dist(self):
        with self.assertRaisesRegex(ValueError, "only write to preview"):
            build.build("dist", self.post)


if __name__ == "__main__":
    unittest.main()
