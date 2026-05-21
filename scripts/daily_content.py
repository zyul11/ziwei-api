#!/usr/bin/env python3
"""
Daily Content Generator — Trending Topics + Short Story
Uses DeepSeek API (or mock data as fallback).
Output: {"trending": [...], "story": "..."}

Usage:
  python3 scripts/daily_content.py                    # zh (default)
  python3 scripts/daily_content.py --lang=en          # English
  python3 scripts/daily_content.py --lang=zh --mock   # force mock data
"""
import json
import os
import random
import re
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List

# ── Paths ──
BASE_DIR = Path(__file__).resolve().parent.parent

# ── Load .env ──
env_path = BASE_DIR / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"

# ── Trending Fallbacks ──

ZH_TRENDING_FALLBACK = [
    {"title": "今日科技热点：AI 大模型新突破", "url": "https://news.example.com/ai-breakthrough"},
    {"title": "财经观察：A股市场走势分析", "url": "https://finance.example.com/a-share"},
    {"title": "健康生活：春季养生小贴士", "url": "https://health.example.com/spring-tips"},
    {"title": "文化娱乐：最新热门电影推荐", "url": "https://entertain.example.com/movies"},
]

EN_TRENDING_FALLBACK = [
    {"title": "Tech: Latest AI Model Breakthrough", "url": "https://news.example.com/ai"},
    {"title": "Markets: Global Stocks Weekly Wrap", "url": "https://finance.example.com/stocks"},
    {"title": "Health: Mindfulness & Meditation Tips", "url": "https://health.example.com/mindfulness"},
    {"title": "Entertainment: Top Movies This Week", "url": "https://entertain.example.com/movies"},
    {"title": "Science: Space Exploration Update", "url": "https://science.example.com/space"},
]

# ── Zodiac energy descriptors for story generation ──
ZODIAC_ENERGIES = [
    "gentle awakening of spring", "steady growth of summer",
    "harvest of autumn", "quiet introspection of winter",
    "new moon of renewal", "full moon of completion",
    "morning light of clarity", "evening glow of reflection",
]


def get_today_energy() -> str:
    """Derive a thematic energy from today's date."""
    day_of_year = date.today().timetuple().tm_yday
    idx = (day_of_year * 7 + 3) % len(ZODIAC_ENERGIES)
    return ZODIAC_ENERGIES[idx]


# ── DeepSeek API ──

def call_deepseek(messages: list, max_tokens: int = 2000) -> Optional[str]:
    """Call DeepSeek API and return raw text content."""
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "***":
        print("⚠️  DEEPSEEK_API_KEY not set, using mock data", file=sys.stderr)
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=0.8,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content.strip()
        # Remove markdown code block wrapping if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        return content
    except Exception as e:
        print(f"❌ DeepSeek API call failed: {e}", file=sys.stderr)
        return None


# ── Trending Topics ──

def get_trending_zh(mock: bool = False) -> List[dict]:
    """Get 3-5 Chinese trending topics."""
    if mock:
        return random.sample(ZH_TRENDING_FALLBACK, min(5, len(ZH_TRENDING_FALLBACK)))

    today_str = date.today().isoformat()
    system_prompt = """你是一个中文资讯聚合助手。请输出今日（{today}）的3-5个中文热搜/热门话题。
每个话题包含 title（中文标题）和 url（用 https://example.com/topic-N 格式的占位链接）。
以JSON数组格式输出：[{{"title": "...", "url": "..."}}]
只输出JSON，不要加markdown标记。""".format(today=today_str)

    user_prompt = f"今天是 {today_str}，请列出今天中文互联网上最热门的话题。"
    raw = call_deepseek([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}])
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            print("⚠️  Failed to parse trending JSON, using fallback", file=sys.stderr)
    return random.sample(ZH_TRENDING_FALLBACK, min(5, len(ZH_TRENDING_FALLBACK)))


def get_trending_en(mock: bool = False) -> List[dict]:
    """Get 3-5 English trending topics."""
    if mock:
        return random.sample(EN_TRENDING_FALLBACK, min(5, len(EN_TRENDING_FALLBACK)))

    today_str = date.today().isoformat()
    system_prompt = """You are a news aggregation assistant. Output 3-5 trending/hot topics for today ({today}).
Each topic has a title (English) and url (placeholder like https://example.com/topic-N).
Output as JSON array: [{{"title": "...", "url": "..."}}]
Output ONLY valid JSON, no markdown.""".format(today=today_str)

    user_prompt = f"Today is {today_str}. List the most trending topics on the internet right now."
    raw = call_deepseek([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}])
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            print("⚠️  Failed to parse trending JSON, using fallback", file=sys.stderr)
    return random.sample(EN_TRENDING_FALLBACK, min(5, len(EN_TRENDING_FALLBACK)))


# ── Daily Story ──

def get_daily_story(lang: str = "zh", mock: bool = False) -> str:
    """Generate a ~150-word story based on today's date/energy."""
    energy = get_today_energy()
    today_str = date.today().isoformat()

    if mock:
        if lang == "zh":
            stories = [
                "春风拂过窗台，一只蝴蝶停在书页上。有人说，蝴蝶记得前世的路。今天的你，或许也在寻找某个熟悉的感受。不必着急，时光会让一切慢慢浮现。",
                "晨光中，老人坐在公园长椅上喂鸽子。孩子们奔跑着放风筝，笑声像银铃般清脆。这就是生活最美好的模样——在简单的日常里，找到属于自己的幸福。",
                "城市的高楼间，夕阳把玻璃幕墙染成金色。程序员小李关上电脑，决定今晚去江边走走。有些答案不在代码里，而在风吹过耳边的声音中。",
            ]
            return random.choice(stories)
        else:
            stories = [
                "The first light of dawn crept through the curtains, carrying the quiet promise of a new beginning. She made tea, watched the steam curl upward, and smiled at the simple beauty of being alive in this moment.",
                "In the corner cafe, an old typewriter sat on a wooden shelf. The barista said it belonged to a poet who wrote here every morning. Today, someone left a single line in the paper tray: 'Tomorrow is just today with hope.'",
                "The garden was waking up. A robin perched on the fence, tilting its head at the gardener. She planted seeds not knowing which would bloom, but trusting the rhythm of the seasons. That's courage, she thought.",
            ]
            return random.choice(stories)

    if lang == "zh":
        system_prompt = f"""你是一个温暖的故事作家。今天是 {today_str}，今日的能量是「{energy}」。
请写一篇约150字的短篇故事，温暖、治愈、有诗意感。故事可以是任何主题，但要扣合今日的能量感。
只输出故事正文，不要加标题、说明或markdown标记。"""
        user_prompt = f"今日能量：「{energy}」。请写一篇小故事。"
    else:
        system_prompt = f"""You are a warm storyteller. Today is {today_str}. Today's energy is: "{energy}".
Write a short story of about 150 words. It should be warm, poetic, and reflective of today's energy.
Output ONLY the story text, no titles, explanations or markdown."""
        user_prompt = f"Today's energy: '{energy}'. Write a short story."

    raw = call_deepseek([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], max_tokens=500)
    if raw:
        # Clean up quotes if JSON-encoded
        if raw.startswith('"') and raw.endswith('"'):
            raw = json.loads(raw)
        return raw

    # Final fallback
    if lang == "zh":
        return "晨光微露，新的一天悄然开始。愿你在这平凡的日子里，发现不平凡的美好。"
    return "A new day dawns quietly. May you find extraordinary beauty in this ordinary day."


# ── Main ──

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate daily trending topics and story")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="Language (zh/en)")
    parser.add_argument("--mock", action="store_true", help="Force mock data")
    args = parser.parse_args()

    trending = get_trending_zh(mock=args.mock) if args.lang == "zh" else get_trending_en(mock=args.mock)
    story = get_daily_story(lang=args.lang, mock=args.mock)

    output = {"trending": trending, "story": story}
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
