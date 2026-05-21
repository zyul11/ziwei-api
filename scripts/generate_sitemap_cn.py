#!/usr/bin/env python3
"""Generate sitemap_cn.xml by scanning articles/ directory (Chinese articles)"""
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "articles"
SITEMAP_PATH = BASE_DIR / "sitemap_cn.xml"
SITE_URL = "https://ziweiapi.site"

today = date.today().isoformat()

urls = [
    f'  <url>\n    <loc>{SITE_URL}/</loc>\n    <priority>1.0</priority>\n    <lastmod>{today}</lastmod>\n  </url>',
    f'  <url>\n    <loc>{SITE_URL}/articles/</loc>\n    <priority>0.9</priority>\n    <lastmod>{today}</lastmod>\n  </url>',
    f'  <url>\n    <loc>{SITE_URL}/shop.html</loc>\n    <priority>0.8</priority>\n    <lastmod>{today}</lastmod>\n  </url>',
    f'  <url>\n    <loc>{SITE_URL}/api-docs.html</loc>\n    <priority>0.7</priority>\n    <lastmod>{today}</lastmod>\n  </url>',
    f'  <url>\n    <loc>{SITE_URL}/about.html</loc>\n    <priority>0.5</priority>\n    <lastmod>{today}</lastmod>\n  </url>',
]

# Add all z/ pages
z_dir = BASE_DIR / "z"
if z_dir.exists():
    files = sorted(z_dir.glob("*.html"), reverse=True)
    for f in files:
        urls.append(f'  <url>\n    <loc>{SITE_URL}/z/{f.name}</loc>\n    <priority>0.6</priority>\n    <lastmod>{today}</lastmod>\n  </url>')

# Add Chinese articles (exclude en/ directory and index.html)
if ARTICLES_DIR.exists():
    files = sorted(ARTICLES_DIR.glob("*.html"), reverse=True)
    for f in files:
        name = f.name
        if name == "index.html":
            continue
        urls.append(f'  <url>\n    <loc>{SITE_URL}/articles/{name}</loc>\n    <priority>0.6</priority>\n    <lastmod>{today}</lastmod>\n  </url>')

sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""

SITEMAP_PATH.write_text(sitemap, encoding="utf-8")
print(f"✅ 中文SiteMap已生成: {SITEMAP_PATH} ({len(urls)} URLs)")
