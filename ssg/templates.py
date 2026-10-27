"""HTML templates as plain functions. All interpolated text goes through esc()."""

import re
from html import escape
from pathlib import Path

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

    def layout(self, *, title, body, path, description="", has_images=False, noindex=False):
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
<link rel="icon" href="{esc(site.get('favicon') or 'data:,')}">
{robots}
<script>{self.head_js}</script>
<style>{self.css}</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
<div class="wrap">
<a class="site-title" href="/">{esc(site['title'])}</a>
{self.nav(path)}
</div>
</header>
<main id="main" class="wrap" tabindex="-1">
{body}
</main>
<footer class="site-footer">
<div class="wrap">
<p>© {esc(site['year'])} {esc(site['author'])} · <a href="/feed.xml">RSS feed</a></p>
</div>
</footer>
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

    def index(self, posts, page, pages):
        heading = "Posts" if page == 1 else f"Posts, page {page} of {pages}"
        items = "\n".join(f"""<li><article>
<h2><a href="{esc(p.url)}">{esc(p.title)}</a></h2>
<p class="meta">{time_tag(p.date)}</p>
<p>{esc(p.summary)}</p>
</article></li>""" for p in posts)
        body = f"""<h1>{esc(heading)}</h1>
<ul class="post-list" role="list">
{items}
</ul>
{self.pagination(page, pages)}"""
        path = index_url(page)
        title = self.site["title"] if page == 1 else f"Posts, page {page}"
        return self.layout(title=title, body=body, path=path)

    def pagination(self, page, pages):
        if pages <= 1:
            return ""
        newer = (f'<li><a href="{index_url(page - 1)}" rel="prev">← Newer posts</a></li>'
                 if page > 1 else "<li></li>")
        older = (f'<li><a href="{index_url(page + 1)}" rel="next">Older posts →</a></li>'
                 if page < pages else "<li></li>")
        return f'<nav class="pagination" aria-label="Pagination"><ul>{newer}{older}</ul></nav>'

    def not_found(self):
        body = """<h1>Page not found</h1>
<p>Sorry, there’s nothing at this address. Try the <a href="/">list of posts</a>.</p>"""
        return self.layout(title="Page not found", body=body, path="/404.html", noindex=True)


# Half-filled circle: reads as "contrast" whichever theme is active.
THEME_ICON = ('<svg aria-hidden="true" focusable="false" width="20" height="20" viewBox="0 0 20 20">'
              '<circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="2"/>'
              '<path d="M10 2a8 8 0 0 1 0 16z" fill="currentColor"/></svg>')


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
