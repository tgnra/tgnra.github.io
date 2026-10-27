# blog

A small static site generator. Two dependencies: Pillow and Markdown.

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # .venv/bin/python on macOS/Linux
.venv/Scripts/python -m ssg serve        # http://localhost:8000, rebuilds on change
.venv/Scripts/python -m ssg build        # -> dist/
.venv/Scripts/python -m ssg new "Title"  # new draft post
.venv/Scripts/python -m unittest
```

Deploy `dist/` to any static host. `dist/_headers` marks `/img/*` as immutable on Netlify and Cloudflare Pages.

## Writing

- **Posts:** `content/posts/YYYY-MM-DD-slug.md`.
- **Pages:** `content/pages/slug.md`.
- **Static files:** anything in `content/static/` is copied to the site root as-is (favicon, CNAME, …).

Front matter (all optional except where noted):

```
---
title: Post title
date: 2026-10-27        # overrides the filename date
summary: Shown on the index and in the feed (defaults to the first paragraph)
hero: ../images/x.jpg   # large image above the post
hero_alt: Description   # required with hero; "" if decorative
draft: true             # skipped unless --drafts
nav: 1                  # pages only: show in the nav, in this order
---
```

## Images

- `![Alt text](../images/photo.jpg "Optional caption")`. The path is relative to the Markdown file, or starts with `/` for a path relative to `content/`.
- A missing alt text fails the build. Write `![""](x.jpg)` for a decorative image.

Each image becomes:

| Tier | When | Output |
|---|---|---|
| placeholder | always, inline in the HTML | 24px, 8 colours, dithered PNG (~300 B) |
| dither | Save-Data or 2G | 320/480px, 8-colour ordered-dither lossless WebP, shown as crisp pixels |
| lite | 3G | 400/800px WebP q45 |
| full | fast or unknown (Safari, Firefox) | 480/800/1280px AVIF and WebP, 800px JPEG fallback |
| original | lightbox | source size up to 2560px |

- `width` and `height` are always set, so nothing shifts as images load.
- `assets/img.js` picks the tier from `navigator.connection` and loads images as they approach the viewport.
- Low tiers offer a "Load full-quality image" button on each image.
- Without JS, a `<noscript>` `<picture>` loads the full tier lazily.
- Variants are cached in `.cache/images/` by content hash. Bump `VERSION` in `ssg/images.py` after changing encoder settings.
- Transparency is composited onto white.

The dither tier is about a predictable, small and distinctive look. It isn't always the smallest file: on smooth images, lossy WebP or AVIF can be smaller still.
