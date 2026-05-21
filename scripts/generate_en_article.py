#!/usr/bin/env python3
"""
English SEO soft article generator for Ziwei Doushu API
Zi Wei Dou Shu articles for overseas Chinese & second-generation diaspora
Outputs to articles/en/ as standalone HTML files
"""

import os
import sys
import json
import random
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Load .env
env_path = BASE_DIR / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"

# ── 50+ English article topics for overseas Chinese / second-gen diaspora ──
ARTICLE_TOPICS = [
    # ── Tarot bridge (10 topics) ──
    "Tarot Tower vs Chinese Daxian: Predicting life's crises",
    "The Fool's Journey: Comparing Tarot with Chinese zodiac destiny",
    "Tarot Death card meaning vs Chinese Ba Zi transformation cycles",
    "Tarot lovers card and Chinese zodiac compatibility",
    "Sun Tarot card vs Tai Yang star: Which fortune system is brighter?",
    "Tarot Wheel of Fortune vs Chinese Four Transformations (Hua Lu, Quan, Ke, Ji)",
    "Tarot High Priestess vs Tian Ji star: Intuition across two systems",
    "Tarot Emperor vs Zi Wei star: Authority figures in fortune telling",
    "Tarot Star card vs Tian Liang star: Hope and healing in your chart",
    "Tarot Judgement vs Po Jun star: Transformation and rebirth",

    # ── Western zodiac bridge (10 topics) ──
    "Aries vs Tai Yang star: The fire sign in Chinese astrology",
    "Pisces vs Tian Tong star: Are they the same dreamer?",
    "Scorpio vs Qi Sha star: The intense warrior archetype",
    "Leo vs Zi Wei star: Two versions of royalty",
    "Your Western zodiac vs Chinese Ba Zi: Which knows you better?",
    "Western zodiac compatibility vs Chinese palace matching: Love accuracy test",
    "Capricorn vs Wu Qu star: The ambitious achiever in two traditions",
    "Gemini vs Tian Fu star: Adaptability and versatility compared",
    "Libra vs Tai Yin star: Beauty and balance across cultures",
    "Cancer vs Tian Xiang star: Nurturing energy in East and West",

    # ── Horoscope / daily fortune bridge (8 topics) ──
    "Weekly tarot reading vs Chinese daily Ba Zi fortune",
    "Your daily horoscope is wrong? Try Chinese Ba Zi instead",
    "Birth chart reading: Western vs Chinese — a comparison",
    "What your Chinese birth chart says about 2026",
    "Lucky colors: Western color astrology vs Chinese five elements",
    "New moon intentions backed by Chinese lunar astrology",
    "2026 monthly Chinese fortune preview: what each month brings",
    "Full moon energy vs Chinese zodiac: lunar cycles decoded",

    # ── Developer / API angles (6 topics) ──
    "How I built a Chinese astrology app with one API",
    "Build a fortune telling bot in 10 minutes using Python + API",
    "The hidden API of Chinese astrology: a developer's guide",
    "Why I switched from Western astrology API to Chinese Ba Zi",
    "Tarot API vs Chinese astrology API: which one for your app?",
    "Integrate Chinese fortune into your website with one endpoint",

    # ── Personality / self-discovery (8 topics) ──
    "14 Chinese zodiac personalities: find your inner star",
    "Chinese zodiac vs MBTI: A surprising personality match",
    "What's your Chinese destiny star? A beginner's guide",
    "The 12 palaces of Chinese astrology explained simply",
    "Chinese zodiac 2026: predictions for every birth year",
    "Your Chinese fortune reading: a step-by-step guide",
    "Career guidance from Chinese astrology: which star drives you?",
    "Love and relationships by Chinese zodiac: find your match",

    # ── Cultural curiosity (8 topics) ──
    "Ancient Chinese astrology: still relevant in 2026?",
    "Why Chinese Ba Zi is more detailed than Western astrology",
    "The math behind Chinese fortune telling: it's surprisingly logical",
    "Chinese astrology for beginners: what is Zi Wei Dou Shu?",
    "From Silk Road to API: the journey of Chinese astrology",
    "Five elements explained: wood, fire, earth, metal, water in your life",
    "Chinese fortune vs Western tarot: which one should you trust?",
    "Why Chinese emperors relied on Zi Wei Dou Shu for decisions",

    # ── Practical life topics (12 topics) ──
    "Money and wealth in Chinese astrology: which palaces to check",
    "Career success by Chinese zodiac: find your lucky industry",
    "Health predictions through your Chinese birth chart",
    "Moving abroad? Check your Qian Yi palace in Chinese astrology",
    "Wedding date selection using Chinese astrology and Ba Zi",
    "Baby name ideas based on Chinese five elements theory",
    "Home Feng Shui tips from your Chinese birth chart",
    "Business partnership compatibility in Chinese zodiac",
    "2026 travel luck by Chinese zodiac sign",
    "Exam success and academic fortune in Chinese astrology",
    "When to start a business: Chinese astrology timing guide",
    "Renovation and moving dates: Chinese calendar wisdom",

    # ── Numerology & calendar topics (8 topics) ──
    "Chinese lunar birthday vs Western birthday: which matters more?",
    "Your Chinese zodiac element: discover your inner nature",
    "Lucky numbers in Chinese astrology by birth chart",
    "2026 Chinese zodiac year of the Horse: predictions and tips",
    "Chinese solar terms and your fortune: 24 seasonal guide",
    "The Chinese Ba Zi clock: how birth hour shapes your destiny",
    "Animal signs in Chinese zodiac: beyond the 12 animals",
    "Chinese fortune calendar: best days for love, work, and money",

    # ── Comparison topics (10 topics) ──
    "Japanese zodiac vs Chinese zodiac: what's the difference?",
    "Indian astrology (Jyotish) vs Chinese Ba Zi: a comparison",
    "Kabbalah vs Chinese five elements: mystical traditions",
    "I Ching vs Chinese astrology: two oracle systems compared",
    "Western numerology vs Chinese Ba Zi: which is more accurate?",
    "Vedic astrology vs Zi Wei Dou Shu: ancient wisdom compared",
    "Celtic tree astrology vs Chinese zodiac: nature's signs",
    "Mayan zodiac vs Chinese zodiac: cross-cultural astrology",
    "Angel numbers vs Chinese lucky numbers: what the universe says",
    "Hindu lunar mansions (Nakshatras) vs Chinese 28 mansions",
]

# ── Slug generation ──
def slugify(text: str) -> str:
    """Convert article title to URL-friendly slug"""
    s = text.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    s = re.sub(r'-+', '-', s)
    return s[:60].strip('-')


def get_article_topic(index: Optional[int] = None) -> str:
    """Rotate through topics. If index is None, use day of year."""
    if index is not None:
        return ARTICLE_TOPICS[index % len(ARTICLE_TOPICS)]
    day_of_year = date.today().timetuple().tm_yday
    return ARTICLE_TOPICS[day_of_year % len(ARTICLE_TOPICS)]


def build_prompt(topic: str) -> list:
    """Build the DeepSeek prompt for English article generation"""
    system_prompt = """You are a passionate Chinese astrology enthusiast who happens to write well. NOT a robot or SEO content mill. Write like a real person sharing something they genuinely find fascinating.

Voice and style:
1. Write like you're telling a friend about something cool you discovered. "You know that feeling when you look at your birth chart and everything clicks? That's what happened to me."
2. Use contractions (don't, can't, it's, you've, I've). Real people talk this way.
3. Vary sentence length. Sometimes a punchy 4-word sentence. Sometimes a longer flowing one. Never robotic uniformity.
4. Include specific, relatable moments: "I remember the first time I saw my Zi Wei chart. I was skeptical. Three minutes later I was texting my mom."
5. Ask rhetorical questions: "Ever wonder why your Western horoscope feels vague sometimes?" "Sound familiar?"
6. Use "you" generously. Directly address the reader's curiosity or skepticism.
7. Share small personal observations: "One thing I've noticed after reading charts for friends..."
8. Avoid ANY of these phrases: "In this article", "we will explore", "this comprehensive guide", "it's essential to", "in conclusion", "dive into", "unlock", "delve", "embark on", "let's dive in", "this powerful tool". These are AI dead giveaways.
9. Minimize lists. One short bullet list max per article. Use prose instead.
10. Each paragraph should feel like a natural thought, not a textbook section. No rigid structure.

Focus: Write directly about Zi Wei Dou Shu and Chinese astrology. Do not use tarot, Western zodiac, or horoscope as a crutch — stay centered on the Chinese tradition. Every article should make the reader feel like they're discovering something real about their heritage.

Target audience: overseas Chinese / second-generation Chinese diaspora who speak English but want to connect with their heritage through Chinese astrology.

CTA: Include a natural recommendation at the end. For dev topics use curl example. Otherwise: "Want to see your own chart? It takes 30 seconds at ziweiapi.site — and it's completely free." Link to /index.html or /shop.html naturally, not in a salesy way.

NEVER mention AI, DeepSeek, machine learning, or GPT.

Disclaimer: Add at bottom: "For entertainment purposes only. Not professional advice."

Output as JSON:
{
  "title": "Article title, 50-80 chars",
  "description": "Meta description, max 155 chars, intriguing not keyword-stuffed",
  "keywords": "SEO keywords, comma separated, max 12",
  "content_html": "Full HTML body content with h2 subheadings, p paragraphs, natural CTA"
}"""

    user_prompt = f"""Write an English article on this topic:

Topic: {topic}

The article should:
- Start with a hook about discovering your Chinese heritage through Zi Wei Dou Shu
- Bridge to Chinese astrology concepts naturally
- Include practical insights a beginner can understand
- End with a CTA linking to /index.html (free chart) or /shop.html (buy API Key)
- Be helpful, not salesy

For developer-oriented topics, include this curl example naturally in the CTA:
curl -X POST https://ziweiapi.site/v1/paipan \\
  -H "Authorization: Bearer zw_your_key" \\
  -H "Content-Type: application/json" \\
  -d '{{"year":1995,"month":8,"day":15,"hour":6,"gender":"male"}}'

For general topics, invite readers to try their free Chinese birth chart at /index.html

Output only valid JSON, no markdown code blocks."""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def call_deepseek(messages: list) -> Optional[dict]:
    """Call DeepSeek API to generate article"""
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "***":
        print("⚠️  DEEPSEEK_API_KEY not set, using mock data")
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
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        return json.loads(content)
    except Exception as e:
        print(f"❌ DeepSeek API call failed: {e}")
        return None


def get_mock_article(topic: str) -> dict:
    """Fallback mock article when API is unavailable"""
    return {
        "title": topic,
        "description": f"Explore the fascinating connection between {topic}. Learn how Chinese astrology offers a unique perspective on fortune and destiny.",
        "keywords": f"Chinese astrology, Ba Zi, Zi Wei Dou Shu, fortune telling, {topic.lower()}",
        "content_html": f"""
<h2>What is {topic.split(':')[0] if ':' in topic else 'Chinese Astrology'}?</h2>
<p>Have you ever wondered if there's more to fortune telling than what you already know? Western systems like tarot and zodiac signs have given us incredible insights for centuries. But there's an ancient Chinese system that takes it even deeper: Zi Wei Dou Shu (Purple Star Astrology).</p>
<p>Unlike Western astrology which uses 12 zodiac signs, Chinese Ba Zi uses your exact birth year, month, day, and hour to calculate a complete destiny chart with 12 palaces and dozens of stars. Think of it as a 3D model of your life, not just a 2D snapshot.</p>

<h2>How It Works</h2>
<p>Your Chinese birth chart is built from two main components: the Heavenly Stems and Earthly Branches of your birth moment. These form four pillars (Ba Zi = Eight Characters) that represent your life's blueprint.</p>
<p>Each pillar reveals different aspects: the year pillar shows your ancestry and early life, the month pillar reveals your career and social life, the day pillar is YOU (your core self), and the hour pillar shows your later years and legacy.</p>

<h2>Try It Yourself</h2>
<p>Ready to see what your Chinese birth chart looks like? It only takes 30 seconds. Enter your birth date and get a complete Zi Wei Dou Shu chart with 12 palaces, 14 main stars, and detailed explanations.</p>
<p>Unlike tarot or horoscopes, this isn't a generalization — your chart is uniquely yours, calculated from your exact birth data.</p>

<div class="cta-section">
<p><strong>🔥 Your Chinese destiny is waiting</strong></p>
<p>👉 <a href="/index.html" style="color:#7b68ee;font-weight:600;">Get your FREE Chinese birth chart →</a> Enter your birth info and see your 12 palaces</p>
<p>👉 <a href="/shop.html" style="color:#f0d060;font-weight:600;">Buy a full reading →</a> Unlock 3000+ words of detailed fortune analysis</p>
</div>"""
    }


def build_html(article: dict, topic: str, published_date: str) -> str:
    """Build the final HTML file with full SEO (JSON-LD, OG, Twitter Card)"""
    slug = slugify(topic)
    canonical_url = f"https://ziweiapi.site/en/{published_date}-{slug}.html"
    today_iso = f"{published_date[:4]}-{published_date[4:6]}-{published_date[6:8]}"

    # JSON-LD
    json_ld = f"""{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{article['title']}",
  "description": "{article.get('description', article['title'])}",
  "datePublished": "{today_iso}",
  "author": {{"@type": "Person", "name": "Ziwei Master"}},
  "publisher": {{"@type": "Organization", "name": "Ziwei API"}},
  "inLanguage": "en"
}}"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{article['title']}</title>
<meta name="description" content="{article.get('description', article['title'])}. Free chart reading with complete interpretation.">
<meta name="keywords" content="{article.get('keywords', topic.lower())}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{canonical_url}">
<link rel="alternate" hreflang="x-default" href="{canonical_url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{article['title'][:80]}">
<meta property="og:description" content="{article.get('description', article['title'])[:150]}">
<meta property="og:url" content="{canonical_url}">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{article['title'][:80]}">
<script type="application/ld+json">{json_ld}</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
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
.article-header h1{{
  font-size:26px;font-weight:900;
  background:linear-gradient(135deg,#e0c8ff,#7b68ee,#4a3aa0);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:1px;line-height:1.4
}}
.article-body{{font-size:15px;color:#c8c0d8;padding:0 4px}}
.article-body h2{{font-size:18px;font-weight:700;color:#c4a0ff;margin:28px 0 12px;padding-bottom:6px;border-bottom:1px solid rgba(123,104,238,.1);letter-spacing:.5px}}
.article-body p{{margin-bottom:16px}}
.article-body a{{color:#7b68ee;text-decoration:none;border-bottom:1px solid rgba(123,104,238,.2);transition:all .2s}}
.article-body a:hover{{color:#a080ff;border-color:#7b68ee}}
.article-body .code-block{{
  background:#0e0e1a;border:1px solid #1e1e3a;border-radius:10px;
  padding:14px;overflow-x:auto;margin:14px 0;
  font-family:'SF Mono','Fira Code','JetBrains Mono',monospace;font-size:12px;line-height:1.7;color:#c8d0e8
}}
.cta-section{{
  margin-top:32px;padding:24px;border-radius:14px;
  background:linear-gradient(135deg,rgba(26,26,46,.93),rgba(16,16,30,.93));
  border:1px solid rgba(123,104,238,.18);text-align:center
}}
.cta-section p{{margin-bottom:10px!important}}
.cta-section .cta-title{{font-size:17px;font-weight:700;color:#e0c8ff;margin-bottom:12px;letter-spacing:1px}}
.cta-section .cta-btn{{
  display:inline-block;padding:10px 28px;margin:4px 6px;border-radius:10px;text-decoration:none;
  font-size:14px;font-weight:600;letter-spacing:.5px;transition:all .3s
}}
.cta-section .cta-btn.primary{{background:linear-gradient(135deg,#7b68ee,#5a4acd);color:#fff;border:none;box-shadow:0 4px 16px rgba(123,104,238,.25)}}
.cta-section .cta-btn.primary:hover{{transform:translateY(-2px);box-shadow:0 6px 24px rgba(123,104,238,.4)}}
.cta-section .cta-btn.secondary{{background:transparent;color:#c4a0ff;border:1px solid rgba(123,104,238,.25)}}
.cta-section .cta-btn.secondary:hover{{border-color:#7b68ee;background:rgba(123,104,238,.08)}}
.subscribe-section{{
  margin-top:28px;padding:28px 24px;border-radius:14px;
  background:linear-gradient(135deg,rgba(26,26,46,.95),rgba(16,16,30,.95));
  border:1px solid rgba(240,208,96,.2);text-align:center
}}
.subscribe-section h3{{font-size:19px;font-weight:700;color:#f0d060;margin-bottom:10px;letter-spacing:1px}}
.subscribe-section p{{font-size:13px;color:#b0a8c8;margin-bottom:18px!important;line-height:1.6}}
.subscribe-section .cta-btn.primary{{background:linear-gradient(135deg,#f0d060,#d4a020);color:#0a0a14;border:none;box-shadow:0 4px 20px rgba(240,208,96,.2)}}
.subscribe-section .cta-btn.primary:hover{{transform:translateY(-2px);box-shadow:0 6px 28px rgba(240,208,96,.3)}}
.footer{{text-align:center;padding:30px 0;color:#3a2a5a;font-size:11px;letter-spacing:.5px;line-height:1.8}}
.footer a{{color:#5a4a7a;text-decoration:none}}
.footer a:hover{{color:#7b68ee}}
@media(max-width:600px){{.article-header h1{{font-size:22px}}.article-body{{font-size:14px}}}}
</style>
</head>
<body>
<div class="container">
  <article>
    <div class="article-header">
      <h1>{article['title']}</h1>
    </div>
    <div class="article-body">
      {article['content_html']}
    </div>
  </article>
  <div class="subscribe-section">
    <h3>Get Your Daily Fortune</h3>
    <p>Subscribe for personalized Zi Wei Dou Shu daily readings delivered to your inbox</p>
    <a href="/index.html#subscribe" class="cta-btn primary">Subscribe Now — $4.9/month</a>
  </div>
  <div class="footer">
    <p>⚠️ For entertainment purposes only. Not professional advice.</p>
    <p>Zi Wei Dou Shu · Chinese Astrology | <a href="/index.html">Free Chart</a> | <a href="/shop.html">Buy API Key</a> | <a href="/api-docs.html?lang=en">API Docs</a> | <a href="/articles/">Articles</a></p>
    <p style="margin-top:6px;font-size:10px">© {datetime.now().year} Ziwei API · All Rights Reserved</p>
  </div>
</div>
</body>
</html>"""


def run(topic_index: Optional[int] = None, output_dir: Optional[str] = None):
    """Main function: generate one English article"""
    if output_dir is None:
        output_dir = str(BASE_DIR / "articles" / "en")

    topic = get_article_topic(topic_index)
    today_str = date.today().strftime("%Y%m%d")
    slug = slugify(topic)

    print(f"📝 Generating English article: {topic}")
    print(f"📅 Date: {today_str}")

    messages = build_prompt(topic)
    result = call_deepseek(messages)

    if result is None:
        print("🔧 Using mock article (API not configured or failed)")
        result = get_mock_article(topic)

    filename = f"{today_str}-{slug}.html"
    filepath = Path(output_dir) / filename

    html = build_html(result, topic, today_str)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(html, encoding="utf-8")

    print(f"✅ Article generated: {filepath}")
    print(f"📌 Title: {result['title']}")
    print(f"🏷️  Keywords: {result.get('keywords', '')}")

    # Regenerate sitemap
    try:
        sitemap_script = Path(__file__).resolve().parent / "generate_sitemap_en.py"
        import subprocess
        subprocess.run(["python3", str(sitemap_script)], cwd=str(BASE_DIR), capture_output=True, timeout=10)
    except Exception as e:
        print(f"⚠️  Sitemap regeneration failed: {e}")

    return filepath


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate English SEO articles for Ziwei API")
    parser.add_argument("--index", type=int, default=None, help="Article topic index")
    parser.add_argument("--output", type=str, default=None, help="Output directory (default: articles/en/)")
    args = parser.parse_args()
    run(topic_index=args.index, output_dir=args.output)
