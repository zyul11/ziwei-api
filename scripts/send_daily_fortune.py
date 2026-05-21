#!/usr/bin/env python3
"""
每日运势 — 主调度脚本（增强版：多级会员体系 + 每日内容）
用途：cron 每日凌晨执行，为所有活跃订阅用户生成本日运势并推送

用法：
  python3 scripts/send_daily_fortune.py                    # 全量发送
  python3 scripts/send_daily_fortune.py --dry-run           # 模拟，只输出统计
  python3 scripts/send_daily_fortune.py --user-id=1         # 指定用户测试
  python3 scripts/send_daily_fortune.py --date=2026-05-18   # 指定日期

会员等级系统（基于 delivery_count）：
  Tier 1 (1-6天):   运势 + 暖心问候
  Tier 2 (7-13天):   + 热门话题
  Tier 3 (14-29天):  + 每日故事
  Tier 4 (30-99天):  + 月度回顾提示
  Tier 5 (100+天):   + 周年纪念消息

支持中/英双语（zh/en），内容根据用户 lang 字段自动适配。
"""
import json
import os
import sqlite3
import smtplib
import subprocess
import sys
import time
import random
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

# ─── 配置 ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DB = Path("/data/ziwei.db")
DB_PATH = DATA_DB if DATA_DB.exists() else BASE_DIR / "data" / "ziwei.db"
ENGINE_SCRIPT = BASE_DIR / "api" / "daily-fortune.js"
DAILY_CONTENT_SCRIPT = BASE_DIR / "scripts" / "daily_content.py"

# ─── .env 加载 ────────────────────────────────────────────────
def load_env():
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().strip().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "87549153@qq.com")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_NAME_ZH = "紫微斗数每日运势"
FROM_NAME_EN = "Ziwei Daily Fortune"
FROM_EMAIL = SMTP_USER
FREE_TRIAL_DAYS = 3
RENEWAL_REMINDER_DAYS = [3, 1]
SITE_URL = "https://ziweiapi.site"


# ─── 辅助函数 ─────────────────────────────────────────────────
def get_tier_info(delivery_count: int) -> Tuple[int, str, List[str]]:
    """
    Return (tier_number, tier_name_zh, tier_features) based on delivery_count.
    Tier 1 = 1-6, Tier 2 = 7-13, Tier 3 = 14-29, Tier 4 = 30-99, Tier 5 = 100+
    """
    if delivery_count >= 100:
        return (5, "至尊会员 · 周年荣耀", [
            "每日运势", "热门话题", "每日故事", "月度回顾", "周年纪念"
        ])
    elif delivery_count >= 30:
        return (4, "高级会员 · 月度伙伴", [
            "每日运势", "热门话题", "每日故事", "月度回顾"
        ])
    elif delivery_count >= 14:
        return (3, "进阶会员 · 故事时光", [
            "每日运势", "热门话题", "每日故事"
        ])
    elif delivery_count >= 7:
        return (2, "成长会员 · 眼界拓展", [
            "每日运势", "热门话题"
        ])
    else:
        return (1, "初心会员 · 温暖启程", [
            "每日运势"
        ])


def get_tier_info_en(delivery_count: int) -> Tuple[int, str, List[str]]:
    """English version of tier info."""
    if delivery_count >= 100:
        return (5, "Supreme Member · Anniversary", [
            "Daily Fortune", "Trending Topics", "Daily Story", "Monthly Review", "Anniversary"
        ])
    elif delivery_count >= 30:
        return (4, "Premium Member · Monthly", [
            "Daily Fortune", "Trending Topics", "Daily Story", "Monthly Review"
        ])
    elif delivery_count >= 14:
        return (3, "Advanced Member · Stories", [
            "Daily Fortune", "Trending Topics", "Daily Story"
        ])
    elif delivery_count >= 7:
        return (2, "Growing Member · Explore", [
            "Daily Fortune", "Trending Topics"
        ])
    else:
        return (1, "New Member · Welcome", [
            "Daily Fortune"
        ])


def get_score_label(score: int, lang: str = "zh") -> Tuple[str, str, str]:
    """Return (emoji, label, tone_message) based on score."""
    if lang == "zh":
        if score >= 5:
            return ("🌟", "大吉",
                    "今日星光灿烂！你的能量如日中天，大胆去追梦吧！")
        elif score >= 1:
            return ("☀️", "小吉",
                    "运势上扬，阳光正好！每一步都走在幸运的节奏上。")
        elif score >= -3:
            return ("🌤", "平",
                    "平稳是福。今日宜静心观察，积蓄力量，明天会更好。")
        else:
            return ("🌧", "波动",
                    "波动是生活的底色，别担心。最暗的夜才看得见最亮的星。")
    else:
        if score >= 5:
            return ("🌟", "Excellent",
                    "The stars are shining bright! Your energy is at its peak — go chase your dreams!")
        elif score >= 1:
            return ("☀️", "Good",
                    "Fortune is rising! The sun is on your side today.")
        elif score >= -3:
            return ("🌤", "Steady",
                    "Steady is safe. Take it easy today, gather strength for tomorrow.")
        else:
            return ("🌧", "Challenging",
                    "Challenges are the backdrop of life. Don't worry — the darkest night shows the brightest stars.")


def get_encouragement(score: int, lang: str = "zh") -> str:
    """Get a warm encouragement or celebration message based on score."""
    if lang == "zh":
        if score >= 5:
            return random.choice([
                "🎉 太棒了！今天的你简直在发光！",
                "✨ 运势满分，去做那个闪闪发光的自己！",
                "🌈 今日大吉！世界都在为你让路。",
            ])
        elif score >= 1:
            return random.choice([
                "🌻 好运正在路上，保持微笑哦～",
                "🍀 今日小确幸，请查收！",
                "🌸 运势不错，适合勇敢一点点。",
            ])
        elif score >= -3:
            return random.choice([
                "🍵 不着急，慢慢来。平静也是力量。",
                "📖 今日宜读书、听歌、发呆。",
                "🌿 低开高走，下午可能会更好哦。",
            ])
        else:
            return random.choice([
                "💪 低谷是上坡路的开始，加油！",
                "🌙 今晚好好休息，明天会是全新的一天。",
                "🤗 抱抱你，风雨过后必有彩虹。",
            ])
    else:
        if score >= 5:
            return random.choice([
                "🎉 Amazing! You're absolutely glowing today!",
                "✨ Perfect score! Go be the shining star you are!",
                "🌈 Excellent day! The world is making way for you!",
            ])
        elif score >= 1:
            return random.choice([
                "🌻 Good fortune is on its way — keep smiling!",
                "🍀 Today's little blessing, delivered!",
                "🌸 A good day to be a little brave.",
            ])
        elif score >= -3:
            return random.choice([
                "🍵 No rush. Take it slow. Peace is also power.",
                "📖 A good day for reading, music, and daydreaming.",
                "🌿 A slow start, but the afternoon may surprise you.",
            ])
        else:
            return random.choice([
                "💪 A low valley is just the start of a climb — keep going!",
                "🌙 Rest well tonight. Tomorrow is a brand new day.",
                "🤗 Sending you a warm hug. After rain comes rainbow.",
            ])


def get_warm_greeting(user_name: str, day_ganzhi: str, lang: str = "zh") -> str:
    """Generate a warm greeting for the email opening."""
    today = date.today()
    if lang == "zh":
        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        wd = weekday_names[today.weekday()]
        return (
            f"亲爱的{user_name or '命主'}，早安。\n"
            f"今日是{today.isoformat()}，星期{wd}，干支为「{day_ganzhi}」。\n"
            f"新的一天，新的能量。紫微斗数为您解读今日运势，愿您知命而运，日日向上。"
        )
    else:
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        wd = weekday_names[today.weekday()]
        return (
            f"Dear {user_name or 'Seeker'}, good morning.\n"
            f"Today is {today.isoformat()}, {wd}. The celestial stem is 「{day_ganzhi}」.\n"
            f"A new day brings new energy. Ziwei Dou Shu illuminates your path — know your destiny, shape your fortune."
        )


# ─── 数据库 ───────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_active_subscriptions():
    """获取所有活跃订阅（含免费试用），现在包含 lang 字段"""
    conn = get_db()
    today = date.today().isoformat()
    rows = conn.execute("""
        SELECT u.id, u.email, u.name, u.birth_year, u.birth_month,
               u.birth_day, u.birth_hour, u.gender, u.city, u.timezone,
               s.plan, s.status, s.start_date, s.end_date,
               s.lang, s.delivery_count, s.tier
        FROM users u
        JOIN subscriptions s ON s.user_id = u.id
        WHERE s.status IN ('active', 'trial')
          AND s.end_date >= ?
          AND u.is_active = 1
    """, (today,)).fetchall()
    conn.close()
    return rows


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row


def get_subscription_by_user_id(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM subscriptions WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    return row


def increment_delivery_count(user_id):
    """Increment delivery_count and recalculate tier for a user."""
    conn = get_db()
    conn.execute("""
        UPDATE subscriptions
        SET delivery_count = COALESCE(delivery_count, 0) + 1
        WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    # Fetch new count and update tier
    row = conn.execute(
        "SELECT delivery_count FROM subscriptions WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    if row:
        dc = row['delivery_count']
        if dc >= 100:
            new_tier = 5
        elif dc >= 30:
            new_tier = 4
        elif dc >= 14:
            new_tier = 3
        elif dc >= 7:
            new_tier = 2
        else:
            new_tier = 1
        conn.execute(
            "UPDATE subscriptions SET tier = ? WHERE user_id = ?",
            (new_tier, user_id)
        )
        conn.commit()
    conn.close()
    return row['delivery_count'] if row else 1


def save_daily_fortune(user_id, date_str, day_ganzhi, score, lucky, caution, detail_json, sent=False):
    conn = get_db()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO daily_fortune_logs
            (user_id, date, day_ganzhi, overall_score, lucky_palaces, caution_palaces, detail_json, sent_via_email, sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, date_str, day_ganzhi, score,
            json.dumps(lucky, ensure_ascii=False),
            json.dumps(caution, ensure_ascii=False),
            json.dumps(detail_json, ensure_ascii=False, indent=2),
            1 if sent else 0,
            datetime.now().isoformat() if sent else None
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.execute("""
            UPDATE daily_fortune_logs
            SET day_ganzhi=?, overall_score=?, lucky_palaces=?, caution_palaces=?,
                detail_json=?, sent_via_email=?, sent_at=?
            WHERE user_id=? AND date=?
        """, (day_ganzhi, score,
              json.dumps(lucky, ensure_ascii=False),
              json.dumps(caution, ensure_ascii=False),
              json.dumps(detail_json, ensure_ascii=False, indent=2),
              1 if sent else 0, datetime.now().isoformat() if sent else None,
              user_id, date_str))
        conn.commit()
    finally:
        conn.close()


def check_fortune_sent(user_id, date_str):
    conn = get_db()
    row = conn.execute(
        "SELECT sent_via_email FROM daily_fortune_logs WHERE user_id=? AND date=?",
        (user_id, date_str)
    ).fetchone()
    conn.close()
    return row and row['sent_via_email']


def get_users_needing_renewal_reminder():
    conn = get_db()
    today = date.today()
    reminders = []
    for days_before in RENEWAL_REMINDER_DAYS:
        target_date = (today + timedelta(days=days_before)).isoformat()
        rows = conn.execute("""
            SELECT u.id, u.email, u.name, s.plan, s.end_date, s.lang
            FROM users u
            JOIN subscriptions s ON s.user_id = u.id
            WHERE s.end_date = ?
              AND s.status = 'active'
        """, (target_date,)).fetchall()
        for r in rows:
            reminders.append((dict(r), days_before))
    conn.close()
    return reminders


# ─── 每日内容（话题 + 故事）───────────────────────────────────
def get_daily_content(lang: str = "zh") -> Optional[Dict[str, Any]]:
    """Call daily_content.py to get trending topics and story."""
    try:
        result = subprocess.run(
            ["python3", str(DAILY_CONTENT_SCRIPT), f"--lang={lang}"],
            capture_output=True, text=True, timeout=30,
            cwd=str(BASE_DIR)
        )
        if result.returncode != 0:
            print(f"  ⚠️  daily_content.py error: {result.stderr.strip()}", file=sys.stderr)
            return None
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        print(f"  ⚠️  daily_content.py timeout", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ⚠️  daily_content.py exception: {e}", file=sys.stderr)
        return None


# ─── 邮件发送 ─────────────────────────────────────────────────
def check_email_config():
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.quit()
        return True
    except Exception as e:
        print(f"⚠️ Email config failed: {e}")
        return False


def send_email(to_email, subject, html_body, text_body=""):
    msg = MIMEMultipart('alternative')
    display_name = str(Header(FROM_NAME_ZH, 'utf-8'))
    msg['From'] = formataddr((display_name, FROM_EMAIL))
    msg['To'] = to_email
    msg['Subject'] = subject
    msg['Reply-To'] = FROM_EMAIL
    msg['List-Unsubscribe'] = f'<{SITE_URL}/unsubscribe.html>'

    if text_body:
        msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"  ❌ Email failed to {to_email}: {e}")
        return False


# ─── 运势计算 ─────────────────────────────────────────────────
def calc_fortune(birth, target_date=None):
    payload = {"birth": birth}
    if target_date:
        payload["targetDate"] = target_date

    try:
        result = subprocess.run(
            ["node", str(ENGINE_SCRIPT)],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True, text=True, timeout=30,
            cwd=str(BASE_DIR)
        )
        if result.returncode != 0:
            print(f"  ❌ Engine error: {result.stderr.strip()}")
            return None
        data = json.loads(result.stdout)
        if not data.get('daily'):
            print(f"  ❌ No daily data in engine output")
            return None
        return data
    except subprocess.TimeoutExpired:
        print(f"  ❌ Engine timeout")
        return None
    except Exception as e:
        print(f"  ❌ Engine exception: {e}")
        return None


# ─── 邮件模板 ─────────────────────────────────────────────────
def build_fortune_email(
    user_name: str,
    fortune_result: dict,
    plan: str = "trial",
    lang: str = "zh",
    delivery_count: int = 1,
    daily_content: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
) -> Tuple[str, str]:
    """
    构建运势邮件（HTML + 纯文本），支持多级会员体系。
    根据 delivery_count 决定展示内容的多寡。
    """
    daily = fortune_result.get('daily', {})
    text = fortune_result.get('text', {})

    day_ganzhi = daily.get('dayGanZhi', '未知')
    overall = text.get('overall', '')
    score = daily.get('overallScore', 0)
    lucky = text.get('luckyAreas', [])
    caution = text.get('cautionAreas', [])
    lucky_color = text.get('luckyColor', '#7C3AED')
    lucky_numbers = text.get('luckyNumbers', [1, 5, 9])
    details = text.get('details', [])
    tip = text.get('tip', '')

    # Tier info
    if lang == "en":
        tier_num, tier_name, tier_features = get_tier_info_en(delivery_count)
    else:
        tier_num, tier_name, tier_features = get_tier_info(delivery_count)

    # Score label and encouragement
    score_emoji, score_label, score_message = get_score_label(score, lang)
    encouragement = get_encouragement(score, lang)
    greeting = get_warm_greeting(user_name, day_ganzhi, lang)

    # Trending + story from daily content
    trending = daily_content.get('trending', []) if daily_content else []
    story = daily_content.get('story', '') if daily_content else ''

    # Build tier progression badges
    all_tier_names = [
        ("1", "初心启程" if lang == "zh" else "New Start"),
        ("2", "眼界拓展" if lang == "zh" else "Explore"),
        ("3", "故事时光" if lang == "zh" else "Stories"),
        ("4", "月度伙伴" if lang == "zh" else "Monthly"),
        ("5", "至尊荣耀" if lang == "zh" else "Supreme"),
    ]
    tier_badges_html = ""
    for i, (tnum, tname) in enumerate(all_tier_names, 1):
        active = i <= tier_num
        tier_badges_html += f"""
        <span style="display:inline-flex;align-items:center;margin:0 4px 4px 0;
            padding:4px 10px;border-radius:999px;font-size:11px;font-weight:bold;
            background:{'#7c3aed' if active else '#1a1630'};
            color:{'#fff' if active else '#6a5a8a'};
            border:1px solid {'#7c3aed' if active else '#2a2040'}">
            {'⭐' if active else '○'} T{tnum} {tname}
        </span>"""

    # Trending HTML
    trending_html = ""
    if tier_num >= 2 and trending:
        trending_items = ""
        for t in trending[:5]:
            title = t.get('title', '')
            url = t.get('url', '#')
            trending_items += f"""
            <tr>
                <td style="padding:8px 12px;border-bottom:1px solid #2a2040;font-size:13px">
                    <a href="{url}" style="color:#c4b5d0;text-decoration:none" target="_blank">🔥 {title}</a>
                </td>
            </tr>"""
        trending_html = f"""
        <tr><td style="padding:0 24px 16px">
            <div style="background:#1a1630;border-radius:12px;padding:12px">
                <div style="color:#a78bfa;font-size:13px;font-weight:bold;margin-bottom:8px">
                    📈 {'今日热门话题' if lang == 'zh' else "Today's Trending Topics"}
                </div>
                <table width="100%" style="border-collapse:collapse">
                    {trending_items}
                </table>
            </div>
        </td></tr>"""

    # Story HTML
    story_html = ""
    if tier_num >= 3 and story:
        story_html = f"""
        <tr><td style="padding:0 24px 16px">
            <div style="padding:14px 16px;background:linear-gradient(135deg,#1a1a3a,#12101e);border-radius:12px;border-left:3px solid #f59e0b">
                <div style="color:#fbbf24;font-size:13px;font-weight:bold;margin-bottom:6px">
                    📖 {'今日故事' if lang == 'zh' else "Today's Story"}
                </div>
                <div style="color:#d0c8e0;font-size:13px;line-height:1.7;font-style:italic">
                    {story}
                </div>
            </div>
        </td></tr>"""

    # Monthly review hint (Tier 4+)
    monthly_html = ""
    if tier_num >= 4:
        monthly_html = f"""
        <tr><td style="padding:0 24px 8px">
            <div style="padding:10px 14px;background:#1a1a2a;border-radius:10px;text-align:center">
                <span style="color:#a78bfa;font-size:12px">
                    📊 {'月度运势回顾即将生成，敬请期待！' if lang == 'zh' else 'Monthly fortune review coming soon — stay tuned!'}
                </span>
            </div>
        </td></tr>"""

    # ── Share Card ──
    share_html = f"""<tr><td style="padding:0 24px 16px">
        <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#1a1a30,#0f0a1e);border-radius:14px;border:1px solid rgba(167,139,250,.12);overflow:hidden">
            <tr><td style="padding:4px 14px 10px;text-align:center">
                <div style="color:#6a5a8a;font-size:9px;letter-spacing:1px;margin-bottom:4px">{'📸 截图分享到朋友圈' if lang == 'zh' else '📸 Screenshot & share with friends'}</div>
                <div style="font-size:11px;color:#8a7a9a">{day_ganzhi}{'日' if lang == 'zh' else ''} · {score_label} · {score_emoji}</div>
                <div style="font-size:22px;font-weight:bold;color:#d0c8e0;margin:4px 0">{'紫微斗数 · 每日命盘' if lang == 'zh' else 'Ziwei · Daily Fortune'}</div>
                <div style="font-size:10px;color:#6a5a8a;line-height:1.5">{overall[:80]}{'…' if len(overall) > 80 else ''}</div>
                <div style="margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,.04);font-size:9px;color:#4a3a5a">
                    {'访问' if lang == 'zh' else 'Visit'} <span style="color:#7c3aed">ziweiapi.site</span> {'获取完整运势' if lang == 'zh' else 'for daily fortune'}
                </div>
            </td></tr>
        </table>
    </td></tr>"""

    # ── Referral Link ──
    ref_url = f"{SITE_URL}/?ref={user_id}" if user_id else f"{SITE_URL}"
    referral_html = f"""<tr><td style="padding:0 24px 16px">
        <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#2a1a2a,#1a0e1e);border-radius:12px;border:1px solid rgba(251,191,36,.12)">
            <tr><td style="padding:12px 16px;text-align:center">
                <div style="color:#fbbf24;font-size:13px;font-weight:bold;margin-bottom:4px">
                    {'🌟 邀请好友，双方各得 3 天免费' if lang == 'zh' else '🌟 Invite a friend — you both get 3 free days'}
                </div>
                <div style="color:#8a7a9a;font-size:10px;line-height:1.5;margin-bottom:8px">
                    {'分享你的专属邀请链接，好友订阅后你和好友各延长 3 天！' if lang == 'zh' else 'Share your invite link. When a friend subscribes, you both get +3 days!'}
                </div>
                <div style="background:#0f0a1e;border-radius:8px;padding:8px 14px;display:inline-block;max-width:100%;word-break:break-all">
                    <a href="{ref_url}" style="color:#fbbf24;font-size:11px;font-weight:bold;text-decoration:none">{ref_url}</a>
                </div>
                <div style="color:#6a5a8a;font-size:9px;margin-top:6px">
                    {'🔗 点击上方链接或复制分享给好友' if lang == 'zh' else '🔗 Click or copy the link above to share'}
                </div>
            </td></tr>
        </table>
    </td></tr>"""

    # ── Anniversary message (Tier 5) ──
    anniversary_html = ""
    if tier_num >= 5:
        anniversary_html = f"""
        <tr><td style="padding:0 24px 16px">
            <div style="padding:14px 16px;background:linear-gradient(135deg,#2a1a3a,#1a1030);border-radius:12px;border:1px solid #a78bfa;text-align:center">
                <div style="font-size:24px;margin-bottom:4px">🎂</div>
                <div style="color:#fbbf24;font-size:14px;font-weight:bold">
                    {'🎉 感谢你一路相伴超过100天！' if lang == 'zh' else '🎉 Thank you for being with us for over 100 days!'}
                </div>
                <div style="color:#c4b5d0;font-size:12px;margin-top:4px">
                    {'你是我们最珍贵的会员，愿未来的每一天都星光璀璨。' if lang == 'zh' else 'You are our most cherished member. May every day ahead shine bright.'}
                </div>
            </div>
        </td></tr>"""

    # Details HTML
    details_html = ""
    for d in details:
        emoji_map = {
            '自我状态': '🧘', '人际关系': '🤝', '感情婚姻': '💕',
            '子女/创意': '🎨', '财运投资': '💰', '身体健康': '🏃',
            '出行际遇': '🚗', '社交人脉': '👥', '事业发展': '💼',
            '家庭房产': '🏠', '精神心灵': '🧠', '长辈贵人': '👴',
        }
        emoji = emoji_map.get(d.get('领域', ''), '📌')
        score_sign = "+" if d.get('评分', 0) > 0 else ""
        details_html += f"""
        <tr>
            <td style="padding:10px 16px;border-bottom:1px solid #2a2040;vertical-align:top;white-space:nowrap">
                <span style="font-size:18px">{emoji}</span>
                <span style="color:#c4b5d0;font-size:13px">{d.get('领域','')}</span>
            </td>
            <td style="padding:10px 16px;border-bottom:1px solid #2a2040;font-size:13px;color:#d0c8e0">
                {d.get('详解','')}
            </td>
            <td style="padding:10px 16px;border-bottom:1px solid #2a2040;text-align:center;font-weight:bold;font-size:15px">
                <span style="color:{'#4ade80' if d.get('评分',0) >= 0 else '#f87171'}">
                    {score_sign}{d.get('评分',0)}
                </span>
            </td>
        </tr>"""

    # Lucky/caution HTML
    lucky_html = ''.join(
        f'<span style="display:inline-block;background:#1a3a2a;color:#4ade80;padding:4px 12px;border-radius:12px;font-size:12px;margin:3px">{a}</span>'
        for a in lucky
    )
    caution_html = ''.join(
        f'<span style="display:inline-block;background:#3a1a1a;color:#f87171;padding:4px 12px;border-radius:12px;font-size:12px;margin:3px">{a}</span>'
        for a in caution
    )

    # Display count message
    count_label = f"{'第' if lang == 'zh' else 'Day'} {delivery_count}{'天' if lang == 'zh' else ''}"

    # Quotes
    zh_quotes = [
        "谋事在人，成事在天。今天的每一步都在为明天铺路。",
        "吉凶本是同源，在好日子里播种，在坏日子里扎根。",
        "化忌不可怕，可怕的是不知道哪里化忌。知道了，就是保护。",
        "紫微斗数不是宿命，是导航。今天你看清了路况。",
        "每一天都是新的开始，昨日已去，明日未至，唯有当下最珍贵。",
    ]
    en_quotes = [
        "Plan with the mind, trust with the heart. Every step today paves tomorrow's path.",
        "Fortune and challenge spring from the same source. Sow in good times, root in hard times.",
        "The stars don't dictate your fate — they illuminate your choices.",
        "Ziwei Dou Shu is not destiny, it's navigation. Today you see the road clearly.",
        "Every day is a fresh start. Yesterday is gone, tomorrow not yet here — cherish the now.",
    ]
    quotes = zh_quotes if lang == "zh" else en_quotes
    quote = random.choice(quotes)

    # Email subject
    if lang == "zh":
        subject = f"📜 {daily.get('date','')} 每日命盘 — {day_ganzhi}日 · {score_label}"
    else:
        subject = f"📜 {daily.get('date','')} Daily Fortune — {day_ganzhi} · {score_label}"

    # ── HTML构建 ──
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0a0a14;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:20px 10px">
<table width="560" cellpadding="0" cellspacing="0" style="background:#12101e;border-radius:16px;overflow:hidden">

<!-- Header -->
<tr><td style="padding:32px 24px 20px;text-align:center;background:linear-gradient(135deg,#1a1030,#0f0a1e)">
    <div style="font-size:40px;margin-bottom:8px">{score_emoji}</div>
    <div style="color:#a78bfa;font-size:13px;letter-spacing:2px">{'紫微斗数 · 每日命盘解析' if lang == 'zh' else 'Ziwei Dou Shu · Daily Chart Analysis'}</div>
    <div style="color:#d0c8e0;font-size:26px;font-weight:bold;margin:12px 0 4px">
        {day_ganzhi}{'日' if lang == 'zh' else ''} · {score_label}
    </div>
    <div style="color:#8a7a9a;font-size:12px">{daily.get('date','')} | {count_label}</div>
</td></tr>

<!-- Tier Badges -->
<tr><td style="padding:4px 24px 12px;text-align:center">
    <div style="color:#8a7a9a;font-size:10px;margin-bottom:4px">
        {'会员等级' if lang == 'zh' else 'Membership Tier'}
    </div>
    <div style="text-align:center">
        {tier_badges_html}
    </div>
</td></tr>

<!-- Greeting -->
<tr><td style="padding:8px 24px 8px">
    <div style="color:#c4b5d0;font-size:14px;line-height:1.7">
        {user_name or ('命主' if lang == 'zh' else 'Seeker')}，{'你好' if lang == 'zh' else 'hello'}.<br>
        <span style="display:block;color:#7c6a9a;font-size:11px;margin:4px 0 8px;font-style:italic">
            {'── 知命而运，日日向上 ──' if lang == 'zh' else '── Know your fate, shape your fortune ──'}
        </span>
        <span style="color:#a78bfa">{overall}</span>
    </div>
</td></tr>

<!-- Encouragement -->
<tr><td style="padding:0 24px 12px">
    <div style="padding:10px 14px;background:#1a1630;border-radius:10px;text-align:center">
        <span style="color:#fbbf24;font-size:15px">{encouragement}</span>
    </div>
</td></tr>

<!-- Score -->
<tr><td style="padding:0 24px 16px">
    <table width="100%">
    <tr>
        <td style="padding:12px;background:#1a1630;border-radius:12px;text-align:center">
            <div style="color:#8a7a9a;font-size:11px">{'今日总评分' if lang == 'zh' else 'Today Score'}</div>
            <div style="color:#d0c8e0;font-size:32px;font-weight:bold;margin:4px 0">{score}</div>
            <div style="color:#8a7a9a;font-size:11px">{'正=吉 / 负=忌' if lang == 'zh' else 'Positive=Good / Negative=Caution'}</div>
        </td>
        <td width="12"></td>
        <td style="padding:12px;background:#1a1630;border-radius:12px;text-align:center">
            <div style="color:#8a7a9a;font-size:11px">{'幸运数字' if lang == 'zh' else 'Lucky Numbers'}</div>
            <div style="color:#a78bfa;font-size:26px;font-weight:bold;margin:4px 0">
                {', '.join(map(str, lucky_numbers))}
            </div>
        </td>
        <td width="12"></td>
        <td style="padding:12px;background:#1a1630;border-radius:12px;text-align:center">
            <div style="color:#8a7a9a;font-size:11px">{'幸运色' if lang == 'zh' else 'Lucky Color'}</div>
            <div style="margin:8px auto;width:36px;height:36px;border-radius:50%;background:{lucky_color};border:2px solid rgba(255,255,255,0.1)"></div>
        </td>
    </tr>
    </table>
</td></tr>

<!-- Lucky/Caution -->
<tr><td style="padding:0 24px 16px">
    <table width="100%">
    <tr>
        <td style="vertical-align:top;padding:12px;background:#0d2a1a;border-radius:12px">
            <div style="color:#4ade80;font-size:12px;font-weight:bold;margin-bottom:8px">{'✅ 宜' if lang == 'zh' else '✅ Good'}</div>
            {lucky_html if lucky_html else '<span style="color:#8a7a9a;font-size:12px">' + ('无特别' if lang == 'zh' else 'None') + '</span>'}
        </td>
        <td width="12"></td>
        <td style="vertical-align:top;padding:12px;background:#2a1010;border-radius:12px">
            <div style="color:#f87171;font-size:12px;font-weight:bold;margin-bottom:8px">{'⚠️ 忌' if lang == 'zh' else '⚠️ Caution'}</div>
            {caution_html if caution_html else '<span style="color:#8a7a9a;font-size:12px">' + ('无特别' if lang == 'zh' else 'None') + '</span>'}
        </td>
    </tr>
    </table>
</td></tr>

<!-- Details -->
<tr><td style="padding:0 24px 16px">
    <div style="color:#a78bfa;font-size:13px;font-weight:bold;margin-bottom:10px">
        {'📋 宫位详解' if lang == 'zh' else '📋 Palace Details'}
    </div>
    <table width="100%" style="border-collapse:collapse">
        <tr style="background:#1a1630">
            <th style="padding:8px 16px;text-align:left;color:#8a7a9a;font-size:11px;border-bottom:1px solid #2a2040">{'领域' if lang == 'zh' else 'Area'}</th>
            <th style="padding:8px 16px;text-align:left;color:#8a7a9a;font-size:11px;border-bottom:1px solid #2a2040">{'解析' if lang == 'zh' else 'Analysis'}</th>
            <th style="padding:8px 16px;text-align:center;color:#8a7a9a;font-size:11px;border-bottom:1px solid #2a2040">{'势' if lang == 'zh' else 'Score'}</th>
        </tr>
        {details_html if details_html else '<tr><td colspan="3" style="padding:16px;text-align:center;color:#8a7a9a;font-size:13px">' + ('今日无特别宫位引动，一切平稳。' if lang == 'zh' else 'No special palace activations today. Everything is steady.') + '</td></tr>'}
    </table>
</td></tr>

<!-- Tip -->
<tr><td style="padding:0 24px 16px">
    <div style="padding:12px 16px;background:linear-gradient(135deg,#2a1a4a,#1a1030);border-radius:12px;border-left:3px solid #a78bfa">
        <div style="color:#c4b5d0;font-size:13px;line-height:1.6">{tip}</div>
    </div>
</td></tr>

<!-- Trending (Tier 2+) -->
{trending_html}

<!-- Story (Tier 3+) -->
{story_html}

<!-- Monthly (Tier 4+) -->
{monthly_html}

<!-- Share Card -->
{share_html}

<!-- Referral Link -->
{referral_html}

<!-- Anniversary (Tier 5+) -->
{anniversary_html}

<!-- Footer -->
<tr><td style="padding:20px 24px;text-align:center;background:#0f0a1e;border-top:1px solid #1a1630">
    <div style="color:#6a5a8a;font-size:11px;line-height:1.7">
        <p style="margin:0 0 8px;font-style:italic;color:#8a7a9a">「{quote}」</p>
        <p style="margin:8px 0 0">
            {'🌟 尊享版' if plan not in ('trial', 'weekly') else '📬 每日运势'}
            | {tier_name} | {count_label}
        </p>
        <p style="margin:4px 0 0">
            <a href="{SITE_URL}/subscribe.html" style="color:#7c3aed;text-decoration:none">{'管理订阅' if lang == 'zh' else 'Manage Subscription'}</a>
            <span style="color:#3a2a5a"> · </span>
            <a href="{SITE_URL}/unsubscribe.html" style="color:#6a5a8a;text-decoration:none">{'取消订阅' if lang == 'zh' else 'Unsubscribe'}</a>
        </p>
        <p style="margin:8px 0 0;color:#4a3a5a">{'每日命盘 · 紫微斗数' if lang == 'zh' else 'Daily Chart · Ziwei Dou Shu'}</p>
    </div>
</td></tr>

</table>
</td></tr></table>
</body></html>"""

    # ── Plain Text ──
    text_body_parts = []
    if lang == "zh":
        text_body_parts.append(f"=== 紫微斗数 每日运势 ===\n日期: {daily.get('date','')} · {day_ganzhi}\n")
    else:
        text_body_parts.append(f"=== Ziwei Daily Fortune ===\nDate: {daily.get('date','')} · {day_ganzhi}\n")

    text_body_parts.append(greeting)
    text_body_parts.append(f"\n{encouragement}")
    text_body_parts.append(f"\n{score_message}")
    text_body_parts.append(f"\n{'总评分' if lang == 'zh' else 'Score'}: {score}")
    text_body_parts.append(f"{'宜' if lang == 'zh' else 'Good'}: {', '.join(lucky) if lucky else '—'}")
    text_body_parts.append(f"{'忌' if lang == 'zh' else 'Caution'}: {', '.join(caution) if caution else '—'}")
    text_body_parts.append(f"{'幸运色' if lang == 'zh' else 'Lucky Color'}: {lucky_color}")
    text_body_parts.append(f"{'幸运数字' if lang == 'zh' else 'Lucky Numbers'}: {', '.join(map(str, lucky_numbers))}")
    text_body_parts.append(f"\n{'--- 宫位详解 ---' if lang == 'zh' else '--- Palace Details ---'}")
    for d in details:
        score_sign = "+" if d.get('评分', 0) > 0 else ""
        text_body_parts.append(f"{d.get('领域','')} [{score_sign}{d.get('评分',0)}]: {d.get('详解','')}")

    text_body_parts.append(f"\n{tip}")

    if trending:
        text_body_parts.append(f"\n{'--- 热门话题 ---' if lang == 'zh' else '--- Trending Topics ---'}")
        for t in trending[:5]:
            text_body_parts.append(f"🔥 {t.get('title','')}")

    if story:
        text_body_parts.append(f"\n{'--- 每日故事 ---' if lang == 'zh' else '--- Today Story ---'}")
        text_body_parts.append(story)

    text_body_parts.append(f"\n{'会员等级' if lang == 'zh' else 'Tier'}: {tier_name}")
    text_body_parts.append(f"{'今日是第' if lang == 'zh' else 'Day'} {delivery_count}{'天' if lang == 'zh' else ''}")
    text_body_parts.append(f"\n{'管理订阅' if lang == 'zh' else 'Manage'}: {SITE_URL}/subscribe.html")
    text_body_parts.append(f"{'取消订阅' if lang == 'zh' else 'Unsubscribe'}: {SITE_URL}/unsubscribe.html")
    text_body_parts.append(f"\n{'🌟 邀请好友，双方各得 3 天' if lang == 'zh' else '🌟 Invite a friend, get +3 days'}: {ref_url}")
    text_body_parts.append(f"\n{'分享这张运势截图到朋友圈，让好运传递 ✨' if lang == 'zh' else 'Share this fortune screenshot with friends ✨'}")

    text_body = "\n".join(text_body_parts)
    return html, text_body, subject


def build_renewal_email(user_name, plan, end_date, days_left, lang="zh"):
    """续费提醒邮件，支持双语"""
    if lang == "zh":
        plan_names = {'weekly': '周卡', 'monthly': '月卡', 'quarterly': '季卡', 'yearly': '年卡'}
        plan_cn = plan_names.get(plan, plan)
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0a0a14;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:20px 10px">
<table width="520" cellpadding="0" cellspacing="0" style="background:#12101e;border-radius:16px;overflow:hidden">
<tr><td style="padding:32px 24px;text-align:center;background:linear-gradient(135deg,#2a1a4a,#1a1030)">
    <div style="font-size:36px;margin-bottom:8px">⏰</div>
    <div style="color:#a78bfa;font-size:18px;font-weight:bold">订阅即将到期</div>
</td></tr>
<tr><td style="padding:24px">
    <div style="color:#c4b5d0;font-size:15px;line-height:1.7">
        {user_name or '命主'}，您好。<br><br>
        您的 <strong style="color:#a78bfa">{plan_cn}</strong> 将于 <strong style="color:#f87171">{end_date}</strong> 到期（剩余 {days_left} 天）。<br><br>
        续费后可继续享受每日运势推送{' + 热门话题 + 每日故事' if days_left >= 7 else ''}，不间断。
    </div>
    <div style="text-align:center;margin:24px 0">
        <a href="{SITE_URL}/subscribe.html" style="display:inline-block;padding:12px 32px;background:linear-gradient(135deg,#7c3aed,#5b21b6);color:#fff;border-radius:999px;text-decoration:none;font-size:15px;font-weight:bold">立即续费</a>
    </div>
    <div style="color:#8a7a9a;font-size:12px;text-align:center;margin-top:12px">
        💡 续费后会员等级和天数将继续累积，不会重置哦！
    </div>
</td></tr>
<tr><td style="padding:16px 24px;text-align:center;background:#0f0a1e;border-top:1px solid #1a1630">
    <div style="color:#6a5a8a;font-size:11px">若已续费请忽略此邮件</div>
</td></tr>
</table>
</td></tr></table>
</body></html>"""

        text_body = f"""⏰ 订阅即将到期

{user_name or '命主'}，您好。

您的 {plan_cn} 将于 {end_date} 到期（剩余 {days_left} 天）。

续费后可继续享受每日运势推送，不间断。
💡 续费后会员等级和天数将继续累积！

续费链接: {SITE_URL}/subscribe.html

若已续费请忽略此邮件。"""
        subject = f"⏰ 订阅即将到期（{days_left}天后）"
    else:
        plan_names = {'weekly': 'Weekly', 'monthly': 'Monthly', 'quarterly': 'Quarterly', 'yearly': 'Yearly'}
        plan_en = plan_names.get(plan, plan)
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0a0a14;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:20px 10px">
<table width="520" cellpadding="0" cellspacing="0" style="background:#12101e;border-radius:16px;overflow:hidden">
<tr><td style="padding:32px 24px;text-align:center;background:linear-gradient(135deg,#2a1a4a,#1a1030)">
    <div style="font-size:36px;margin-bottom:8px">⏰</div>
    <div style="color:#a78bfa;font-size:18px;font-weight:bold">Subscription Expiring Soon</div>
</td></tr>
<tr><td style="padding:24px">
    <div style="color:#c4b5d0;font-size:15px;line-height:1.7">
        Dear {user_name or 'Seeker'},<br><br>
        Your <strong style="color:#a78bfa">{plan_en}</strong> plan will expire on <strong style="color:#f87171">{end_date}</strong> ({days_left} days left).<br><br>
        Renew now to keep receiving daily fortune readings{' + trending topics + stories' if days_left >= 7 else ''}.
    </div>
    <div style="text-align:center;margin:24px 0">
        <a href="{SITE_URL}/subscribe.html" style="display:inline-block;padding:12px 32px;background:linear-gradient(135deg,#7c3aed,#5b21b6);color:#fff;border-radius:999px;text-decoration:none;font-size:15px;font-weight:bold">Renew Now</a>
    </div>
    <div style="color:#8a7a9a;font-size:12px;text-align:center;margin-top:12px">
        💡 Your membership tier and day count will continue accumulating after renewal!
    </div>
</td></tr>
<tr><td style="padding:16px 24px;text-align:center;background:#0f0a1e;border-top:1px solid #1a1630">
    <div style="color:#6a5a8a;font-size:11px">If you already renewed, please ignore this email.</div>
</td></tr>
</table>
</td></tr></table>
</body></html>"""

        text_body = f"""⏰ Subscription Expiring Soon

Dear {user_name or 'Seeker'},

Your {plan_en} plan will expire on {end_date} ({days_left} days left).

Renew now to keep receiving daily fortune readings.
💡 Your membership tier and day count will continue accumulating!

Renew: {SITE_URL}/subscribe.html

If you already renewed, please ignore this email."""
        subject = f"⏰ Subscription Expiring Soon ({days_left} days left)"

    return html, text_body, subject


# ─── 自动化营销 Hook ─────────────────────────────────────────
def marketing_hook(user, fortune_result):
    """营销逻辑钩子，每次发送运势后调用"""
    hooks = []
    plan = user.get('plan', 'trial')
    lang = user.get('lang', 'zh')

    if plan == 'trial':
        conn = get_db()
        logs = conn.execute("""
            SELECT COUNT(*) as cnt FROM daily_fortune_logs
            WHERE user_id=? AND sent_via_email=1
        """, (user['id'],)).fetchone()
        conn.close()
        days_received = logs['cnt'] if logs else 0
        if days_received >= 2:
            if lang == "zh":
                hooks.append({
                    'type': 'trial_to_paid',
                    'subject': '✨ 免费试用即将结束，升级解锁每日完整运势',
                    'message': '你已体验了3天每日运势。升级到月卡后，每天收到完整版命盘解析 + 宫位详解 + 热门话题 + 每日故事。',
                })
            else:
                hooks.append({
                    'type': 'trial_to_paid',
                    'subject': '✨ Free Trial Ending — Unlock Full Daily Fortune',
                    'message': 'You have experienced 3 days of daily fortune. Upgrade to unlock full chart analysis + trending topics + daily stories.',
                })
    return hooks


# ─── 主流程 ───────────────────────────────────────────────────
def run(target_date=None, dry_run=False, user_id=None):
    today = target_date or date.today().isoformat()
    print(f"\n{'='*50}")
    print(f"  每日运势调度 | {today}")
    print(f"  {'DRY RUN' if dry_run else 'LIVE'}")
    if user_id:
        print(f"  Single user mode: id={user_id}")
    print(f"{'='*50}\n")

    # 验证邮件配置
    email_ok = False
    if not dry_run:
        email_ok = check_email_config()
        print(f"📧 SMTP: {'OK' if email_ok else 'FAILED'}")
        if not email_ok:
            print("⚠️  Continuing without email...")

    # 获取活跃用户
    if user_id:
        user = get_user_by_id(user_id)
        if not user:
            print(f"❌ User {user_id} not found")
            return
        # Check/create subscription
        sub = get_subscription_by_user_id(user_id)
        if not sub:
            conn = get_db()
            end = (date.today() + timedelta(days=FREE_TRIAL_DAYS)).isoformat()
            conn.execute("""
                INSERT INTO subscriptions (user_id, plan, status, start_date, end_date, lang)
                VALUES (?, 'trial', 'active', ?, ?, 'zh')
            """, (user_id, today, end))
            conn.commit()
            conn.close()
            print(f"  ✅ Created trial subscription for user {user_id} (ends {end})")
        users = get_active_subscriptions() if not user_id else [dict(get_user_by_id(user_id))]
    else:
        users = get_active_subscriptions()

    print(f"👤 Active users: {len(users)}")
    if not users:
        print("  No active users found.")
        print("  💡 Tip: Run with --user-id=1 after adding a user via admin")
        return

    # Pre-fetch daily content once (for trending + story)
    daily_content = None
    if not dry_run:
        # Detect lang from first user to determine which content to fetch
        # In practice, we might need both zh and en, but fetch based on majority
        print("  Fetching daily content...")
        # We'll fetch content per user later based on their lang
    else:
        # In dry run, also try to get content
        pass

    # 统计
    stats = {
        'total': len(users),
        'sent': 0,
        'skipped': 0,
        'failed': 0,
        'total_score': 0,
    }

    # Cache daily content by language
    content_cache = {}

    for u in users:
        u = dict(u)
        user_lang = u.get('lang', 'zh') or 'zh'
        print(f"\n── {u.get('email', '?')} ({u.get('plan', '?')}) [lang={user_lang}] ──")

        # 跳过已发送
        if check_fortune_sent(u['id'], today) and not dry_run:
            print(f"  ⏭️  Already sent today")
            stats['skipped'] += 1
            continue

        birth = {
            "year": u['birth_year'],
            "month": u['birth_month'],
            "day": u['birth_day'],
            "hour": u['birth_hour'],
            "gender": u['gender'],
        }

        print(f"  Birth: {birth['year']}-{birth['month']:02d}-{birth['day']:02d} H{birth['hour']}")
        print(f"  Computing fortune...")

        fortune = calc_fortune(birth, today)
        if not fortune:
            stats['failed'] += 1
            continue

        daily = fortune.get('daily', {})
        text = fortune.get('text', {})

        score = daily.get('overallScore', 0)
        stats['total_score'] += score

        lucky = daily.get('luckyPalaces', [])
        caution = daily.get('cautionPalaces', [])
        ganzhi = daily.get('dayGanZhi', '')

        print(f"  Score: {score} | 干支: {ganzhi}")
        print(f"  Lucky: {', '.join(lucky) if lucky else '—'}")
        print(f"  Caution: {', '.join(caution) if caution else '—'}")

        # Get delivery count (before incrementing for display)
        sub = get_subscription_by_user_id(u['id'])
        delivery_count = sub['delivery_count'] if sub else 0
        # delivery_count is what was before today; the actual count after sending will be +1
        display_count = delivery_count + 1  # This is the count that includes today
        tier_num, tier_name, _ = get_tier_info(display_count) if user_lang == 'zh' else get_tier_info_en(display_count)
        print(f"  📊 Delivery count: {delivery_count} → {display_count} | Tier: T{tier_num}")

        if dry_run:
            stats['sent'] += 1
            continue

        # Fetch daily content if needed by this user's tier
        user_content = None
        if tier_num >= 2:
            # Fetch content for this language if not cached
            if user_lang not in content_cache:
                print(f"  Fetching daily content ({user_lang})...")
                content_cache[user_lang] = get_daily_content(lang=user_lang)
            user_content = content_cache.get(user_lang)

        # 存DB
        save_daily_fortune(
            u['id'], today, ganzhi, score,
            [text.get('luckyAreas', [])],
            [text.get('cautionAreas', [])],
            fortune, sent=False
        )

        # 发邮件
        if email_ok:
            html, text_body, subject = build_fortune_email(
                u.get('name', ''),
                fortune,
                u.get('plan', 'trial'),
                lang=user_lang,
                delivery_count=display_count,
                daily_content=user_content,
                user_id=u.get('id'),
            )
            ok = send_email(u['email'], subject, html, text_body)
            if ok:
                print(f"  ✅ Email sent (lang={user_lang}, tier=T{tier_num})")
                stats['sent'] += 1
                # 更新发送状态 + 递增 delivery_count
                save_daily_fortune(
                    u['id'], today, ganzhi, score,
                    [text.get('luckyAreas', [])],
                    [text.get('cautionAreas', [])],
                    fortune, sent=True
                )
                increment_delivery_count(u['id'])
            else:
                print(f"  ❌ Email failed")
                stats['failed'] += 1
            # QQ SMTP 限速
            time.sleep(2)
        else:
            # Even without email, increment count
            increment_delivery_count(u['id'])
            stats['sent'] += 1

        # 营销Hook
        hooks = marketing_hook(u, fortune)
        for h in hooks:
            print(f"  🎯 Marketing hook: {h['subject']}")

    # 续费提醒
    if not dry_run and not user_id:
        reminders = get_users_needing_renewal_reminder()
        if reminders:
            print(f"\n📬 Renewal reminders: {len(reminders)}")
            for r, days_left in reminders:
                r_lang = r.get('lang', 'zh') or 'zh'
                html, text_body, subject = build_renewal_email(
                    r['name'], r['plan'], r['end_date'], days_left, lang=r_lang
                )
                if email_ok:
                    ok = send_email(r['email'], subject, html, text_body)
                    print(f"  {'✅' if ok else '❌'} {r['email']} - {r['plan']} expires {r['end_date']}")
                time.sleep(1)

    # 更新统计
    if not dry_run and stats['sent'] > 0:
        avg_score = round(stats['total_score'] / max(stats['sent'], 1), 1)
        conn = get_db()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO fortune_stats
                (stat_date, total_active_users, total_sent, total_opened, avg_score)
                VALUES (?, ?, ?, 0, ?)
            """, (today, stats['total'], stats['sent'], avg_score))
            conn.commit()
        except Exception as e:
            print(f"  ⚠️ Stats insert failed (table may not exist): {e}")
        finally:
            conn.close()

    # 报告
    print(f"\n{'='*50}")
    print(f"  📊 报告 | {today}")
    print(f"  活跃用户: {stats['total']}")
    print(f"  成功发送: {stats['sent']}")
    print(f"  跳过(已发): {stats['skipped']}")
    print(f"  失败: {stats['failed']}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='每日运势推送（增强版）')
    parser.add_argument('--dry-run', action='store_true', help='模拟运行')
    parser.add_argument('--date', type=str, help='指定日期 (YYYY-MM-DD)')
    parser.add_argument('--user-id', type=int, help='指定用户')
    args = parser.parse_args()

    run(
        target_date=args.date,
        dry_run=args.dry_run,
        user_id=args.user_id,
    )
