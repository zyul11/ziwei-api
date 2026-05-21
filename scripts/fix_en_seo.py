#!/usr/bin/env python3
"""批量修复旧英文文章的SEO标签"""
import re
from pathlib import Path
from datetime import date

BASE_DIR = Path("/home/ubuntu/ziwei-api")
WEBSITE = "https://ziweiapi.site"

def fix_en_article(fp: Path):
    text = fp.read_text(encoding="utf-8")
    original = text

    title_m = re.search(r"<title>(.*?)</title>", text)
    desc_m = re.search(r'<meta name="description" content="(.*?)"', text)
    canonical_m = re.search(r'<link rel="canonical" href="(.*?)"', text)
    canonical_url = canonical_m.group(1) if canonical_m else ""
    title = title_m.group(1) if title_m else ""
    desc = desc_m.group(1) if desc_m else ""

    og_title_esc = title[:80].replace('"', "'")
    desc_esc = desc[:150].replace('"', "'")
    today_iso = date.today().isoformat()

    # Add OG + Twitter
    og_block = f"""<meta property="og:type" content="article">
<meta property="og:title" content="{og_title_esc}">
<meta property="og:description" content="{desc_esc}">
<meta property="og:url" content="{canonical_url}">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{og_title_esc}">"""

    if 'og:title' not in text:
        desc_end = re.search(r'<meta name="description" content=".*?">', text)
        if desc_end:
            pos = desc_end.end()
            text = text[:pos] + "\n" + og_block + text[pos:]

    # Add description CTA
    desc_old = re.search(r'<meta name="description" content=".*?"', text)
    if desc_old and "Free chart reading" not in desc_old.group():
        new_desc = desc_old.group().rstrip('"') + '. Free chart reading with complete interpretation."'
        text = text.replace(desc_old.group(), new_desc)

    # Add Article schema
    if '"@type": "Article"' not in text:
        article_schema = f"""<script type="application/ld+json">{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{og_title_esc}",
  "description": "{desc_esc}",
  "datePublished": "{today_iso}",
  "author": {{"@type": "Person", "name": "Ziwei Master"}},
  "publisher": {{"@type": "Organization", "name": "Ziwei API"}},
  "inLanguage": "en"
}}</script>"""
        text = text.replace("</head>", article_schema + "\n</head>")

    # Add hreflang x-default
    if 'hreflang="x-default"' not in text:
        canonical_tag = re.search(r'<link rel="canonical" href=".*?"', text)
        if canonical_tag:
            pos = canonical_tag.end()
            text = text[:pos] + "\n" + f'<link rel="alternate" hreflang="x-default" href="{canonical_url}">' + text[pos:]

    if text != original:
        fp.write_text(text, encoding="utf-8")
        return True
    return False

fixed = 0
for fp in BASE_DIR.glob("articles/en/*.html"):
    t = fp.read_text(encoding="utf-8")
    if 'og:title' not in t or '"@type": "Article"' not in t:
        if fix_en_article(fp):
            fixed += 1
            print(f"  ✅ {fp.name}")

print(f"\n总计修复: {fixed} 个文件")
