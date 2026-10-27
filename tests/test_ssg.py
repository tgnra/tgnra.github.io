import shutil
import tempfile
import textwrap
import unittest
import xml.etree.ElementTree as etree
from pathlib import Path

from PIL import Image

from ssg import content
from ssg.build import build
from ssg.markdown_ext import BuildError

ROOT = Path(__file__).resolve().parent.parent


class FrontMatterTest(unittest.TestCase):
    def test_parses_and_coerces(self):
        meta, body = content.parse_front_matter(textwrap.dedent("""\
            ---
            title: "Hello: world"
            draft: true
            nav: 2
            ---
            Body
            """))
        self.assertEqual(meta, {"title": "Hello: world", "draft": True, "nav": 2})
        self.assertEqual(body, "Body\n")

    def test_no_front_matter(self):
        self.assertEqual(content.parse_front_matter("Just text"), ({}, "Just text"))

    def test_unclosed(self):
        with self.assertRaises(ValueError):
            content.parse_front_matter("---\ntitle: x\n")


class SiteTest(unittest.TestCase):
    """Builds a small throwaway site and inspects dist/."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / "site.toml").write_text('title = "T"\nbase_url = "https://ex.com/"\n')
        for d in ("posts", "pages", "images"):
            (self.root / "content" / d).mkdir(parents=True)
        Image.new("RGB", (1000, 500), (200, 100, 50)).save(self.root / "content/images/a.jpg")

    def post(self, name, text):
        (self.root / "content/posts" / name).write_text(textwrap.dedent(text), encoding="utf-8")

    def read(self, path):
        return (self.root / "dist" / path).read_text(encoding="utf-8")

    def build(self):
        return build(self.root, log=lambda msg: None)

    def test_posts_ordered_newest_first_and_drafts_skipped(self):
        self.post("2026-01-01-old.md", "---\ntitle: Old\n---\nOld body\n")
        self.post("2026-03-01-new.md", "---\ntitle: New\n---\nNew body\n")
        self.post("2026-02-01-draft.md", "---\ntitle: Draft\ndraft: true\n---\nx\n")
        self.build()
        index = self.read("index.html")
        self.assertLess(index.index(">New<"), index.index(">Old<"))
        self.assertNotIn("Draft", index)
        self.assertIn("New body", index)  # summary falls back to first paragraph
        self.assertFalse((self.root / "dist/posts/draft").exists())

    def test_feed_is_valid_xml_with_absolute_urls(self):
        self.post("2026-01-01-pic.md", "---\ntitle: Pic\n---\n![A square](../images/a.jpg)\n\n[about](/about/)\n")
        self.build()
        rss = etree.fromstring(self.read("feed.xml"))
        item = rss.find("channel/item")
        self.assertEqual(item.findtext("link"), "https://ex.com/posts/pic/")
        encoded = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
        self.assertIn('src="https://ex.com/img/', encoded)
        self.assertIn('href="https://ex.com/about/"', encoded)
        self.assertNotIn("data:image", encoded)

    def test_image_markup(self):
        self.post("2026-01-01-pic.md", '---\ntitle: Pic\n---\n![A square](../images/a.jpg "Caption")\n')
        self.build()
        html = self.read("posts/pic/index.html")
        for needle in ('<figure class="img">', 'width="1000"', 'height="500"', "data-eager",
                       'src="data:image/png;base64,', "data-dither=", "data-lite=", "data-full=",
                       'type="image/avif"', "<noscript>",
                       'class="zoom"', "<figcaption>Caption</figcaption>"):
            self.assertIn(needle, html)
        self.assertIn("IntersectionObserver", html)  # loader only on pages with images
        self.assertNotIn("IntersectionObserver", self.read("index.html"))

    def test_theme_toggle_on_every_page(self):
        self.post("2026-01-01-a.md", "---\ntitle: A\n---\nx\n")
        self.build()
        for page in ("index.html", "posts/a/index.html", "404.html"):
            html = self.read(page)
            self.assertIn('class="theme-toggle" aria-pressed="false"', html)
            self.assertIn('localStorage.getItem("theme")', html)
        self.assertNotIn("img-quality", self.read("posts/a/index.html"))

    def test_decorative_image_is_not_a_link(self):
        self.post("2026-01-01-pic.md", '---\ntitle: Pic\n---\n![""](../images/a.jpg)\n')
        self.build()
        html = self.read("posts/pic/index.html")
        self.assertIn('alt=""', html)
        self.assertNotIn('class="zoom"', html)

    def test_missing_alt_fails(self):
        self.post("2026-01-01-pic.md", "---\ntitle: Pic\n---\n![](../images/a.jpg)\n")
        with self.assertRaises(BuildError):
            self.build()

    def test_headings_shift_below_title(self):
        self.post("2026-01-01-h.md", "---\ntitle: H\n---\n# One\n\n## Two\n\n```\ncode\n```\n")
        self.build()
        html = self.read("posts/h/index.html")
        self.assertIn('<h2 id="one">One</h2>', html)
        self.assertIn('<h3 id="two">Two</h3>', html)
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn('<pre tabindex="0">', html)

    def test_pagination(self):
        (self.root / "site.toml").write_text('title = "T"\nposts_per_page = 2\n')
        for day in range(1, 6):
            self.post(f"2026-01-0{day}-p{day}.md", f"---\ntitle: P{day}\n---\nx\n")
        self.build()
        self.assertTrue((self.root / "dist/page/3/index.html").exists())
        self.assertIn('rel="next"', self.read("index.html"))
        self.assertIn('rel="prev"', self.read("page/3/index.html"))


class SampleSiteTest(unittest.TestCase):
    def test_sample_content_builds(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        shutil.copytree(ROOT / "content", root / "content", ignore=shutil.ignore_patterns("*stress*"))
        shutil.copy(ROOT / "site.toml", root / "site.toml")
        self.assertEqual(build(root, log=lambda msg: None), [])


if __name__ == "__main__":
    unittest.main()
