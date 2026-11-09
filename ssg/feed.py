"""RSS 2.0 feed and sitemap."""

import datetime as dt
import xml.etree.ElementTree as etree
from email.utils import format_datetime

ATOM = "http://www.w3.org/2005/Atom"
CONTENT = "http://purl.org/rss/1.0/modules/content/"


def _rfc822(date):
    return format_datetime(dt.datetime(date.year, date.month, date.day, tzinfo=dt.timezone.utc))


def rss(site, posts):
    """Posts only. Albums have their own feed: see photos_rss()."""
    return _rss(site, posts, site["title"], "/feed.xml", lambda p: p.feed_html)


def photos_rss(site, albums):
    """Albums only; each item's content is the album's description and all its photos."""
    return _rss(site, albums, f"{site['title']} – photos", "/photos.xml", lambda a: a.feed_html)


def _rss(site, docs, title, path, content_of):
    etree.register_namespace("atom", ATOM)
    etree.register_namespace("content", CONTENT)
    base = site["base_url"]
    root = etree.Element("rss", {"version": "2.0"})
    channel = etree.SubElement(root, "channel")
    for tag, text in (("title", title), ("link", base + "/"),
                      ("description", site["description"]), ("language", site["language"])):
        etree.SubElement(channel, tag).text = text
    etree.SubElement(channel, f"{{{ATOM}}}link", {
        "href": base + path, "rel": "self", "type": "application/rss+xml"})
    if docs:
        etree.SubElement(channel, "lastBuildDate").text = _rfc822(docs[0].date)
    for doc in docs[: site["feed_items"]]:
        item = etree.SubElement(channel, "item")
        url = base + doc.url
        etree.SubElement(item, "title").text = doc.title
        etree.SubElement(item, "link").text = url
        etree.SubElement(item, "guid", {"isPermaLink": "true"}).text = url
        etree.SubElement(item, "pubDate").text = _rfc822(doc.date)
        etree.SubElement(item, "description").text = doc.summary
        etree.SubElement(item, f"{{{CONTENT}}}encoded").text = content_of(doc)
    return '<?xml version="1.0" encoding="utf-8"?>\n' + etree.tostring(root, encoding="unicode")


def sitemap(site, urls):
    ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
    root = etree.Element("urlset", {"xmlns": ns})
    for path, date in urls:
        u = etree.SubElement(root, "url")
        etree.SubElement(u, "loc").text = site["base_url"] + path
        if date:
            etree.SubElement(u, "lastmod").text = date.isoformat()
    return '<?xml version="1.0" encoding="utf-8"?>\n' + etree.tostring(root, encoding="unicode")
