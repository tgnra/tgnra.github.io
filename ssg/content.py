"""Load posts and pages from Markdown files with simple front matter."""

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")


@dataclass
class Doc:
    kind: str  # "post" or "page"
    source: Path
    slug: str
    title: str
    body: str
    date: dt.date | None = None
    summary: str = ""
    draft: bool = False
    hero: str = ""
    hero_alt: str = ""
    nav: int | None = None
    meta: dict = field(default_factory=dict)
    html: str = ""
    feed_html: str = ""

    @property
    def url(self):
        return f"/posts/{self.slug}/" if self.kind == "post" else f"/{self.slug}/"


def parse_front_matter(text):
    """Split `---` delimited `key: value` front matter from the body.

    Values are unquoted; true/false become bools and plain integers become ints.
    """
    text = text.lstrip("﻿")
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines(keepends=True)
    meta = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return meta, "".join(lines[i + 1:])
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"bad front matter line: {line.strip()!r}")
        meta[key.strip().lower()] = _coerce(value.strip())
    raise ValueError("front matter is not closed with ---")


def _coerce(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_-]+", "-", text) or "untitled"


def load_doc(path, kind):
    meta, body = parse_front_matter(Path(path).read_text(encoding="utf-8"))
    stem = Path(path).stem
    date = None
    if m := DATE_PREFIX.match(stem):
        date = dt.date.fromisoformat(m.group(1))
        stem = m.group(2)
    if "date" in meta:
        date = dt.date.fromisoformat(str(meta["date"])[:10])
    if kind == "post" and date is None:
        raise ValueError(f"{path}: posts need a date (front matter or YYYY-MM-DD- filename)")
    return Doc(
        kind=kind,
        source=Path(path),
        slug=meta.get("slug") or slugify(stem),
        title=str(meta.get("title") or stem.replace("-", " ").title()),
        body=body,
        date=date,
        summary=str(meta.get("summary", "")),
        draft=bool(meta.get("draft", False)),
        hero=str(meta.get("hero", "")),
        hero_alt=str(meta.get("hero_alt", "")),
        nav=meta.get("nav") if isinstance(meta.get("nav"), int) else None,
        meta=meta,
    )


def load_all(content_dir, drafts=False):
    """Return (posts newest first, pages)."""
    content_dir = Path(content_dir)
    posts = [load_doc(p, "post") for p in sorted((content_dir / "posts").glob("*.md"))]
    pages = [load_doc(p, "page") for p in sorted((content_dir / "pages").glob("*.md"))]
    if not drafts:
        posts = [p for p in posts if not p.draft]
        pages = [p for p in pages if not p.draft]
    posts.sort(key=lambda p: (p.date, p.slug), reverse=True)
    _check_unique(posts + pages)
    return posts, pages


def _check_unique(docs):
    seen = {}
    for doc in docs:
        if doc.url in seen:
            raise ValueError(f"{doc.source} and {seen[doc.url]} both map to {doc.url}")
        seen[doc.url] = doc.source
