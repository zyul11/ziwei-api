#!/usr/bin/env python3
"""
Auto-generate articles/index.html by scanning the articles/ directory.
Reads each HTML file's <title> and <meta description> tags.
Groups by date, shows 繁/简/EN versions.
"""
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "articles"
OUTPUT_PATH = ARTICLES_DIR / "index.html"

SITE_URL = "https://ziweiapi.site"


def parse_html(filepath: Path) -> dict:
    """Extract <title> and <meta description> from an HTML file"""
    try:
        text = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    title_m = re.search(r'<title>(.*?)</title>', text, re.DOTALL)
    title = title_m.group(1).strip() if title_m else filepath.stem

    desc_m = re.search(r'<meta name="description" content="(.*?)"', text, re.DOTALL)
    desc = desc_m.group(1).strip() if desc_m else ""

    return {"title": title, "desc": desc}


def detect_lang(filename: str) -> str:
    """Detect language from filename"""
    if filename.endswith("-en.html"):
        return "en"
    elif filename.endswith("-zhs.html"):
        return "zh-Hans"
    else:
        return "zh-Hant"


def make_lang_tag(lang: str) -> str:
    return {
        "zh-Hant": '<span class="lt hant">繁</span>',
        "zh-Hans": '<span class="lt hans">简</span>',
        "en": '<span class="lt en">EN</span>',
    }.get(lang, "")


def run():
    # Scan all HTML files in articles/
    articles = []
    if ARTICLES_DIR.exists():
        for f in sorted(ARTICLES_DIR.glob("*.html"), reverse=True):
            if f.name == "index.html":
                continue
            parsed = parse_html(f)
            if parsed is None:
                continue
            lang = detect_lang(f.name)
            # Extract date from filename (YYYYMMDD format)
            date_m = re.match(r"(\d{8})", f.name)
            pub_date = date_m.group(1) if date_m else ""

            # Map date to YYYY-MM-DD
            display_date = f"{pub_date[:4]}-{pub_date[4:6]}-{pub_date[6:8]}" if pub_date else ""

            # Base file (without lang suffix)
            base = re.sub(r"(-(en|zhs))?\.html$", "", f.name)

            articles.append({
                "file": f.name,
                "base": base,
                "title": parsed["title"],
                "desc": parsed["desc"],
                "lang": lang,
                "date": display_date,
                "raw_date": pub_date,
            })

    # Group by base filename
    groups = {}
    for a in articles:
        key = a["base"]
        if key not in groups:
            groups[key] = {"date": a["date"], "raw_date": a["raw_date"], "versions": {}}
        groups[key]["versions"][a["lang"]] = a

    # Sort by date descending
    sorted_keys = sorted(groups.keys(), key=lambda k: groups[k]["raw_date"], reverse=True)

    # Build JS data
    js_entries = []
    for key in sorted_keys:
        g = groups[key]
        vers = g["versions"]
        hant = vers.get("zh-Hant", {})
        hans = vers.get("zh-Hans", {})
        en = vers.get("en", {})

        title_hant = hant.get("title", "")
        title_hans = hans.get("title", "")
        title_en = en.get("title", "")
        desc_zh = hant.get("desc", hans.get("desc", ""))
        desc_en = en.get("desc", "")

        # Just use the base file for link (点繁去繁，点简去简)
        base_file = hant.get("file", "").replace(".html", "") if hant.get("file") else ""

        js_entries.append(f'''  {{
    date:'{g["date"]}', file:'{base_file}',
    zhHant:'{title_hant}', zhHans:'{title_hans}', en:'{title_en}',
    descZh:'{desc_zh}', descEn:'{desc_en}'
  }}''')

    js_data = ",\n".join(js_entries)

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>紫微鬥數命理文章 - 每日運勢分析 | Ziweiapi</title>
<meta name="description" content="紫微鬥數每日命理文章，涵蓋十四主星運勢、財帛宮事業宮解析、各地命理指南。繁體中文/简体中文/English。">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{SITE_URL}/articles/">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a14;color:#d0c8e0;min-height:100vh;line-height:1.6}}
.container{{max-width:800px;margin:0 auto;padding:20px}}
h1{{color:#e8b860;font-size:22px;margin:30px 0 6px;letter-spacing:2px}}
.sub{{color:#7a6a9a;font-size:12px;margin-bottom:24px;letter-spacing:1px}}
.lang-filter{{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}}
.lang-filter button{{background:transparent;border:1px solid #3a2a5a;color:#7a6a9a;padding:4px 14px;border-radius:6px;font-size:12px;cursor:pointer;transition:all .2s}}
.lang-filter button:hover{{border-color:#e8a040;color:#e8a040}}
.lang-filter button.active{{background:rgba(232,160,64,.12);border-color:#e8a040;color:#e8b860}}
.article-list{{list-style:none}}
.article-item{{background:linear-gradient(135deg,rgba(26,26,46,.93),rgba(16,16,30,.93));border:1px solid rgba(232,160,64,.15);border-radius:10px;padding:14px 18px;margin-bottom:10px;transition:border-color .2s}}
.article-item:hover{{border-color:#e8a040}}
.article-item a{{text-decoration:none;color:#d0c8e0;display:block}}
.article-item .date{{font-size:11px;color:#7a6a9a;letter-spacing:1px}}
.article-item .title{{font-size:15px;color:#e8b860;margin:4px 0;font-weight:500}}
.article-item .desc{{font-size:12px;color:#8a7a9a}}
.article-item .lang-tags{{display:flex;gap:4px;margin-top:6px}}
.article-item .lang-tags .lt{{font-size:10px;padding:1px 6px;border-radius:3px;border:1px solid}}
.article-item .lang-tags .lt.hant{{border-color:rgba(232,160,64,.3);color:#e8a040}}
.article-item .lang-tags .lt.hans{{border-color:rgba(123,104,238,.3);color:#a080ff}}
.article-item .lang-tags .lt.en{{border-color:rgba(100,200,150,.3);color:#64c896}}
.back{{display:inline-block;margin-top:30px;color:#7a6a9a;font-size:12px;text-decoration:none}}
.back:hover{{color:#e8a040}}
</style>
</head>
<body>
<div class="container">
  <h1>📖 命理文章</h1>
  <div class="sub">紫微鬥數每日運勢分析 · 十四主星深度解析 · 真實命盤解讀</div>
  <div class="lang-filter">
    <button class="active" data-filter="all" onclick="filterLang('all')">全部</button>
    <button data-filter="zh-Hant" onclick="filterLang('zh-Hant')">繁</button>
    <button data-filter="zh-Hans" onclick="filterLang('zh-Hans')">简</button>
    <button data-filter="en" onclick="filterLang('en')">EN</button>
  </div>
  <ul class="article-list" id="articleList"></ul>
  <a href="/" class="back">← 返回首页</a>
</div>
<script>
const articles = [
{js_data}
];
let currentFilter = 'all';
function filterLang(l) {{
  currentFilter = l;
  document.querySelectorAll('.lang-filter button').forEach(b => b.classList.toggle('active', b.dataset.filter === l));
  renderList();
}}
function renderList() {{
  const list = document.getElementById('articleList');
  list.innerHTML = '';
  articles.forEach(a => {{
    const hasHant = a.zhHant && a.zhHant !== '';
    const hasHans = a.zhHans && a.zhHans !== '';
    const hasEn = a.en && a.en !== '';
    if (currentFilter !== 'all') {{
      if (currentFilter === 'zh-Hant' && !hasHant) return;
      if (currentFilter === 'zh-Hans' && !hasHans) return;
      if (currentFilter === 'en' && !hasEn) return;
    }}
    const li = document.createElement('li');
    li.className = 'article-item';
    let varHref = a.file;
    if (currentFilter === 'zh-Hant' && hasHant) varHref = a.file + (a.zhHant ? '.html' : '');
    else if (currentFilter === 'zh-Hans' && hasHans) varHref = a.file + '-zhs.html';
    else if (currentFilter === 'en' && hasEn) varHref = a.file + '-en.html';
    else if (hasHant) varHref = a.file + '.html';
    else if (hasHans) varHref = a.file + '-zhs.html';
    else if (hasEn) varHref = a.file + '-en.html';
    let title = a.zhHant || a.zhHans || a.en || '';
    let desc = a.descZh || a.descEn || '';
    let langTags = '';
    if (hasHant) langTags += '<span class="lt hant">繁</span>';
    if (hasHans) langTags += '<span class="lt hans">简</span>';
    if (hasEn) langTags += '<span class="lt en">EN</span>';
    li.innerHTML = `<a href="/articles/${{varHref.replace('.html','')}}.html">
      <div class="date">${{a.date}}</div>
      <div class="title">${{title}}</div>
      <div class="desc">${{desc}}</div>
      <div class="lang-tags">${{langTags}}</div>
    </a>`;
    list.appendChild(li);
  }});
}}
renderList();
</script>
</body>
</html>"""

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"✅ 文章列表已更新: {OUTPUT_PATH} ({len(js_entries)} 篇文章)")


if __name__ == "__main__":
    run()
