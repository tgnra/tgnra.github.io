import shutil
import tempfile
import unittest
import xml.etree.ElementTree as etree
from pathlib import Path

from ssg.build import build


class ExtrasTest(unittest.TestCase):
    """giro/ downloads, robots/sitemap rules and the --base-url override."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / "site.toml").write_text('title = "T"\nbase_url = "https://ex.com/"\n')
        for d in ("posts", "pages"):
            (self.root / "content" / d).mkdir(parents=True)
        (self.root / "content/posts/2026-01-01-a.md").write_text("---\ntitle: A\n---\nx\n")
        self.logs = []

    def downloads(self, *names):
        d = self.root / "content/downloads"
        d.mkdir(exist_ok=True)
        for name in names:
            (d / name).write_bytes(name.encode())

    def build(self, **kwargs):
        return build(self.root, log=self.logs.append, **kwargs)

    def dist(self, path=""):
        return self.root / "dist" / path

    def test_highest_numbered_apk_is_published(self):
        self.downloads("giro2.apk", "giro10.apk", "giro9.apk",
                       "giro.apk", "giro11.apk.bak", "Giro12.apk", "notes.txt")
        self.build()
        self.assertEqual(sorted(p.name for p in self.dist("giro").iterdir()),
                         ["giro10.apk", "index.html", "version.txt"])
        page = self.dist("giro/index.html").read_text(encoding="utf-8")
        self.assertIn('<a href="/giro/giro10.apk" download', page)
        self.assertIn('<meta name="robots" content="noindex">', page)
        self.assertEqual(self.dist("giro/version.txt").read_bytes(), b"10")
        self.assertEqual(self.dist("giro/giro10.apk").read_bytes(), b"giro10.apk")
        self.assertIn("giro: giro10.apk (version 10)", self.logs)

    def test_no_downloads_means_no_giro(self):
        self.build()
        self.assertFalse(self.dist("giro").exists())

    def test_no_matching_files_means_no_giro(self):
        self.downloads("other.apk")
        self.build()
        self.assertFalse(self.dist("giro").exists())

    def test_hidden_from_search_engines(self):
        self.downloads("giro3.apk")
        self.build()
        self.assertIn("Disallow: /giro/", self.dist("robots.txt").read_text())
        self.assertNotIn("giro", self.dist("sitemap.xml").read_text())
        self.assertIn("/giro/*\n  X-Robots-Tag: noindex, nofollow", self.dist("_headers").read_text())

    def test_base_url_override(self):
        self.build(base_url="https://user.github.io/")
        channel = etree.fromstring(self.dist("feed.xml").read_text(encoding="utf-8")).find("channel")
        self.assertEqual(channel.findtext("link"), "https://user.github.io/")
        self.assertEqual(channel.find("item").findtext("link"), "https://user.github.io/posts/a/")
        html = self.dist("posts/a/index.html").read_text(encoding="utf-8")
        self.assertIn('<link rel="canonical" href="https://user.github.io/posts/a/">', html)


if __name__ == "__main__":
    unittest.main()
