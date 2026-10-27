"""Build the site: content/ + assets/ + site.toml -> dist/."""

import datetime as dt
import math
import re
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


GIRO = re.compile(r"giro(\d+)\.apk")


def load_config(root, base_url=None):
    site = dict(DEFAULTS)
    path = Path(root) / "site.toml"
    if path.exists():
        site.update(tomllib.loads(path.read_text(encoding="utf-8")))
    if base_url:
        site["base_url"] = base_url
    site["base_url"] = site["base_url"].rstrip("/")
    site.setdefault("year", dt.date.today().year)
    return site


def build(root=".", drafts=False, base_url=None, log=print):
    started = time.perf_counter()
    root = Path(root).resolve()
    site = load_config(root, base_url)
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

    # Empty dist/ rather than deleting it: on Windows a server or Explorer
    # window holding the folder open would make the delete fail.
    dist.mkdir(exist_ok=True)
    for child in dist.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()
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
    (dist / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nDisallow: /giro/\nSitemap: {site['base_url']}/sitemap.xml\n")
    # Netlify / Cloudflare Pages header rules (GitHub Pages ignores this file):
    # hashed images never change; giro/ stays out of search results.
    (dist / "_headers").write_text(
        "/img/*\n  Cache-Control: public, max-age=31536000, immutable\n"
        "/giro/*\n  X-Robots-Tag: noindex, nofollow\n")
    static = content_dir / "static"
    if static.is_dir():
        shutil.copytree(static, dist, dirs_exist_ok=True)
    if giro := copy_giro(content_dir / "downloads", dist / "giro", log):
        write(dist, "/giro/", t.giro(*giro))

    n_images = len(list((dist / "img").glob("*"))) if (dist / "img").exists() else 0
    log(f"built {len(posts)} posts, {len(pages)} pages, {n_images} image files "
        f"in {time.perf_counter() - started:.2f}s -> {dist}")
    return warnings


def copy_giro(downloads, out, log):
    """Publish the highest-numbered giro<N>.apk plus version.txt containing N.

    Returns (filename, version, size in bytes), or None when there is no APK.
    """
    if not downloads.is_dir():
        return
    found = [(int(m.group(1)), p) for p in downloads.iterdir()
             if p.is_file() and (m := GIRO.fullmatch(p.name))]
    if not found:
        return
    version, apk = max(found)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(apk, out / apk.name)
    (out / "version.txt").write_text(str(version), encoding="utf-8")
    log(f"giro: {apk.name} (version {version})")
    return apk.name, version, apk.stat().st_size


def write(dist, url, html):
    path = dist / url.strip("/") / "index.html" if url.endswith("/") else dist / url.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
