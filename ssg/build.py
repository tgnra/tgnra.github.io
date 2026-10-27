"""Build the site: content/ + assets/ + site.toml -> dist/."""

import datetime as dt
import math
import shutil
import time
import tomllib
from pathlib import Path

from . import content, feed
from .images import ImageProcessor
from .markdown_ext import BlogExtension, BuildError, figure_html, make_markdown
from .templates import Templates, index_url

DEFAULTS = {
    "title": "My blog",
    "description": "",
    "base_url": "http://localhost:8000",
    "author": "",
    "language": "en",
    "posts_per_page": 10,
    "feed_items": 20,
    "nav": [{"title": "Home", "href": "/"}],
}


def load_config(root):
    site = dict(DEFAULTS)
    path = Path(root) / "site.toml"
    if path.exists():
        site.update(tomllib.loads(path.read_text(encoding="utf-8")))
    site["base_url"] = site["base_url"].rstrip("/")
    site.setdefault("year", dt.date.today().year)
    return site


def build(root=".", drafts=False, log=print):
    started = time.perf_counter()
    root = Path(root).resolve()
    site = load_config(root)
    content_dir = root / "content"
    dist = root / "dist"
    warnings = []

    def warn(msg):
        warnings.append(msg)
        log(f"warning: {msg}")

    posts, pages = content.load_all(content_dir, drafts=drafts)
    site["nav"] = list(site["nav"]) + [
        {"title": p.title, "href": p.url}
        for p in sorted((p for p in pages if p.nav is not None), key=lambda p: p.nav)
    ]

    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir()
    images = ImageProcessor(dist / "img", root / ".cache" / "images")
    page_ext = BlogExtension(images, content_dir, warn=warn)
    feed_ext = BlogExtension(images, content_dir, mode="feed", base_url=site["base_url"],
                             warn=lambda msg: None)
    page_md, feed_md = make_markdown(page_ext), make_markdown(feed_ext)
    t = Templates(site)

    for doc in posts + pages:
        hero = None
        if doc.hero:
            if "hero_alt" not in doc.meta:
                raise BuildError(f'{doc.source}: hero needs hero_alt (hero_alt: "" if decorative)')
            hero = images.process(page_ext.resolve(doc.hero, doc.source))
        page_ext.begin(doc.source, eager_first=doc.kind == "post" and not hero)
        doc.html = page_md.reset().convert(doc.body)
        doc.summary = doc.summary or page_ext.first_paragraph
        if doc.kind == "post":
            feed_ext.begin(doc.source)
            doc.feed_html = feed_md.reset().convert(doc.body)
            if hero:
                doc.feed_html = figure_html(hero, doc.hero_alt, mode="feed",
                                            base_url=site["base_url"]) + doc.feed_html
            hero_html = figure_html(hero, doc.hero_alt, eager=True) if hero else ""
            write(dist, doc.url, t.post(doc, hero_html))
        else:
            write(dist, doc.url, t.page(doc))

    per_page = site["posts_per_page"]
    n_pages = max(1, math.ceil(len(posts) / per_page))
    for n in range(1, n_pages + 1):
        write(dist, index_url(n), t.index(posts[(n - 1) * per_page: n * per_page], n, n_pages))

    (dist / "404.html").write_text(t.not_found(), encoding="utf-8")
    (dist / "feed.xml").write_text(feed.rss(site, posts), encoding="utf-8")
    urls = [(index_url(n), None) for n in range(1, n_pages + 1)]
    urls += [(d.url, d.date) for d in posts + pages]
    (dist / "sitemap.xml").write_text(feed.sitemap(site, urls), encoding="utf-8")
    (dist / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {site['base_url']}/sitemap.xml\n")
    # Netlify / Cloudflare Pages header rules: hashed images never change.
    (dist / "_headers").write_text("/img/*\n  Cache-Control: public, max-age=31536000, immutable\n")
    static = content_dir / "static"
    if static.is_dir():
        shutil.copytree(static, dist, dirs_exist_ok=True)

    n_images = len(list((dist / "img").glob("*"))) if (dist / "img").exists() else 0
    log(f"built {len(posts)} posts, {len(pages)} pages, {n_images} image files "
        f"in {time.perf_counter() - started:.2f}s -> {dist}")
    return warnings


def write(dist, url, html):
    path = dist / url.strip("/") / "index.html" if url.endswith("/") else dist / url.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
