#!/usr/bin/env python3
"""
批量修复现有热点文章的SEO问题：添加OG标签、Twitter Card、Article schema、description CTA
应用于 articles/ 目录下所有 20260516/17/18 的热点文章
"""
import re
from pathlib import Path
from datetime import date

BASE_DIR = Path("/home/ubuntu/ziwei-api")
WEBSITE = "https://ziweiapi.site"

def fix_article(fp: Path):
    text = fp.read_text(encoding="utf-8")
    original = text

    name = fp.name
    lang = "en" if name.endswith("-en.html") else ("zh-Hans" if name.endswith("-zhs.html") else "zh-Hant")

    # Extract info from existing tags
    title_m = re.search(r"<title>(.*?)</title>", text)
    desc_m = re.search(r'<meta name="description" content="(.*?)"', text)
    canonical_m = re.search(r'<link rel="canonical" href="(.*?)"', text)
    canonical_url = canonical_m.group(1) if canonical_m else ""
    title = title_m.group(1) if title_m else ""
    desc = desc_m.group(1) if desc_m else ""

    og_locale = {"zh-Hant": "zh_TW", "zh-Hans": "zh_CN", "en": "en_US"}.get(lang, "zh_TW")
    og_title_esc = title[:80].replace('"', "'")
    desc_esc = desc[:150].replace('"', "'")

    # Build OG + Twitter blocks
    og_block = f"""<meta property="og:type" content="article">
<meta property="og:title" content="{og_title_esc}">
<meta property="og:description" content="{desc_esc}">
<meta property="og:url" content="{canonical_url}">
<meta property="og:locale" content="{og_locale}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{og_title_esc}">"""

    # Build Article JSON-LD if missing
    today_iso = date.today().isoformat()
    # Try to extract date from filename
    date_m = re.match(r"(\d{4})(\d{2})(\d{2})", name)
    pub_date = f"{date_m.group(1)}-{date_m.group(2)}-{date_m.group(3)}" if date_m else today_iso

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

    # Fix description CTA: append CTA if not already present
    desc_old = desc_m.group(0) if desc_m else ""
    if "免費排盤" not in desc_old and "free chart" not in desc_old.lower() and "free reading" not in desc_old.lower():
        cta_suffix = "免費排盤即得完整命盤解讀。" if lang != "en" else "Free chart reading with complete interpretation."
        new_desc = desc_old.rstrip('">') + f"。{cta_suffix}\">"
        text = text.replace(desc_old, new_desc)

    # Add OG block after description (before canonical or after keywords/robots)
    if 'og:title' not in text:
        # Insert OG block after the last meta tag before </head> or before <style>
        insert_point = r'(<style|<link rel="canonical|<script type="application/ld\+json|<link rel="alternate)'
        # Insert after the robots/canonical/hreflang block, before the next section
        m = re.search(r'(</head>)', text)
        if m:
            # Find a good insertion point - after last meta tag
            # Better: insert after the description meta tag
            desc_end = re.search(r'<meta name="description" content=".*?">', text)
            if desc_end:
                pos = desc_end.end()
                text = text[:pos] + "\n" + og_block + text[pos:]
                print(f"    + OG tags after description")
            else:
                # Insert before </head>
                text = text.replace("</head>", og_block + "\n</head>")
                print(f"    + OG tags before </head>")
        else:
            text = text.replace("</head>", og_block + "\n</head>")
            print(f"    + OG tags before </head>")

    # Add Article schema if missing
    if '"@type": "Article"' not in text:
        text = text.replace("</head>", article_schema + "\n</head>")
        print(f"    + Article schema")

    if text != original:
        fp.write_text(text, encoding="utf-8")
        return True
    return False

fixed = 0
for pattern in ["20260516-*.html", "20260517-*.html", "20260518-01*.html"]:
    for fp in sorted(BASE_DIR.glob(f"articles/{pattern}")):
        fn = fp.name
        if fn == "index.html":
            continue
        print(f"📄 {fn}")
        try:
            if fix_article(fp):
                fixed += 1
                print(f"  ✅ 已修复")
            else:
                print(f"  ➖ 无需修改")
        except Exception as e:
            print(f"  ❌ 错误: {e}")

print(f"\n✅ 总计: {fixed} 个文件已修复")
