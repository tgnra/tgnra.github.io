"""HTML templates as plain functions. All interpolated text goes through esc()."""

import re
from html import escape
from pathlib import Path

from markdown.serializers import to_html_string

from .markdown_ext import image

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def esc(s):
    return escape(str(s), quote=True)


def _minify_css(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    return re.sub(r"\s*([{};,>])\s*", r"\1", css).strip()


def _minify_js(js):
    # Only strips whole-line comments and indentation; safe for our own scripts.
    lines = (line.strip() for line in js.splitlines())
    return "\n".join(line for line in lines if line and not line.startswith("//"))


class Templates:
    def __init__(self, site, assets_dir=ASSETS):
        self.site = site
        self.css = _minify_css((assets_dir / "style.css").read_text(encoding="utf-8"))
        self.head_js = _minify_js((assets_dir / "head.js").read_text(encoding="utf-8"))
        self.img_js = _minify_js((assets_dir / "img.js").read_text(encoding="utf-8"))
        self.theme_js = _minify_js((assets_dir / "theme.js").read_text(encoding="utf-8"))

    # -- layout ---------------------------------------------------------------

    def layout(self, *, title, body, path, description="", has_images=False, noindex=False,
               wide=False):
        site = self.site
        full_title = site["title"] if title == site["title"] else f"{title} – {site['title']}"
        canonical = site["base_url"] + path
        robots = '<meta name="robots" content="noindex">' if noindex else ""
        scripts = f"<script>{self.img_js}</script>" if has_images else ""
        return _tidy(f"""<!doctype html>
<html lang="{esc(site['language'])}" class="no-js">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description or site['description'])}">
<meta name="color-scheme" content="light dark">
<link rel="canonical" href="{esc(canonical)}">
<link rel="alternate" type="application/rss+xml" title="{esc(site['title'])}" href="/feed.xml">
<link rel="alternate" type="application/rss+xml" title="{esc(site['title'])} – photos" href="/photos.xml">
<link rel="preload" href="/fonts/adamina.woff2" as="font" type="font/woff2" crossorigin>
<link rel="icon" href="{esc(site.get('favicon') or 'data:,')}">
{robots}
<script>{self.head_js}</script>
<style>{self.css}</style>
</head>
<body{' class="wide"' if wide else ''}>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
<div class="wrap">
<a class="site-title" href="/">{esc(site['title'])}</a>
{self.nav(path)}
</div>
</header>
<main id="main"{"" if wide else ' class="wrap"'} tabindex="-1">
{body}
</main>
<script>{self.theme_js}</script>
{scripts}
</body>
</html>
""")

    def nav(self, path):
        items = []
        for item in self.site["nav"]:
            href = item["href"]
            current = ' aria-current="page"' if href == path else ""
            items.append(f'<li><a href="{esc(href)}"{current}>{esc(item["title"])}</a></li>')
        # Revealed by theme.js; without JS the system setting applies.
        items.append(f'<li hidden><button type="button" class="theme-toggle" aria-pressed="false"'
                     f' title="Dark theme">{THEME_ICON}<span class="vh">Dark theme</span></button></li>')
        return f'<nav aria-label="Main"><ul>{"".join(items)}</ul></nav>'

    # -- pages ----------------------------------------------------------------

    def post(self, doc, hero_html=""):
        body = f"""<article class="post">
<header>
<h1>{esc(doc.title)}</h1>
<p class="meta">{time_tag(doc.date)}</p>
</header>
{hero_html}
{doc.html}
</article>"""
        return self.layout(title=doc.title, body=body, path=doc.url,
                           description=doc.summary, has_images=_has_images(body))

    def page(self, doc):
        body = f"<h1>{esc(doc.title)}</h1>\n{doc.html}"
        return self.layout(title=doc.title, body=body, path=doc.url,
                           description=doc.summary, has_images=_has_images(body))

    def index(self, entries, page, pages):
        """The homepage: albums and posts mixed, newest first."""
        items = []
        for i, e in enumerate(entries):
            items.append(self.album_card(e, eager=(i == 0)) if e.kind == "album" else self.post_row(e))
        heading = "" if page == 1 else f'<h1 class="home-col">Page {page} of {pages}</h1>'
        body = f"""<h1 class="vh">{esc(self.site['title'])}</h1>
{heading}
<div class="entries">
{"".join(items)}
</div>
<div class="home-col">{self.pagination(page, pages)}</div>"""
        path = index_url(page)
        title = self.site["title"] if page == 1 else f"Page {page}"
        return self.layout(title=title, body=body, path=path, wide=True, has_images=_has_images(body))

    def post_row(self, p):
        return f"""<article class="entry post-row"><div class="home-col row">
<h2><a href="{esc(p.url)}">{esc(p.title)}</a></h2>
<div class="side">
<p class="meta"><span class="tag">Post</span> {time_tag(p.date)}</p>
<p>{esc(p.summary)}</p>
</div>
</div></article>
"""

    def album_card(self, a, eager=False):
        shots = "".join(
            f'<div style="--ar:{ph.info.width / ph.info.height:.4f}">'
            + _img(ph.info, "", STRIP_SIZES, link=False, noupgrade=True, eager=eager and n == 0)
            + "</div>"
            for n, ph in enumerate(a.home_photos()))
        count = f"{len(a.photos)} photo{'s' if len(a.photos) != 1 else ''}"
        return f"""<article class="entry album-card">
<div class="strip">{shots}</div>
<div class="album-title">
<p class="meta"><span class="tag">Album</span> {time_tag(a.date)} · {count}</p>
<h2><a href="{esc(a.url)}">{esc(a.title)}</a></h2>
{f'<p class="summary">{esc(a.summary)}</p>' if a.summary else ''}
</div>
</article>
"""

    def album(self, a):
        figs = []
        for n, ph in enumerate(a.photos):
            cap = f"\n<figcaption>{esc(ph.caption)}</figcaption>" if ph.caption else ""
            figs.append(f'<figure style="--ar:{ph.info.width / ph.info.height:.4f}">'
                        + _img(ph.info, ph.alt, GALLERY_SIZES, eager=n < 2) + cap + "</figure>")
        count = f"{len(a.photos)} photo{'s' if len(a.photos) != 1 else ''}"
        body = f"""<div class="home-col album-page">
<header>
<h1>{esc(a.title)}</h1>
<p class="meta">{time_tag(a.date)} · {count}</p>
</header>
<div class="album-text">{a.html}</div>
</div>
<div class="gallery home-col">
{"".join(figs)}
</div>"""
        return self.layout(title=a.title, body=body, path=a.url, description=a.summary,
                           wide=True, has_images=_has_images(body))

    def albums_index(self, albums):
        cards = "".join(self.album_card(a) for a in albums) or '<p class="home-col">No albums yet.</p>'
        body = f'<h1 class="vh">Albums</h1>\n<div class="entries">{cards}</div>'
        return self.layout(title="Albums", body=body, path="/albums/", wide=True, has_images=_has_images(body))

    def posts_index(self, posts):
        rows = "".join(self.post_row(p) for p in posts) or '<p class="home-col">No posts yet.</p>'
        body = f'<h1 class="vh">Posts</h1>\n<div class="entries">{rows}</div>'
        return self.layout(title="Posts", body=body, path="/posts/", wide=True)

    def pagination(self, page, pages):
        if pages <= 1:
            return ""
        newer = (f'<li><a href="{index_url(page - 1)}" rel="prev">← Newer posts</a></li>'
                 if page > 1 else "<li></li>")
        older = (f'<li><a href="{index_url(page + 1)}" rel="next">Older posts →</a></li>'
                 if page < pages else "<li></li>")
        return f'<nav class="pagination" aria-label="Pagination"><ul>{newer}{older}</ul></nav>'

    def giro(self, filename, version, size):
        body = f"""<h1>Giro</h1>
<p>Version {esc(version)} for Android · {size / 1_000_000:.1f} MB</p>
<p><a href="/giro/{esc(filename)}" download type="application/vnd.android.package-archive">Download {esc(filename)}</a></p>"""
        return self.layout(title="Giro", body=body, path="/giro/", noindex=True)

    def not_found(self):
        body = """<h1>Page not found</h1>
<p>Sorry, there’s nothing at this address. Try the <a href="/">homepage</a>.</p>"""
        return self.layout(title="Page not found", body=body, path="/404.html", noindex=True)


# Half-filled circle: reads as "contrast" whichever theme is active.
THEME_ICON = ('<svg aria-hidden="true" focusable="false" width="20" height="20" viewBox="0 0 20 20">'
              '<circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="2"/>'
              '<path d="M10 2a8 8 0 0 1 0 16z" fill="currentColor"/></svg>')


# Strip photos are about 1/N of the viewport wide, where N is how many the CSS shows.
STRIP_SIZES = "(min-width: 2000px) 25vw, (min-width: 641px) 33vw, 50vw"
GALLERY_SIZES = "(min-width: 1400px) 400px, (min-width: 700px) 33vw, 50vw"


def _img(info, alt, sizes, link=True, noupgrade=False, eager=False):
    el = image(info, alt, eager=eager, sizes=sizes, link=link)
    if noupgrade:
        for img in el.iter("img"):
            if img.get("data-full") is not None:
                img.set("data-noupgrade", "")
    return to_html_string(el)


def index_url(page):
    return "/" if page == 1 else f"/page/{page}/"


def time_tag(date):
    return f'<time datetime="{date.isoformat()}">{date.day} {date:%B %Y}</time>'


def _has_images(html):
    return "data-full=" in html


def _tidy(html):
    """Drop blank lines and indentation outside <pre>, which is whitespace-significant."""
    parts = re.split(r"(<pre[\s>].*?</pre>)", html, flags=re.S)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"\n\s*", "\n", parts[i])
    return "".join(parts)
