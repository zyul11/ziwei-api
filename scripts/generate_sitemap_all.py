#!/usr/bin/env python3
"""Generate all sitemaps: sitemap.xml (combined), sitemap_en.xml, sitemap_cn.xml"""
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).resolve().parent.parent
SITE_URL = "https://ziweiapi.site"
today = date.today().isoformat()

# ── Combined sitemap.xml ──────────────────────────────────────────────
def generate_combined():
    urls = []

    # Static pages
    static = [
        ("/", 1.0),
        ("/shop.html", 0.8),
        ("/tools/", 0.8),
        ("/articles/", 0.7),
        ("/api-docs.html", 0.7),
        ("/about.html", 0.5),
        ("/privacy.html", 0.4),
    ]
    for path, pri in static:
        urls.append(make_url(path, pri))

    # Tool pages (en + all locales)
    tools_dir = BASE_DIR / "tools"
    if tools_dir.exists():
        for f in sorted(tools_dir.glob("**/*.html"), reverse=True):
            rel = f.relative_to(BASE_DIR)
            priority = 0.7 if f.name == "index.html" else 0.6
            urls.append(make_url(f"/{rel}", priority))

    # Tool article guides
    tools_articles = BASE_DIR / "articles" / "tools"
    if tools_articles.exists():
        for f in sorted(tools_articles.glob("*.html"), reverse=True):
            rel = f.relative_to(BASE_DIR)
            urls.append(make_url(f"/{rel}", 0.6))

    # Chinese articles (root articles/*.html)
    articles_dir = BASE_DIR / "articles"
    if articles_dir.exists():
        for f in sorted(articles_dir.glob("*.html"), reverse=True):
            if f.name == "index.html":
                continue
            # Skip tools subdir (already handled above)
            if f.parent.name == "tools":
                continue
            rel = f.relative_to(BASE_DIR)
            urls.append(make_url(f"/{rel}", 0.6))

    # English articles in articles/en/
    en_dir = BASE_DIR / "articles" / "en"
    if en_dir.exists():
        for f in sorted(en_dir.glob("*.html"), reverse=True):
            if f.name == "index.html":
                continue
            rel = f.relative_to(BASE_DIR)
            urls.append(make_url(f"/{rel}", 0.6))

    # z/ pages (Ziwei astrology)
    z_dir = BASE_DIR / "z"
    if z_dir.exists():
        for f in sorted(z_dir.glob("*.html"), reverse=True):
            rel = f.relative_to(BASE_DIR)
            urls.append(make_url(f"/{rel}", 0.6))

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>
"""
    (BASE_DIR / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    print(f"✅ sitemap.xml generated with {len(urls)} URLs")
    return len(urls)


def make_url(path, priority):
    return f"""  <url>
    <loc>{SITE_URL}{path}</loc>
    <priority>{priority}</priority>
    <lastmod>{today}</lastmod>
  </url>"""


# ── English sitemap (sitemap_en.xml) ──────────────────────────────────
def generate_en():
    urls = [
        make_url("/api-docs.html?lang=en", 0.9),
        make_url("/articles/en/", 0.7),
    ]
    en_dir = BASE_DIR / "articles" / "en"
    if en_dir.exists():
        for f in sorted(en_dir.glob("*.html"), reverse=True):
            if f.name == "index.html":
                continue
            urls.append(make_url(f"/articles/en/{f.name}", 0.6))

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>
"""
    (BASE_DIR / "sitemap_en.xml").write_text(sitemap, encoding="utf-8")
    print(f"✅ sitemap_en.xml generated with {len(urls)} URLs")


# ── Chinese sitemap (sitemap_cn.xml) ──────────────────────────────────
def generate_cn():
    urls = [
        make_url("/", 1.0),
        make_url("/articles/", 0.9),
        make_url("/shop.html", 0.8),
        make_url("/api-docs.html", 0.7),
        make_url("/about.html", 0.5),
    ]
    z_dir = BASE_DIR / "z"
    if z_dir.exists():
        for f in sorted(z_dir.glob("*.html"), reverse=True):
            urls.append(make_url(f"/z/{f.name}", 0.6))

    articles_dir = BASE_DIR / "articles"
    if articles_dir.exists():
        for f in sorted(articles_dir.glob("*.html"), reverse=True):
            name = f.name
            if name == "index.html":
                continue
            urls.append(make_url(f"/articles/{name}", 0.6))

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""
    (BASE_DIR / "sitemap_cn.xml").write_text(sitemap, encoding="utf-8")
    print(f"✅ sitemap_cn.xml generated with {len(urls)} URLs")


if __name__ == "__main__":
    total = generate_combined()
    generate_en()
    generate_cn()
    print(f"🎯 All sitemaps generated. Total URLs in combined: {total}")
