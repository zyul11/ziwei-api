#!/usr/bin/env python3
"""
批量修复所有文章页的SEO问题：添加OG标签、Twitter Card、Article schema
覆盖 articles/ 下所有 .html 文件（不含 index / template / tools）
"""
import re
from pathlib import Path
from datetime import date

BASE_DIR = Path("/home/ubuntu/ziwei-api")
WEBSITE = "https://ziweiapi.site"

def fix_article(fp: Path):
    text = fp.read_text(encoding="utf-8")
    original = text

    # Skip if already has OG + JSON-LD
    has_og = 'og:title' in text
    has_schema = '"@type": "Article"' in text
    if has_og and has_schema:
        print(f"  ➖ 已有全套SEO，跳过")
        return False

    name = fp.name

    # Detect language
    lang = "en"
    locale = "en_US"
    if name.endswith("-en.html") or fp.parent.name == "en":
        lang = "en"
        locale = "en_US"
    elif name.endswith("-zhs.html"):
        lang = "zh-Hans"
        locale = "zh_CN"
    else:
        lang = "zh-Hant"
        locale = "zh_TW"

    # Extract info from existing tags
    title_m = re.search(r"<title>(.*?)</title>", text)
    desc_m = re.search(r'<meta name="description" content="(.*?)"', text)
    canonical_m = re.search(r'<link rel="canonical" href="(.*?)"', text)
    canonical_url = canonical_m.group(1) if canonical_m else f"{WEBSITE}/articles/{name}"
    title = title_m.group(1) if title_m else ""
    desc = desc_m.group(1) if desc_m else title[:150]

    og_title_esc = title[:80].replace('"', "'")
    desc_esc = desc[:150].replace('"', "'")

    # Build OG + Twitter block
    og_block = f"""<meta property="og:type" content="article">
<meta property="og:title" content="{og_title_esc}">
<meta property="og:description" content="{desc_esc}">
<meta property="og:url" content="{canonical_url}">
<meta property="og:locale" content="{locale}">
<meta property="og:image" content="https://ziweiapi.site/og-image.jpg">
<meta property="og:image:alt" content="紫微斗數命盤推演">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{og_title_esc}">"""

    # Try to extract date from filename
    date_m = re.match(r"(\d{4})(\d{2})(\d{2})", name)
    pub_date = f"{date_m.group(1)}-{date_m.group(2)}-{date_m.group(3)}" if date_m else date.today().isoformat()

    article_schema = f"""<script type="application/ld+json">{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{og_title_esc}",
  "description": "{desc_esc}",
  "datePublished": "{pub_date}",
  "author": {{"@type": "Person", "name": "Ziwei Master"}},
  "publisher": {{"@type": "Organization", "name": "Ziwei API"}},
  "inLanguage": "{lang}"
}}</script>"""

    if not has_og:
        # Insert OG block after description meta or before </head>
        desc_end = re.search(r'<meta name="description" content=".*?">', text)
        if desc_end:
            pos = desc_end.end()
            text = text[:pos] + "\n" + og_block + text[pos:]
            print(f"    + OG tags after description")
        else:
            text = text.replace("</head>", og_block + "\n</head>")
            print(f"    + OG tags before </head>")

    if not has_schema:
        text = text.replace("</head>", article_schema + "\n</head>")
        print(f"    + Article schema")

    if text != original:
        fp.write_text(text, encoding="utf-8")
        return True
    return False

# Collect all article HTML files
files = []
for fp in sorted(BASE_DIR.glob("articles/*.html")):
    fn = fp.name
    if fn in ("index.html", "template.html"):
        continue
    files.append(fp)

for fp in sorted(BASE_DIR.glob("articles/**/*.html")):
    fn = fp.name
    if fn in ("index.html", "template.html"):
        continue
    if fp not in files:
        files.append(fp)

fixed = 0
skipped = 0
for fp in files:
    print(f"📄 {fp.relative_to(BASE_DIR)}")
    try:
        if fix_article(fp):
            fixed += 1
            print(f"  ✅ 已修复")
        else:
            skipped += 1
    except Exception as e:
        print(f"  ❌ 错误: {e}")

print(f"\n✅ 总计: {fixed} 个文件已修复, {skipped} 个无需修改")
