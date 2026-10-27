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
| full | fast or unknown (Safari, Firefox) | 480/800/1280px AVIF, then WebP; 800px JPEG only for clients with neither |
| original | lightbox | AVIF, then WebP (JPEG fallback) at source size up to 2560px |

- `width` and `height` are always set, so nothing shifts as images load.
- `assets/img.js` picks the tier from `navigator.connection` and loads images as they approach the viewport.
- Low tiers offer a "Load full-quality image" button on each image.
- Browsers pick the first format they support from `<picture>`: AVIF (smallest), then WebP. JPEG is only for clients with neither, the no-JS lightbox link, and the RSS feed.
- Without JS, a `<noscript>` `<picture>` loads the full tier lazily.
- Variants are cached in `.cache/images/` by content hash. Bump `VERSION` in `ssg/images.py` after changing encoder settings.
- Transparency is composited onto white.

The dither tier is about a predictable, small and distinctive look. It isn't always the smallest file: on smooth images, lossy WebP or AVIF can be smaller still.

## Deploying to GitHub Pages

`.github/workflows/pages.yml` runs on every push to `main`, or when started by hand. It runs the tests, builds the site with the Pages URL as `--base-url`, and deploys `dist/`. Generated image variants are cached between runs.

One-time setup: in the repository, go to **Settings → Pages → Source** and choose **GitHub Actions**.

The site must be served from the domain root, because all its URLs are root-relative (`/img/…`, `/posts/…`). That works for:
- a user or organisation site (a repository named `<user>.github.io`)
- a custom domain: put a `CNAME` file in `content/static/`

A project site at `<user>.github.io/<repo>/` doesn't work. The workflow fails with an explanation rather than deploying a broken site.

GitHub Pages ignores `dist/_headers`. That's harmless: it's only used by Netlify and Cloudflare Pages.

Use `--base-url` to build for another host: `python -m ssg build --base-url https://example.org`. It overrides `base_url` in `site.toml`.

## giro/ downloads

To publish an APK, put `giro<N>.apk` files in `content/downloads/`. `N` must be a plain integer, such as `giro12.apk`.

The build copies the highest-numbered file (compared as numbers, so 10 beats 9) to `/giro/giro<N>.apk`. It also writes `/giro/version.txt`, which contains just `N` with no newline. Other files in `content/downloads/` are ignored. If no file matches, nothing is published.

`giro/` is kept out of search engines:
- `robots.txt` disallows it
- it never appears in the sitemap
- there's no index page and nothing links to it
- `_headers` adds `X-Robots-Tag: noindex`, but only on Netlify and Cloudflare; GitHub Pages ignores it

GitHub rejects files over 100 MB in a git repository. For a larger APK, use Git LFS (Pages artifacts include LFS files only if the checkout step sets `lfs: true`), or host the APK on GitHub Releases instead.
