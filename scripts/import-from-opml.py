"""
Simple script which imports Creators from an OPML file.
"""

import re

import opml

import app

with open("/home/sethmlarson/sethmlarson.dev/archive/feeds.opml") as f:
    feeds_opml = opml.OpmlDocument.loads(f.read())


def slugify(text: str):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


for outline in feeds_opml.outlines:
    app.db.add(
        app.Creator(
            display_name=outline.text,
            slug=slugify(outline.text),
            web_url=outline.html_url,
            feed_url=outline.xml_url or None,
        )
    )

app.db.commit()
