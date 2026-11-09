"""Load posts and pages from Markdown files with simple front matter."""

import datetime as dt
import json
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


PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FEATURED = 4  # the most the homepage strip ever shows (ultrawides)


@dataclass
class Photo:
    path: Path
    alt: str = ""
    caption: str = ""
    info: object = None  # ImageInfo, set at build time


@dataclass
class Album:
    source: Path  # the album's folder
    slug: str
    title: str
    date: dt.date
    photos: list
    body: str = ""
    summary: str = ""
    draft: bool = False
    featured: list = field(default_factory=list)
    html: str = ""
    kind: str = "album"

    @property
    def url(self):
        return f"/albums/{self.slug}/"

    def home_photos(self):
        """The photos shown in the homepage strip: `featured`, else evenly spaced."""
        if self.featured:
            return self.featured[:MAX_FEATURED]
        n = min(MAX_FEATURED, len(self.photos))
        if n == len(self.photos):
            return list(self.photos)
        return [self.photos[round(i * (len(self.photos) - 1) / (n - 1))] for i in range(n)]


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


def load_album(folder):
    """An album is a folder of photos plus an optional album.md or album.json.

    album.md:   front matter (title, date, summary, featured, draft) + a Markdown description.
    album.json: {"title", "date", "summary", "description", "featured", "draft",
                 "photos": {"01.jpg": {"alt": "...", "caption": "..."}}}
    The date can also come from a YYYY-MM-DD- folder prefix; photos are sorted by filename.
    """
    folder = Path(folder)
    meta, body = {}, ""
    if (folder / "album.json").is_file():
        meta = json.loads((folder / "album.json").read_text(encoding="utf-8"))
        body = str(meta.get("description", ""))
    elif (folder / "album.md").is_file():
        meta, body = parse_front_matter((folder / "album.md").read_text(encoding="utf-8"))
    stem, date = folder.name, None
    if m := DATE_PREFIX.match(stem):
        date, stem = dt.date.fromisoformat(m.group(1)), m.group(2)
    if "date" in meta:
        date = dt.date.fromisoformat(str(meta["date"])[:10])
    if date is None:
        raise ValueError(f"{folder}: albums need a date (album front matter or YYYY-MM-DD- folder name)")
    details = meta.get("photos") if isinstance(meta.get("photos"), dict) else {}
    files = sorted((f for f in folder.iterdir() if f.suffix.lower() in PHOTO_EXTS),
                   key=lambda f: f.name.lower())
    if not files:
        raise ValueError(f"{folder}: album has no photos")
    title = str(meta.get("title") or stem.replace("-", " ").title())
    photos = []
    for i, f in enumerate(files, 1):
        d = details.get(f.name) or {}
        photos.append(Photo(f, alt=str(d.get("alt") or f"Photo {i} from {title}"),
                            caption=str(d.get("caption", ""))))
    by_name = {p.path.name: p for p in photos}
    featured = []
    raw = meta.get("featured") or []
    for name in (raw if isinstance(raw, list) else str(raw).split(",")):
        name = name.strip()
        if name not in by_name:
            raise ValueError(f"{folder}: featured photo {name!r} is not in the album")
        featured.append(by_name[name])
    return Album(source=folder, slug=meta.get("slug") or slugify(stem), title=title, date=date,
                 photos=photos, body=body, summary=str(meta.get("summary", "")),
                 draft=bool(meta.get("draft", False)), featured=featured)


def load_albums(content_dir, drafts=False):
    base = Path(content_dir) / "albums"
    albums = [load_album(f) for f in sorted(base.iterdir()) if f.is_dir()] if base.is_dir() else []
    if not drafts:
        albums = [a for a in albums if not a.draft]
    albums.sort(key=lambda a: (a.date, a.slug), reverse=True)
    return albums


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
