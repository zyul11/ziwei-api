#!/usr/bin/env python3
"""
监控 Google Search Central + web.dev 博客，检测新的 SEO 相关内容
- 拉取 RSS feed
- 与上次记录比较
- 新文章 → 提取要点 → 建议规则变更
- 输出到 knowledge/seo_updates_log.md

用法：
  python3 scripts/monitor_seo_sources.py
"""
import re
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import urlopen, Request

BASE_DIR = Path(__file__).resolve().parent.parent
KB_DIR = Path("/home/ubuntu/knowledge/seo")
LOG_PATH = KB_DIR / "seo_updates_log.md"
STATE_PATH = Path("/tmp/seo_monitor_state.json")
GEFEI_KB_PATH = KB_DIR / "gefei-seo-deep-kb.md"

SOURCES = [
    {
        "name": "Google Search Central",
        "url": "https://developers.google.com/search/blog/feed.xml",
        "keywords": ["search", "spam", "ranking", "indexing", "crawl", "structured data",
                      "schema", "seo", "meta", "canonical", "hreflang", "sitemap",
                      "core update", "algorithm", "ai overview", "generative"],
    },
    {
        "name": "web.dev",
        "url": "https://web.dev/feed.xml?hl=en",
        "keywords": ["seo", "performance", "core web vitals", "lighthouse",
                      "mobile", "accessibility", "lcp", "cls", "inp", "fid",
                      "loading", "responsive", "image optimization"],
    },
]

SEO_KEYWORDS_SET = {"seo", "search", "ranking", "crawl", "indexing", "spam", "structured data",
                    "schema", "canonical", "sitemap", "core web vitals", "lighthouse",
                    "generative", "ai overview", "algorithm", "performance", "mobile-first",
                    "core update", "hreflang", "googlebot"}

def fetch_rss(url: str) -> list:
    """Fetch RSS feed and extract items"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; SEOMonitorBot/1.0; +https://textools.site/seo-audit)',
        'Accept': 'application/rss+xml, application/xml, text/xml'
    }
    req = Request(url, headers=headers)
    items = []
    try:
        with urlopen(req, timeout=15) as resp:
            data = resp.read().decode('utf-8', errors='replace')
        root = ET.fromstring(data)
        # Handle both RSS and Atom
        channel = root.find('channel')
        if channel is not None:
            for item in channel.findall('item'):
                title_el = item.find('title')
                link_el = item.find('link')
                desc_el = item.find('description')
                pub_el = item.find('pubDate')
                guid_el = item.find('guid')
                items.append({
                    'title': (title_el.text or '').strip() if title_el is not None else '',
                    'link': (link_el.text or '').strip() if link_el is not None else '',
                    'description': strip_html((desc_el.text or '') if desc_el is not None else ''),
                    'pub_date': (pub_el.text or '').strip() if pub_el is not None else '',
                    'guid': (guid_el.text or '').strip() if guid_el is not None else (link_el.text or '').strip() if link_el is not None else '',
                })
    except Exception as e:
        print(f"  ⚠️ 抓取失败: {e}")
    return items

def strip_html(text: str) -> str:
    """Remove HTML tags from text"""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:300]

def is_seo_relevant(item: dict) -> bool:
    """Check if an article is relevant to SEO"""
    text = (item.get('title', '') + ' ' + item.get('description', '')).lower()
    matches = sum(1 for kw in SEO_KEYWORDS_SET if kw in text)
    return matches >= 1

def load_state() -> dict:
    """Load last-seen state"""
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except:
            pass
    return {"last_guid": "", "seen_guids": []}

def save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, indent=2))

def suggest_rules(article: dict) -> list:
    """Suggest potential rule changes based on article content"""
    title = article.get('title', '').lower()
    desc = article.get('description', '').lower()
    combined = title + ' ' + desc
    suggestions = []

    # Match known patterns
    if 'generative' in combined or 'ai overview' in combined or 'ai in search' in combined:
        suggestions.append({
            'type': 'new_rule',
            'confidence': 'experimental',
            'id': 'ai_content_optimization',
            'name': 'AI Search Optimization',
            'description': 'Content optimized for generative AI search features (structured answers, entity clarity)',
            'source_article': article.get('link', ''),
        })
    if 'spam' in combined or 'back button' in combined or 'policy' in combined:
        suggestions.append({
            'type': 'rule_warning',
            'confidence': 'medium',
            'id': 'back_button_hijacking',
            'name': 'No Back Button Hijacking',
            'description': 'Google now explicitly penalizes sites that hijack the back button',
            'source_article': article.get('link', ''),
        })
    if 'core web vitals' in combined or 'lcp' in combined or 'cls' in combined or 'inp' in combined:
        suggestions.append({
            'type': 'weight_adjust',
            'confidence': 'medium',
            'id': 'page_speed',
            'name': 'Page Speed (Core Web Vitals)',
            'adjustment': '+2',
            'description': 'Google continues emphasizing Core Web Vitals for ranking',
            'source_article': article.get('link', ''),
        })
    if 'structured data' in combined or 'schema' in combined or 'json-ld' in combined:
        suggestions.append({
            'type': 'new_rule',
            'confidence': 'experimental',
            'id': 'schema_type_check',
            'name': 'Schema Type Validation',
            'description': 'Check that structured data uses the correct @type for the page content',
            'source_article': article.get('link', ''),
        })
    if 'mobile' in combined or 'mobile-first' in combined:
        suggestions.append({
            'type': 'weight_adjust',
            'confidence': 'medium',
            'id': 'viewport',
            'name': 'Mobile Viewport',
            'adjustment': '+1',
            'source_article': article.get('link', ''),
        })

    return suggestions


def run():
    print("🔍 监控 SEO 信息来源...")
    state = load_state()
    all_new = []
    all_suggestions = []

    for source in SOURCES:
        print(f"\n📡 {source['name']} ({source['url']})")
        items = fetch_rss(source['url'])
        print(f"   共 {len(items)} 条")

        new_items = []
        for item in items:
            if item['guid'] not in state.get('seen_guids', []):
                if is_seo_relevant(item):
                    new_items.append(item)

        if new_items:
            print(f"   🆕 SEO 相关新文章: {len(new_items)} 条")
            for ni in new_items:
                print(f"      📄 {ni['pub_date']} — {ni['title'][:80]}")
                print(f"         {ni['link']}")
                # Suggest rules
                suggestions = suggest_rules(ni)
                if suggestions:
                    for s in suggestions:
                        all_suggestions.append({**s, 'article': ni['title']})
                        print(f"         💡 建议规则: [{s['confidence']}] {s['name']}")

            all_new.extend(new_items)
            # Update state
            for ni in new_items:
                if ni['guid'] not in state['seen_guids']:
                    state['seen_guids'].append(ni['guid'])
        else:
            print("   ➖ 无新内容")

    # Keep only last 100 guids
    if len(state['seen_guids']) > 100:
        state['seen_guids'] = state['seen_guids'][-100:]

    save_state(state)

    # ── 输出日志 ──
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_entries = []
    log_entries.append(f"# SEO 信息来源监控日志\n")
    log_entries.append(f"上次更新: {timestamp}\n")

    if all_new:
        log_entries.append(f"## 🆕 新文章 ({len(all_new)} 条)\n")
        for item in all_new:
            log_entries.append(f"### {item['title']}")
            log_entries.append(f"- **来源**: {item.get('source_name', '')}")
            log_entries.append(f"- **日期**: {item['pub_date']}")
            log_entries.append(f"- **链接**: {item['link']}")
            log_entries.append(f"- **摘要**: {item['description'][:200]}")
            log_entries.append("")

        if all_suggestions:
            log_entries.append("## 💡 规则建议\n")
            log_entries.append("| 建议 | 置信度 | 来源文章 | 说明 |")
            log_entries.append("|------|--------|---------|------|")
            for s in all_suggestions:
                log_entries.append(f"| {s['name']} | {s['confidence']} | {s.get('article','')[:40]} | {s.get('description','')[:60]} |")
            log_entries.append("")
    else:
        log_entries.append("*暂无新内容*\n")

    # Write log
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(log_entries) + "\n", encoding="utf-8")
    print(f"\n📝 日志已保存: {LOG_PATH}")

    # Summary
    if all_suggestions:
        print(f"\n{'='*50}")
        print(f"📋 规则建议汇总 ({len(all_suggestions)} 条):")
        for s in all_suggestions:
            print(f"  [{s['confidence']:12s}] {s['name']}: {s.get('description','')}")
        print(f"\n💡 提示: experimental 建议需要手动审核后加入 seo-rules.json")
        print(f"   medium 建议可以直接应用为现有规则的权重调整")

    return all_suggestions


if __name__ == "__main__":
    run()
