#!/usr/bin/env python3
"""
紫微斗数繁体SEO软文自动生成脚本
可每日排程运行，从50+主题列表中轮换，使用DeepSeek AI生成
输出为 articles/ 目录下的独立HTML文件
"""

import os
import sys
import json
import random
import re
import unicodedata
from datetime import datetime, date
from pathlib import Path
from typing import Optional

# ── 确保项目根路径在sys.path中 ──
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# ── 尝试加载.env ──
env_path = BASE_DIR / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"

# ── 城市定向数据 ──
CITY_DATA = {
    "新加坡": {
        "region": "東南亞",
        "direction": "西北方位",
        "description": "華人為主，金融、科技、貿易行業興盛，氣候溫暖濕潤",
        "keywords": ["新加坡紫微鬥數", "獅城命理", "東南亞紫微"],
    },
    "台北": {
        "region": "台灣北部",
        "direction": "東北方位",
        "description": "科技、服務業、製造業發達，文化底蘊深厚",
        "keywords": ["台北紫微鬥數", "台灣命理", "北部紫微"],
    },
    "香港": {
        "region": "華南沿海",
        "direction": "正東方位",
        "description": "國際金融中心，貿易、地產行業興盛，中西文化交融",
        "keywords": ["香港紫微鬥數", "港島命理", "華南紫微"],
    },
    "吉隆坡": {
        "region": "東南亞",
        "direction": "正西方位",
        "description": "多元文化交匯，旅遊、科技行業蓬勃發展",
        "keywords": ["吉隆坡紫微鬥數", "大馬命理", "東南亞紫微"],
    },
}

# ── 50+ 文章主题列表 ──
ARTICLE_TOPICS = [
    # 主星专题
    "七殺坐命事業運",
    "破軍坐命創業運勢",
    "廉貞坐命感情運",
    "貪狼坐命桃花運",
    "紫微坐命帝王格局",
    "天機坐命智慧運勢",
    "太陽坐命光明格局",
    "武曲坐命財運解析",
    "天同坐命福氣運勢",
    "天府坐命財庫格局",

    # 综合运势
    "紫微鬥數看財運",
    "紫微鬥數看事業運",
    "紫微鬥數看感情運",
    "紫微鬥數看婚姻運",
    "紫微鬥數看健康運",
    "紫微鬥數看學業運",
    "紫微鬥數看子女運",
    "紫微鬥數看父母緣",
    "紫微鬥數看兄弟緣",
    "紫微鬥數看貴人運",

    # 星曜组合
    "武曲天相感情運勢",
    "天同太陰性格分析",
    "紫微天府帝王組合",
    "太陽太陰日月輝映",
    "廉貞貪狼風流彩蝶",
    "巨門天同口福之運",
    "七殺破軍廉貞殺破狼",
    "紫微天相輔佐帝王",
    "天機太陰機月同梁",
    "武曲七殺剛柔並濟",

    # 宫位专题
    "命宮空宮怎麼辦",
    "財帛宮星曜解析",
    "官祿宮事業運勢",
    "夫妻宮感情走向",
    "福德宮前世今生",
    "遷移宮外出運勢",
    "疾厄宮健康隱患",
    "兄弟宮手足緣分",
    "子女宮子女運勢",
    "田宅宮房產運勢",

    # 四化专题
    "化祿在命宮錢財運勢",
    "化權在官祿事業成就",
    "化科在財帛名望雙收",
    "化忌在疾厄健康提醒",
    "四化飛星祕訣解析",
    "自化祿自化忌含義",
    "命宮化祿一生順遂",
    "夫妻宮化科感情美滿",

    # 大限流年
    "十年大限如何看",
    "流年運勢解析方法",
    "大限祿權科忌影響",
    "2025年紫微流年運勢",
    "2026年紫微流年運勢",
    "2027年紫微流年運勢",

    # 命理文化
    "紫微鬥數與西方星座",
    "紫微鬥數與MBTI人格",
    "紫微鬥數歷史淵源",
    "安星法入門教學",
    "如何看懂紫微命盤",
    "紫微鬥數十二宮詳解",
    "命主身主含義解析",
    "紫微鬥數術語大全",
    "紫微鬥數看前世今生",
    "紫微鬥數看人生使命",

    # 特殊格局
    "日月並明富貴格局",
    "雄宿乾元格局解析",
    "月朗天門貴格",
    "石中隱玉祕藏格局",
    "府相朝垣貴氣格局",
    "將星得地武職榮顯",
    "文星拱命學業有成",
    "權祿巡逢事業高升",
]


# ── 拼音工具函数 ──
PINYIN_MAP = {
    '七': 'qi', '殺': 'sha', '坐': 'zuo', '命': 'ming', '事': 'shi', '業': 'ye', '運': 'yun',
    '破': 'po', '軍': 'jun', '創': 'chuang', '業': 'ye', '勢': 'shi',
    '廉': 'lian', '貞': 'zhen', '感': 'gan', '情': 'qing',
    '貪': 'tan', '狼': 'lang', '桃': 'tao', '花': 'hua',
    '紫': 'zi', '微': 'wei', '鬥': 'dou', '數': 'shu', '帝': 'di', '王': 'wang', '格': 'ge', '局': 'ju',
    '機': 'ji', '智': 'zhi', '慧': 'hui',
    '太': 'tai', '陽': 'yang', '光': 'guang', '明': 'ming',
    '武': 'wu', '曲': 'qu', '財': 'cai',
    '同': 'tong', '福': 'fu', '氣': 'qi',
    '府': 'fu', '庫': 'ku',
    '看': 'kan', '婚': 'hun', '姻': 'yin', '健': 'jian', '康': 'kang', '學': 'xue',
    '子': 'zi', '女': 'nv', '父': 'fu', '母': 'mu', '兄': 'xiong', '弟': 'di', '緣': 'yuan',
    '貴': 'gui', '人': 'ren',
    '天': 'tian', '相': 'xiang', '陰': 'yin', '性': 'xing', '格': 'ge',
    '組': 'zu', '合': 'he',
    '日': 'ri', '月': 'yue', '輝': 'hui', '映': 'ying',
    '風': 'feng', '流': 'liu', '彩': 'cai', '蝶': 'die',
    '口': 'kou', '福': 'fu',
    '殺': 'sha', '破': 'po', '狼': 'lang',
    '輔': 'fu', '佐': 'zuo',
    '機': 'ji', '月': 'yue', '梁': 'liang',
    '剛': 'gang', '柔': 'rou', '並': 'bing', '濟': 'ji',
    '空': 'kong', '宮': 'gong', '怎': 'zen', '麼': 'me', '辦': 'ban',
    '解析': 'jiexi',
    '走': 'zou', '向': 'xiang',
    '前': 'qian', '世': 'shi', '生': 'sheng',
    '遷': 'qian', '移': 'yi', '外': 'wai', '出': 'chu',
    '疾': 'ji', '厄': 'e', '隱': 'yin', '患': 'huan',
    '手': 'shou', '足': 'zu', '房': 'fang', '產': 'chan',
    '化': 'hua', '祿': 'lu', '權': 'quan', '科': 'ke', '忌': 'ji',
    '錢': 'qian', '成': 'cheng', '就': 'jiu', '名': 'ming', '望': 'wang', '雙': 'shuang', '收': 'shou',
    '提': 'ti', '醒': 'xing',
    '飛': 'fei', '星': 'xing', '祕': 'mi', '訣': 'jue',
    '自': 'zi', '含': 'han', '義': 'yi',
    '一': 'yi', '生': 'sheng', '順': 'shun', '遂': 'sui',
    '美': 'mei', '滿': 'man',
    '十': 'shi', '年': 'nian', '大': 'da', '限': 'xian', '如': 'ru', '何': 'he',
    '流': 'liu', '年': 'nian', '法': 'fa',
    '影': 'ying', '響': 'xiang',
    '歷': 'li', '史': 'shi', '淵': 'yuan', '源': 'yuan',
    '安': 'an', '星': 'xing', '法': 'fa', '入': 'ru', '門': 'men', '教': 'jiao', '學': 'xue',
    '懂': 'dong', '盤': 'pan',
    '十': 'shi', '二': 'er', '詳': 'xiang', '解': 'jie',
    '主': 'zhu', '身': 'shen', '含': 'han',
    '術': 'shu', '語': 'yu', '大': 'da', '全': 'quan',
    '人': 'ren', '生': 'sheng', '使': 'shi', '命': 'ming',
    '明': 'ming', '富': 'fu', '貴': 'gui',
    '雄': 'xiong', '宿': 'su', '乾': 'qian', '元': 'yuan',
    '朗': 'lang',
    '石': 'shi', '中': 'zhong', '隱': 'yin', '玉': 'yu', '祕': 'mi', '藏': 'cang',
    '朝': 'chao', '垣': 'yuan', '貴': 'gui',
    '將': 'jiang', '星': 'xing', '得': 'de', '地': 'di', '武': 'wu', '職': 'zhi', '榮': 'rong', '顯': 'xian',
    '文': 'wen', '拱': 'gong',
    '巡': 'xun', '逢': 'feng', '高': 'gao', '升': 'sheng',
    '與': 'yu', '西': 'xi', '方': 'fang', '星': 'xing', '座': 'zuo',
    '歷': 'li', '史': 'shi',
    '2025': '2025', '2026': '2026', '2027': '2027',
    'MBTI': 'mbti',
    '祕': 'mi',
}


def simple_pinyin(text: str) -> str:
    """将繁体中文转换为简单拼音（用于文件名）"""
    result = []
    for ch in text:
        if ch in PINYIN_MAP:
            result.append(PINYIN_MAP[ch])
        elif '\u4e00' <= ch <= '\u9fff':
            # 未映射的中文字，使用 unicode 编码
            result.append(f'u{ord(ch):04x}')
        elif ch.isalnum():
            result.append(ch.lower())
    return '-'.join(filter(None, result)).replace('--', '-').strip('-')


def get_article_topic(index: Optional[int] = None) -> str:
    """轮换获取文章主题，如果指定index则用该位置，否则随机"""
    if index is not None:
        return ARTICLE_TOPICS[index % len(ARTICLE_TOPICS)]
    # 也可基于日期选择：每天一个主题
    day_of_year = date.today().timetuple().tm_yday
    return ARTICLE_TOPICS[day_of_year % len(ARTICLE_TOPICS)]


def build_prompt(topic: str, city: str) -> list:
    """构建 DeepSeek 生成文章的 prompt"""
    city_info = CITY_DATA.get(city, {
        "region": "華人地區",
        "direction": "中心方位",
        "description": "多元文化交融之地",
        "keywords": [f"{city}紫微鬥數"],
    })

    system_prompt = """你是紫微斗数专家，精通繁体中文命理写作。请用专业但通俗易懂的繁体中文写一篇 SEO 优化的紫微斗数软文。

写作要求：
1. 标题格式：使用「紫微斗數XXX」或「XXX運勢」或「XXX命盤解析」作为标题，**标题长度请控制在20-55字以内**
2. 文章长度：**800-1500字（必须超过800字，少于800字将不被接受）**
3. 语言风格：繁体中文（香港/台湾用语），亲切专业，带点神秘感
4. SEO优化：自然融入长尾关键词，标题包含核心关键词
5. 内容结构：开篇引言 → 核心分析（2-3小节带小标题）→ 给读者的建议 → CTA引导
6. 文章底部必须包含CTA，引导读者到 /index.html 免费排盘体验 和 /shop.html 购买完整解读
7. 情感基调：积极正面，给人希望和方向
8. 每段都不超过200字，段落之间空一行

输出格式为 JSON：
{
  "title": "文章标题（繁体）",
  "description": "SEO meta description，不超过160字",
  "keywords": "SEO keywords，逗号分隔，不超过10个",
  "content_html": "文章HTML正文（繁体，包含h2小标题、p段落，末尾CTA）"
}"""

    user_prompt = f"""请写一篇面向 {city}（{city_info['region']}，{city_info['direction']}）读者的紫微斗数文章。

主题：{topic}

{city}地区特点：{city_info['description']}

请在文章中自然地融入以下关键词：{', '.join(city_info['keywords'])}

文章末尾的CTA请使用繁体中文，引导用户：
- 前往 /index.html 免费体验紫微斗数排盘
- 前往 /shop.html 购买完整AI解读

请直接输出JSON，不要加markdown代码块标记。"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def call_deepseek(messages: list) -> Optional[dict]:
    """调用 DeepSeek API 生成文章"""
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "sk-your-key-here":
        print("⚠️  未设置 DEEPSEEK_API_KEY，使用模拟数据")
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=0.8,
            max_tokens=3000,
        )
        content = resp.choices[0].message.content.strip()
        # 去掉可能的 markdown 代码块包裹
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        return json.loads(content)
    except Exception as e:
        print(f"❌ DeepSeek API 调用失败: {e}")
        return None


def get_mock_article(topic: str, city: str) -> dict:
    """当API不可用时返回模拟文章"""
    city_info = CITY_DATA.get(city, {
        "region": "華人地區",
        "direction": "中心方位",
        "description": "多元文化交融之地",
        "keywords": [f"{city}紫微鬥數"],
    })
    return {
        "title": f"紫微斗數看{topic} — {city}地區運勢深度解析",
        "description": f"紫微斗數專家為{city}讀者深度解析{topic}，結合命盤星曜組合，提供專業的運勢指引與人生建議。",
        "keywords": f"紫微斗數,{topic},{city}紫微斗數,命盤解析,{city_info['keywords'][0]}",
        "content_html": f"""<h2>開篇：{topic}的命理奧秘</h2>
<p>在紫微斗數的宇宙中，每顆星曜都承載著獨特的能量與信息。對於身處{city}的朋友來說，理解自身的命盤結構，是掌握人生節奏的關鍵。本文將為您深入剖析{topic}的背後意涵，結合{city}的地緣能量，為您提供專屬的運勢指引。</p>

<h2>核心解析：{topic}的關鍵影響</h2>
<p>在紫微斗數命盤中，星曜的排列組合決定了個人的先天特質與後天運勢走向。{topic}這一命題，涉及了多個宮位的交互作用，以及主星、輔星的吉凶影響。命宮中的主星決定了您的核心性格，而兄弟宮、夫妻宮等則反映了人際關係的質量。</p>
<p>若您的命盤中出現了吉星匯聚的情況，這代表您在相關領域擁有天生的優勢。反之，若煞星較多，則需要通過後天的調整與努力來化解。紫微斗數不僅是一門預測學，更是一門人生智慧學，幫助我們在了解自身的基礎上，做出更明智的選擇。</p>

<h2>給{city}讀者的實用建議</h2>
<p>身在{city}這座充滿活力的城市，您的事業、感情、財運都與城市能量息息相關。建議您可以通過紫微斗數排盤，深入了解自己的命盤結構，並根據當下的流年運勢，做出最適合自己的規劃。每個人的命盤都是獨一無二的，真正的智慧在於順應天時、把握機遇。</p>

<h2>結語：開啟您的命盤探索之旅</h2>
<p>紫微斗數的智慧源遠流長，它不僅能幫助我們認清自身的優勢與劣勢，更能指引我們在人生的關鍵節點做出正確的選擇。如果您對自己的命盤感到好奇，不妨現在就開始探索。</p>

<div class="cta-section">
<p><strong>✨ 準備好探索您的命盤了嗎？</strong></p>
<p>👉 <a href="/index.html" style="color:#7b68ee;font-weight:600;">免費體驗紫微斗數排盤 →</a> 輸入出生資訊即可查看您的專屬命盤</p>
<p>👉 <a href="/shop.html" style="color:#f0d060;font-weight:600;">購買完整AI解讀 →</a> 解鎖3000+字的深度命盤分析</p>
</div>"""
    }


def build_html(article: dict, topic: str, city: str, published_date: str) -> str:
    """构建最终的 HTML 文件（含完整SEO：OG、Twitter、JSON-LD）"""
    city_info = CITY_DATA.get(city, {})
    region = city_info.get("region", city)
    canonical_url = f"https://ziweiapi.site/articles/{published_date}-{simple_pinyin(topic)}.html"
    # Truncate title for HTML tag (30-55 chars optimal)
    raw_title = article['title']
    if len(raw_title) > 55:
        raw_title = raw_title[:52] + '...'
    og_title = raw_title[:80].replace('"', "'")
    # Truncate meta description to 100-155 chars
    raw_desc = article.get('description', article['title'])
    if len(raw_desc) > 152:
        raw_desc = raw_desc[:149] + '...'
    elif len(raw_desc) < 100:
        raw_desc = raw_desc + ' — 免費線上排盤即得完整命盤解讀。'
    og_desc = raw_desc[:150].replace('"', "'")
    pub_date_iso = f"{published_date[:4]}-{published_date[4:6]}-{published_date[6:8]}"
    json_ld = f"""{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{og_title}",
  "description": "{og_desc}",
  "datePublished": "{pub_date_iso}",
  "author": {{"@type": "Person", "name": "Ziwei Master"}},
  "publisher": {{"@type": "Organization", "name": "Ziwei API"}},
  "inLanguage": "zh-Hant"
}}"""
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5545263418745440" crossorigin="anonymous"></script>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{raw_title}</title>
<meta name="description" content="{raw_desc}">
<meta name="keywords" content="{article.get('keywords', topic)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{canonical_url}">
<link rel="alternate" hreflang="zh-Hant" href="{canonical_url}">
<link rel="alternate" hreflang="zh-Hans" href="{canonical_url.replace('/articles/', '/zhs/articles/')}">
<link rel="alternate" hreflang="en" href="{canonical_url.replace('/articles/', '/en/articles/')}">
<link rel="alternate" hreflang="x-default" href="{canonical_url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_desc}">
<meta property="og:url" content="{canonical_url}">
<meta property="og:locale" content="zh_TW">
<meta property="og:image" content="https://ziweiapi.site/og-image.jpg">
<meta property="og:image:alt" content="紫微鬥數命盤推演">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{og_desc}">
<script type="application/ld+json">{json_ld}</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{
  font-family:'Noto Sans SC','PingFang TC','Microsoft JhengHei',sans-serif;
  background:#0a0a14;color:#d0c8e0;min-height:100vh;position:relative;line-height:1.8
}}
body::before{{
  content:'';position:fixed;inset:0;
  background:radial-gradient(1px 1px at 10%20%,rgba(255,255,255,.3),transparent),
             radial-gradient(1px 1px at 30%60%,rgba(255,255,255,.2),transparent),
             radial-gradient(1px 1px at 50%10%,rgba(255,255,255,.25),transparent),
             radial-gradient(1.5px 1.5px at 85%65%,rgba(255,215,0,.2),transparent),
             radial-gradient(1.5px 1.5px at 25%55%,rgba(123,104,238,.2),transparent);
  pointer-events:none;z-index:0
}}
body::after{{
  content:'';position:fixed;top:50%;left:50%;
  width:700px;height:700px;margin:-350px 0 0 -350px;border-radius:50%;
  background:conic-gradient(from 0deg,transparent,rgba(123,104,238,.04),transparent 30%,rgba(123,104,238,.02),transparent 60%,rgba(123,104,238,.03),transparent);
  pointer-events:none;z-index:0;animation:bgSpin 40s linear infinite
}}
@keyframes bgSpin{{from{{transform:translate(-50%,-50%) rotate(0deg)}}to{{transform:translate(-50%,-50%) rotate(360deg)}}}}
.container{{max-width:800px;margin:0 auto;padding:24px 20px;position:relative;z-index:1}}
.article-header{{text-align:center;padding:30px 0 20px;border-bottom:1px solid rgba(123,104,238,.12);margin-bottom:24px}}
.article-header .meta{{font-size:11px;color:#5a4a7a;letter-spacing:1px;margin-bottom:8px}}
.article-header .meta .tag{{display:inline-block;background:rgba(123,104,238,.12);border:1px solid rgba(123,104,238,.15);border-radius:4px;padding:1px 8px;font-size:10px;color:#7b68ee;margin-left:6px}}
.article-header h1{{
  font-family:'Noto Serif SC','Noto Serif TC',serif;font-size:26px;font-weight:900;
  background:linear-gradient(135deg,#e0c8ff,#7b68ee,#4a3aa0);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:2px;line-height:1.4
}}
.article-body{{font-size:15px;color:#c8c0d8;padding:0 4px}}
.article-body h2{{font-size:18px;font-weight:700;color:#c4a0ff;margin:28px 0 12px;padding-bottom:6px;border-bottom:1px solid rgba(123,104,238,.1);letter-spacing:1.5px}}
.article-body p{{margin-bottom:16px;text-indent:2em}}
.article-body a{{color:#7b68ee;text-decoration:none;border-bottom:1px solid rgba(123,104,238,.2);transition:all .2s}}
.article-body a:hover{{color:#a080ff;border-color:#7b68ee}}
.cta-section{{
  margin-top:32px;padding:24px;border-radius:14px;
  background:linear-gradient(135deg,rgba(26,26,46,.93),rgba(16,16,30,.93));
  border:1px solid rgba(123,104,238,.18);text-align:center
}}
.cta-section p{{text-indent:0!important;margin-bottom:10px!important}}
.cta-section .cta-title{{font-size:17px;font-weight:700;color:#e0c8ff;margin-bottom:12px;letter-spacing:1.5px}}
.cta-section .cta-btn{{
  display:inline-block;padding:10px 28px;margin:4px 6px;border-radius:10px;text-decoration:none;
  font-size:14px;font-weight:600;letter-spacing:1px;transition:all .3s
}}
.cta-section .cta-btn.primary{{background:linear-gradient(135deg,#7b68ee,#5a4acd);color:#fff;border:none;box-shadow:0 4px 16px rgba(123,104,238,.25)}}
.cta-section .cta-btn.primary:hover{{transform:translateY(-2px);box-shadow:0 6px 24px rgba(123,104,238,.4)}}
.cta-section .cta-btn.secondary{{background:transparent;color:#c4a0ff;border:1px solid rgba(123,104,238,.25)}}
.cta-section .cta-btn.secondary:hover{{border-color:#7b68ee;background:rgba(123,104,238,.08)}}
.city-badge{{
  display:inline-flex;align-items:center;gap:4px;
  background:rgba(123,104,238,.08);border:1px solid rgba(123,104,238,.12);
  border-radius:20px;padding:3px 12px;font-size:11px;color:#9a8aaa
}}
.footer{{text-align:center;padding:30px 0;color:#3a2a5a;font-size:11px;letter-spacing:.5px;line-height:1.8}}
@media(max-width:600px){{.article-header h1{{font-size:22px}}.article-body{{font-size:14px}}}}
</style>
</head>
<body>
<div class="container">
  <article>
    <div class="article-header">
      <div class="meta">
        <span>{published_date}</span>
        <span class="tag">🌏 {region}</span>
        <span class="city-badge">📍 {city}</span>
      </div>
      <h1>{article['title']}</h1>
    </div>
    <div class="article-body">
      {article['content_html']}
    </div>
  </article>
  <div class="subscribe-section" style="margin-top:24px;padding:20px;border-radius:14px;background:linear-gradient(135deg,rgba(26,26,46,.93),rgba(16,16,30,.93));border:1px solid rgba(123,104,238,.18);text-align:center">
    <h3 style="font-size:16px;color:#c4a0ff;margin-bottom:10px">每日紫微运势订阅</h3>
    <p style="font-size:13px;color:#a898b8;margin-bottom:12px;text-indent:0">基于您的命盘，每日推送专属运势分析 · 幸运色 · 宜忌指南</p>
    <p style="font-size:12px;color:#7a6a9a;margin-bottom:14px;text-indent:0">$4.9/月 · $29.9/年</p>
    <a href="/index.html#subscribe" class="cta-btn primary">立即订阅</a>
  </div>
  <div class="footer">
    <p>⚠️ AI生成內容僅供娛樂參考，不構成專業建議 · 基於 DeepSeek AI</p>
    <p>紫微鬥數 · AI 命盤推演 | <a href="/index.html" style="color:#5a4a7a;text-decoration:none;">免費排盤</a> | <a href="/shop.html" style="color:#5a4a7a;text-decoration:none;">購買 Key</a></p>
    <p style="margin-top:6px;font-size:10px">© {datetime.now().year} 紫微鬥數 AI · 版權所有</p>
  </div>
</div>
</body>
</html>"""


def run(index: Optional[int] = None, city: Optional[str] = None, output_dir: Optional[str] = None):
    """
    主运行函数
    - index: 文章主题索引（None则按日期自动轮换）
    - city: 面向城市（None则随机选择）
    - output_dir: 输出目录（默认 articles/）
    """
    if city is None:
        city = random.choice(list(CITY_DATA.keys()))

    if output_dir is None:
        output_dir = str(BASE_DIR / "articles")

    topic = get_article_topic(index)
    today_str = date.today().strftime("%Y%m%d")

    print(f"📝 生成文章：{topic}")
    print(f"📍 面向城市：{city}")
    print(f"📅 日期：{today_str}")

    # 构建 prompt 并调用 API
    messages = build_prompt(topic, city)
    result = call_deepseek(messages)

    if result is None:
        print("🔧 使用模拟文章（API未配置或调用失败）")
        result = get_mock_article(topic, city)

    pinyin = simple_pinyin(topic)
    filename = f"{today_str}-{pinyin}.html"
    filepath = Path(output_dir) / filename

    html = build_html(result, topic, city, today_str)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(html, encoding="utf-8")

    print(f"✅ 文章已生成：{filepath}")
    print(f"📌 标题：{result['title']}")
    print(f"🏷️  关键词：{result.get('keywords', '')}")
    return filepath


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="紫微斗数繁体SEO软文自动生成")
    parser.add_argument("--index", type=int, default=None, help="文章主题索引（0-{len(ARTICLE_TOPICS)-1}）")
    parser.add_argument("--city", type=str, default=None, choices=list(CITY_DATA.keys()),
                        help=f"面向城市（默认随机：{', '.join(CITY_DATA.keys())}）")
    parser.add_argument("--output", type=str, default=None, help="输出目录（默认 articles/）")
    args = parser.parse_args()

    run(index=args.index, city=args.city, output_dir=args.output)
