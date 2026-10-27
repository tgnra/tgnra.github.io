"""Generate stress-test posts and images.

    python tools/stress.py           # write ~120 posts + images
    python tools/stress.py --clean   # remove them again

Everything generated is named stress-* so it can be cleaned without touching
real content. Output is deterministic (seeded).
"""

import argparse
import datetime as dt
import random
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "content" / "posts"
PAGES = ROOT / "content" / "pages"
IMAGES = ROOT / "content" / "images" / "stress"
N_POSTS = 120

WORDS = """the a of to and in is it that for on with as was at by an be this from
or which you one had not but have what were all when we there can been has more
if will their out so up said its about into than them only other new some could
time these two may then do first any my now such like our over man me even most
made after also did many before must through back years where much your way well
down should because each just those people how too little state good very make
world still own see men work long get here between both life being under never
day same another know while last might us great old year off come since against
go came right used take three light image pixel bandwidth dither palette network
latency render layout gradient texture""".split()


def sentence(r, lo=6, hi=18):
    words = [r.choice(WORDS) for _ in range(r.randint(lo, hi))]
    if r.random() < 0.15:
        words[r.randrange(len(words))] = f"**{r.choice(WORDS)}**"
    if r.random() < 0.15:
        words[r.randrange(len(words))] = f"*{r.choice(WORDS)}*"
    if r.random() < 0.1:
        words[r.randrange(len(words))] = f"`{r.choice(WORDS)}()`"
    if r.random() < 0.1:
        words[r.randrange(len(words))] = f"[{r.choice(WORDS)}](/about/)"
    s = " ".join(words)
    return s[0].upper() + s[1:] + r.choice(".....?!")


def paragraph(r, n=None):
    return " ".join(sentence(r) for _ in range(n or r.randint(2, 7)))


# -- images -------------------------------------------------------------------

def fractal(size, seed, octaves=6):
    """Photo-like texture: summed, upscaled noise at several scales plus grain."""
    w, h = size
    random.seed(seed)
    acc = Image.new("L", size, 128)
    for i in range(octaves):
        scale = 2 ** (octaves - i + 1)
        small = Image.effect_noise((max(2, w // scale), max(2, h // scale)), 90)
        layer = small.resize(size, Image.Resampling.BICUBIC)
        acc = Image.blend(acc, layer, 0.5 if i == 0 else 0.35 / i)
    return ImageOps.autocontrast(acc)


def photo(size, seed, palette):
    gray = fractal(size, seed)
    img = ImageOps.colorize(gray, *palette)
    grain = Image.effect_noise(size, 30).convert("RGB")
    return ImageChops.overlay(img, Image.blend(Image.new("RGB", size, (128,) * 3), grain, 0.15))


PALETTES = [
    ("#0b1d2a", "#e8d9b0", "#4f7c6b"),  # forest
    ("#1a0f2e", "#ffd6a0", "#c0587e"),  # dusk
    ("#06121f", "#d8f0ff", "#3a7bbf"),  # sea
    ("#2a1a0a", "#fff2d6", "#b07a3a"),  # desert
    ("#111111", "#f4f4f4", "#777777"),  # mono
]


def make_images():
    IMAGES.mkdir(parents=True, exist_ok=True)
    made = {}

    def save(name, img, **kw):
        img.save(IMAGES / name, **kw)
        made[name.rsplit(".", 1)[0]] = name

    # Photo-like JPEGs of various shapes.
    shapes = {
        "huge": (4000, 3000), "landscape": (2400, 1600), "portrait": (1500, 2400),
        "square": (800, 800), "panorama": (6000, 1000), "tall": (600, 3000),
        "small": (450, 300), "tiny": (120, 80),
    }
    for i, (name, size) in enumerate(shapes.items()):
        save(f"stress-{name}.jpg", photo(size, i, PALETTES[i % len(PALETTES)]), quality=90)
    for i in range(12):
        size = (1600 + 200 * (i % 4), 1000 + 150 * (i % 3))
        save(f"stress-gallery-{i:02d}.jpg", photo(size, 100 + i, PALETTES[i % len(PALETTES)]),
             quality=88)

    # Odd formats and modes.
    art = Image.new("RGBA", (1000, 600), (0, 0, 0, 0))
    d = ImageDraw.Draw(art)
    for i in range(8):
        d.ellipse((60 + i * 100, 100 + (i % 2) * 120, 260 + i * 100, 400 + (i % 2) * 120),
                  fill=(40 * i, 200 - 20 * i, 160, 160))
    save("stress-transparent.png", art)
    save("stress-grayscale.jpg", fractal((1800, 1200), 7), quality=88)
    save("stress-palette.gif", photo((900, 600), 8, PALETTES[1]).quantize(64))
    save("stress-cmyk.jpg", photo((1400, 900), 9, PALETTES[3]).convert("CMYK"), quality=88)
    deep = fractal((1200, 800), 10).convert("I").point(lambda v: v * 257)
    save("stress-16bit.png", deep.convert("I;16"))

    # Stored sideways with an EXIF orientation tag: should display upright.
    upright = photo((1200, 1800), 11, PALETTES[2])
    d = ImageDraw.Draw(upright)
    d.text((40, 40), "THIS WAY UP", fill="white", font_size=96)
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 CW to display
    upright.rotate(90, expand=True).save(IMAGES / "stress-exif-rotated.jpg", quality=88,
                                         exif=exif)
    made["stress-exif-rotated"] = "stress-exif-rotated.jpg"
    return made


# -- posts --------------------------------------------------------------------

def img(name, alt, title=None):
    t = f' "{title}"' if title else ""
    return f"![{alt}](../images/stress/{name}{t})"


def body_longform(r, ims):
    out = [paragraph(r)]
    for level in (1, 2, 2, 3, 4, 2, 3):
        out.append("#" * level + " " + sentence(r, 2, 6).rstrip(".?!"))
        out += [paragraph(r) for _ in range(r.randint(1, 3))]
    out.append("> " + paragraph(r, 2) + "\n>\n> — " + r.choice(WORDS).title())
    out.append("\n".join(f"{i + 1}. {sentence(r)}" + "".join(
        f"\n    - {sentence(r, 3, 8)}" for _ in range(r.randint(0, 2))) for i in range(5)))
    out.append(f"A claim that needs a source.[^1] And another.[^2]\n\n"
               f"[^1]: {sentence(r)}\n[^2]: {sentence(r)}")
    return out


def body_gallery(r, ims):
    out = [paragraph(r, 2)]
    for i in range(12):
        out.append(img(ims[f"stress-gallery-{i:02d}"], f"Generated texture number {i + 1}",
                       f"Gallery image {i + 1} of 12" if i % 3 == 0 else None))
        if i % 4 == 3:
            out.append(paragraph(r, 2))
    return out


def body_shapes(r, ims):
    out = [paragraph(r, 2)]
    for name in ("huge", "panorama", "portrait", "tall", "square", "small", "tiny"):
        out.append(f"## {name.title()}")
        out.append(img(ims[f"stress-{name}"], f"A {name} generated texture", f"{name} image"))
    return out


def body_formats(r, ims):
    out = ["Each image below uses an unusual mode or format."]
    for name, alt in [
        ("transparent", "Translucent overlapping circles on a transparent background"),
        ("grayscale", "Grayscale cloud texture"),
        ("palette", "64-colour palette GIF texture"),
        ("cmyk", "CMYK JPEG texture in desert tones"),
        ("16bit", "16-bit grayscale PNG texture"),
        ("exif-rotated", "Portrait texture labelled THIS WAY UP, which should be upright"),
    ]:
        out.append(f"## {name}")
        out.append(img(ims[f"stress-{name}"], alt))
    out.append('Decorative image with empty alt:\n\n' + img(ims["stress-small"], '""'))
    return out


def body_inline(r, ims):
    return [
        f"Text with an inline image {img(ims['stress-tiny'], 'tiny texture')} in the middle "
        f"of a sentence, then {img(ims['stress-small'], 'small texture')} another. "
        + paragraph(r, 3),
        f"[{img(ims['stress-square'], 'Square texture linked to the about page')}](/about/)",
        paragraph(r),
        "External image (left untouched, lazy):\n\n"
        "![Placeholder from an external host](https://picsum.photos/600/300)",
    ]


def body_overflow(r, ims):
    cols = 12
    head = "| " + " | ".join(f"Column {c}" for c in range(cols)) + " |"
    sep = "|" + "---|" * cols
    rows = ["| " + " | ".join(r.choice(WORDS) * r.randint(1, 3) for _ in range(cols)) + " |"
            for _ in range(8)]
    long_line = "x = " + " + ".join(f"value_{i}" for i in range(60))
    return [
        paragraph(r, 2),
        "\n".join([head, sep, *rows]),
        f"```python\n{long_line}\nprint(x)\n```",
        "Unbreakable: Pneumonoultramicroscopicsilicovolcanoconiosis" * 3,
        "URL: https://example.com/" + "very-long-path-segment/" * 12,
        "    indented code block\n    with   spacing   preserved",
    ]


def body_unicode(r, ims):
    return [
        "Ünïcödé: ✓ → ½ ∞ “curly” ‘quotes’ — em dash … ellipsis, emoji 🌄🖼️, CJK 日本語のテキスト。",
        "Right-to-left: <span dir=\"rtl\" lang=\"ar\">مرحبا بالعالم</span>",
        "Escaping: 5 < 6 & 7 > 3 & AT&T, and `<script>alert('x')</script>` in code.",
        paragraph(r),
    ]


def body_headings_only(r, ims):
    # Starts at ### so headings get shifted; skips a level to trigger a warning.
    return ["### Starts deep", paragraph(r, 2), "##### Skips a level", paragraph(r, 2)]


def body_empty(r, ims):
    return []


KINDS = [body_longform, body_gallery, body_shapes, body_formats, body_inline,
         body_overflow, body_unicode, body_headings_only, body_empty]
TITLES = {
    body_unicode: "Ünïcödé & <escaping> \"test\" 🌄",
    body_empty: "A post with no body",
}


def make_posts(ims):
    POSTS.mkdir(parents=True, exist_ok=True)
    r = random.Random(42)
    day = dt.date(2026, 10, 26)
    for i in range(N_POSTS):
        kind = KINDS[i % len(KINDS)]
        title = TITLES.get(kind) or sentence(r, 2, 9).rstrip(".?!")
        if i % 17 == 0:
            title = " ".join([sentence(r, 12, 14).rstrip(".?!")] * 2)  # very long title
        meta = [f'title: "{title}"' if '"' not in title else f"title: '{title}'"]
        if i % 5 == 0:
            hero = ["stress-landscape", "stress-huge", "stress-panorama", "stress-portrait"][i // 5 % 4]
            meta += [f"hero: ../images/stress/{ims[hero]}", f"hero_alt: Hero texture for post {i}"]
        if i % 7 == 3:
            meta.append(f"summary: {sentence(r)}")
        if i % 23 == 11:
            meta.append("draft: true")
        body = "\n\n".join(kind(r, ims)) + "\n"
        slug = f"stress-{i:03d}-{kind.__name__.removeprefix('body_')}"
        text = "---\n" + "\n".join(meta) + "\n---\n\n" + body
        (POSTS / f"{day.isoformat()}-{slug}.md").write_text(text, encoding="utf-8")
        if i % 4 != 0:  # several posts share some dates
            day -= dt.timedelta(days=r.randint(1, 12))

    PAGES.mkdir(parents=True, exist_ok=True)
    (PAGES / "stress-long-page.md").write_text(
        "---\ntitle: Stress page\nnav: 9\n---\n\n" + "\n\n".join(body_longform(r, ims)) + "\n",
        encoding="utf-8")


def clean():
    for p in list(POSTS.glob("*-stress-*.md")) + list(PAGES.glob("stress-*.md")):
        p.unlink()
    shutil.rmtree(IMAGES, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true", help="remove generated content")
    args = ap.parse_args()
    clean()
    if args.clean:
        print("removed stress content")
        return 0
    ims = make_images()
    make_posts(ims)
    print(f"wrote {N_POSTS} posts, 1 page and {len(ims)} images")
    return 0


if __name__ == "__main__":
    sys.exit(main())
