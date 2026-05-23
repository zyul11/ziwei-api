"""
紫微斗数 API — 排盘 + AI 解读 + API Key 计费
"""
import json
import sqlite3
import subprocess
import secrets
import os
import json as jmod
import hashlib
import random
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

# Load .env for local dev
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from fastapi import FastAPI, HTTPException, Header, Depends, Request, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from openai import OpenAI
from typing import Optional

# ─── config ────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
ENGINE_PATH = BASE_DIR / "api" / "ziwei-engine.js"
DATABASE_PATH = Path("/data/ziwei.db") if Path("/data").exists() else BASE_DIR / "data" / "ziwei.db"
DEEPSEEK_API_KEY = ""

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
LEMONSQUEEZY_API_KEY = os.getenv("LEMONSQUEEZY_API_KEY", "")
LEMONSQUEEZY_STORE_ID = os.getenv("LEMONSQUEEZY_STORE_ID", "")
LEMONSQUEEZY_WEBHOOK_SECRET = os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET", "")
BASE_URL = os.getenv("BASE_URL", "http://ziweiapi.site")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_API = "https://api-m.paypal.com"  # production
USDT_WALLET = "TMVWYC7SYnDg5UVFuBGbMY1Q2PbpnaXPei"
TRONGRID_API = "https://api.trongrid.io"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"  # USDT (TRC-20) mainnet
# PAYPAL_API = "https://api-m.sandbox.paypal.com"  # sandbox

# Owner key for GSC dashboard (only this key can view all sites' search performance)
OWNER_KEY_HASH = os.getenv("OWNER_KEY_HASH", "f416fd73ddc34f27")

# ─── SMTP config ────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(to: str, subject: str, html: str) -> bool:
    """发送HTML邮件，返回是否成功"""
    if not SMTP_USER or not SMTP_PASS:
        print(f"[email] SMTP not configured, skipping to {to}: {subject}")
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"紫微斗数 <{SMTP_FROM}>"
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        print(f"[email] Sent to {to}: {subject}")
        return True
    except Exception as e:
        print(f"[email] Failed to {to}: {e}")
        return False

client: Optional[OpenAI] = None
db_conn: Optional[sqlite3.Connection] = None

# ─── lifespan ───────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global client, db_conn
    import os
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if api_key and api_key != "sk-your-key-here":
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db_conn = sqlite3.connect(str(DATABASE_PATH), check_same_thread=False)
    db_conn.execute("""CREATE TABLE IF NOT EXISTS api_keys (key TEXT PRIMARY KEY, name TEXT, balance INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now')), expires_at TEXT, active INTEGER DEFAULT 1)""")
    db_conn.execute("""CREATE TABLE IF NOT EXISTS usage_log (id INTEGER PRIMARY KEY AUTOINCREMENT, api_key TEXT, endpoint TEXT, input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0, cost INTEGER DEFAULT 1, created_at TEXT DEFAULT (datetime('now')))""")
    db_conn.execute("""CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, package TEXT NOT NULL, amount REAL NOT NULL, pay_method TEXT DEFAULT 'alipay', status TEXT DEFAULT 'pending', api_key TEXT, payjs_order_id TEXT, created_at TEXT DEFAULT (datetime('now')), paid_at TEXT)""")
    db_conn.commit()
    # Add end_date to subscriptions if missing (migration)
    try:
        db_conn.execute("ALTER TABLE subscriptions ADD COLUMN end_date TEXT")
        db_conn.commit()
    except: pass
    # Add subscriptions table if not exists
    db_conn.execute("""CREATE TABLE IF NOT EXISTS subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, plan TEXT NOT NULL DEFAULT 'gift', status TEXT DEFAULT 'active', subscribed_at TEXT DEFAULT (datetime('now')), end_date TEXT, cancelled_at TEXT, user_id INTEGER)""")
    # Add buyer_email to orders if missing
    try:
        db_conn.execute("ALTER TABLE orders ADD COLUMN buyer_email TEXT")
        db_conn.commit()
    except: pass
    # GSC daily stats table
    db_conn.execute("""CREATE TABLE IF NOT EXISTS gsc_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        date TEXT NOT NULL,
        impressions INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        ctr REAL DEFAULT 0,
        avg_position REAL DEFAULT 0,
        top_queries TEXT DEFAULT '{}',
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(domain, date)
    )""")
    # Create index for faster lookups
    try:
        db_conn.execute("CREATE INDEX IF NOT EXISTS idx_sub_email ON subscriptions(email)")
    except: pass
    # Add language to users if missing
    try:
        db_conn.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'zh'")
        db_conn.commit()
    except: pass
    # Add source + marketing_consent to orders (game subscription tracking)
    try:
        db_conn.execute("ALTER TABLE orders ADD COLUMN source TEXT DEFAULT ''")
        db_conn.commit()
    except: pass
    try:
        db_conn.execute("ALTER TABLE orders ADD COLUMN marketing_consent INTEGER DEFAULT 0")
        db_conn.commit()
    except: pass
    # Add source + marketing_consent to subscriptions
    try:
        db_conn.execute("ALTER TABLE subscriptions ADD COLUMN source TEXT DEFAULT ''")
        db_conn.commit()
    except: pass
    try:
        db_conn.execute("ALTER TABLE subscriptions ADD COLUMN marketing_consent INTEGER DEFAULT 0")
        db_conn.commit()
    except: pass
    # Add marketing_consent to users
    try:
        db_conn.execute("ALTER TABLE users ADD COLUMN marketing_consent INTEGER DEFAULT 0")
        db_conn.commit()
    except: pass
    # Add tx_hash to orders for USDT tracking
    try:
        db_conn.execute("ALTER TABLE orders ADD COLUMN tx_hash TEXT")
        db_conn.commit()
    except: pass
    # Add source to users
    try:
        db_conn.execute("ALTER TABLE users ADD COLUMN source TEXT DEFAULT ''")
        db_conn.commit()
    except: pass
    # Add seo_urls table for SEO scan subscriptions
    db_conn.execute("""CREATE TABLE IF NOT EXISTS seo_urls (id INTEGER PRIMARY KEY AUTOINCREMENT, api_key TEXT NOT NULL, url TEXT NOT NULL, last_scan TEXT, last_score INTEGER, created_at TEXT DEFAULT (datetime('now')), active INTEGER DEFAULT 1)""")
    try:
        db_conn.execute("ALTER TABLE seo_urls ADD COLUMN last_score INTEGER")
        db_conn.commit()
    except: pass
    # Add audit_logs table for anonymized data collection
    db_conn.execute("""CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, domain_hash TEXT, score INTEGER, total_checks INTEGER, passed INTEGER, warnings INTEGER, failed INTEGER, high_issues INTEGER, med_issues INTEGER, low_issues INTEGER, word_count INTEGER, content_type TEXT, created_at TEXT DEFAULT (datetime('now')))""")
    # Add scan_logs table for per-key scan tracking (anti-abuse)
    db_conn.execute("""CREATE TABLE IF NOT EXISTS scan_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, key_hash TEXT, url TEXT, score INTEGER, ip TEXT, created_at TEXT DEFAULT (datetime('now')))""")
    # Add email_subscribers table for email sequence automation
    db_conn.execute("""CREATE TABLE IF NOT EXISTS email_subscribers (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE, domain TEXT, score INTEGER, step INTEGER DEFAULT 0, subscribed_at TEXT DEFAULT (datetime('now')), last_sent TEXT, unsubscribed INTEGER DEFAULT 0, source TEXT DEFAULT 'scan')""")
    db_conn.execute("""CREATE TABLE IF NOT EXISTS email_sequence_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, subscriber_id INTEGER, step INTEGER, subject TEXT, sent_at TEXT DEFAULT (datetime('now')), opened INTEGER DEFAULT 0, FOREIGN KEY(subscriber_id) REFERENCES email_subscribers(id))""")
    yield
    if db_conn:
        db_conn.close()

app = FastAPI(title="紫微斗数 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

static_dir = Path(__file__).parent.parent
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    from fastapi.responses import HTMLResponse
    @app.get("/app/{page:path}")
    def serve_page(page: str):
        fp = static_dir / page
        if fp.exists(): return HTMLResponse(fp.read_text(encoding="utf-8"))
        return HTMLResponse("Not found", 404)
    # 文章页及相关资源直接通过 /articles/ 访问
    @app.get("/articles/{subpath:path}")
    def serve_articles(subpath: str):
        if not subpath:
            subpath = "index.html"
        fp = static_dir / "articles" / subpath
        if fp.exists() and fp.is_file():
            if str(fp).endswith(('.html','.json','.txt','.xml')):
                return HTMLResponse(fp.read_text(encoding="utf-8"))
            return FileResponse(str(fp))
        # 301 /articles/ → /articles/index.html
        if not subpath.endswith('.html'):
            fp2 = static_dir / "articles" / (subpath + ".html")
            if fp2.exists():
                return HTMLResponse(fp2.read_text(encoding="utf-8"))
        return HTMLResponse("Not found", 404)
    @app.get("/")
    async def serve_root():
        html = (static_dir / "release" / "index.html").read_text(encoding="utf-8")
        # 注入统计数据
        try:
            tk = db_conn.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]
            tu = db_conn.execute("SELECT COUNT(*) FROM usage_log").fetchone()[0]
            html = html.replace('id="statUsers">-</span>', f'id="statUsers">{tk}</span>')
            html = html.replace('id="statCalls">-</span>', f'id="statCalls">{tu}</span>')
            # SEO audit stats
            total_audits = db_conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
            total_issues = db_conn.execute("SELECT COALESCE(SUM(high_issues+med_issues+low_issues),0) FROM audit_logs").fetchone()[0]
            total_fixes = db_conn.execute("SELECT COALESCE(SUM(total_checks-passed),0) FROM audit_logs").fetchone()[0]
            html = html.replace('id="statSites">0</h3>', f'id="statSites">{total_audits}</h3>')
            html = html.replace('id="statIssues">0</h3>', f'id="statIssues">{total_issues}</h3>')
            html = html.replace('id="statFixes">0</h3>', f'id="statFixes">{total_fixes}</h3>')
        except:
            pass
        from fastapi.responses import HTMLResponse
        resp = HTMLResponse(html)
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp

# ─── models ─────────────────────────────────────────────────
class PaiPanRequest(BaseModel):
    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: float = Field(..., ge=0, le=23)
    gender: str = Field(..., pattern="^(male|female)$")
    style: str = Field("modern", pattern="^(modern|classical|poetic)$")
    city: str = Field("", max_length=100)
    language: str = Field("zh-Hant", pattern="^(zh-Hant|zh-Hans|en|zh)$")

class PaiPanResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None

class KeyCreateRequest(BaseModel):
    name: str = "default"
    quota: int = 500

class KeyCreateResponse(BaseModel):
    key: str
    balance: int

# ─── middleware ─────────────────────────────────────────────
def get_api_key(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(401, "Missing Authorization header")
    key = authorization.replace("Bearer ", "").strip()
    cur = db_conn.execute("SELECT balance, active, expires_at FROM api_keys WHERE key=?", (key,))
    row = cur.fetchone()
    if not row: raise HTTPException(403, "Invalid API key")
    if not row[1]: raise HTTPException(403, "API key is disabled")
    if row[2] and datetime.fromisoformat(row[2]) < datetime.now(): raise HTTPException(403, "API key expired")
    if row[0] <= 0: raise HTTPException(402, "Insufficient balance")
    return key

def deduct_balance(key: str, cost: int = 1):
    db_conn.execute("UPDATE api_keys SET balance = balance - ? WHERE key = ?", (cost, key))
    db_conn.commit()

def log_usage(key: str, endpoint: str, cost: int = 1, in_tokens: int = 0, out_tokens: int = 0):
    db_conn.execute("INSERT INTO usage_log (api_key, endpoint, input_tokens, output_tokens, cost) VALUES (?, ?, ?, ?, ?)", (key, endpoint, in_tokens, out_tokens, cost))
    db_conn.commit()

# ─── engine ─────────────────────────────────────────────────
import shutil
_NODE = shutil.which("node") or "/Users/air/.local/bin/node"

def run_engine(year: int, month: int, day: int, hour: float, gender: str) -> dict:
    inp = json.dumps({"year": year, "month": month, "day": day, "hour": hour, "gender": gender})
    r = subprocess.run([_NODE, str(ENGINE_PATH)], input=inp, capture_output=True, text=True, timeout=10, cwd=str(BASE_DIR))
    if r.returncode != 0: raise RuntimeError(f"Engine error: {r.stderr}")
    return json.loads(r.stdout)

# ─── AI prompts (multilingual) ─────────────────────────────
def load_style_prompt(style: str, language: str = "zh-Hant") -> str:
    lang_zh = "zh-Hant" if language in ("zh-Hant","zh") else "zh-Hans"
    en = language == "en"
    if en:
        return {
            "modern": "You are a Zi Wei Dou Shu expert. Use casual English, emojis. Focus on Life/Wealth/Career/Spouse palaces. If city given, incorporate local context. End with 'This is for entertainment and reference only.'",
            "classical": "You are a classical Zi Wei master. Semi-classical English. Reference traditional sayings. Analyze star combos. End with 'This is for entertainment and reference only.'",
            "poetic": "You are a healing astrology guide. Poetic English. 3-5 sentences per paragraph. Warm uplifting energy. End with 'This is for entertainment and reference only.'",
        }.get(style, "")
    return {
        "modern": f"你是一个紫微斗数命理师。口语化。分析命宫/财帛/官禄/夫妻宫。结合城市特点。请使用{lang_zh}回答。结尾注明'仅供娱乐参考'。",
        "classical": f"半文言风格。传统断语。五行生克。四化流转。请使用{lang_zh}回答。结尾注明'仅供娱乐参考'。",
        "poetic": f"治愈系风格。诗意短句。每段3-5句。请使用{lang_zh}回答。结尾注明'仅供娱乐参考'。",
    }.get(style, "")

def load_daily_prompt(style: str, language: str = "zh-Hant") -> str:
    lang_zh = "zh-Hant" if language in ("zh-Hant","zh") else "zh-Hans"
    en = language == "en"
    if en:
        return {
            "modern": "You are an environmental psychology analyst. Based on user's chart + today's date, give daily tips: energy theme, do's/don'ts, lucky colors (2-3), active palace, space tip. Max 300 words. Don't say fortune-telling.",
            "classical": "You are a classical Zi Wei calendar expert. Analyze: today's spirits, palace activation, do's/don'ts, 5-element balance, timing tip. End with '...entertainment only.' Max 300 words.",
            "poetic": "You are a healing energy guide. Morning poem, how user looks today, a small ritual, today's mantra. Warm poetic language. Max 300 words. End with '...entertainment only.'",
        }.get(style, "")
    return {
        "modern": f"环境心理学+色彩艺术分析师。今日能量/宜忌/幸运色/关注宫位/空间小提示。请使用{lang_zh}回答。300字以内。",
        "classical": f"传统命师+黄历择日。今日神煞/十二宫引动/宜忌/五行调候/择时提示。请使用{lang_zh}回答。300字以内。结尾注明'仅供娱乐参考'。",
        "poetic": f"治愈系能量指引。清晨诗句/今日的你/小仪式/今日箴言。请使用{lang_zh}回答。300字以内。结尾注明'仅供娱乐参考'。",
    }.get(style, "")

def load_daxian_prompt(style: str, language: str = "zh-Hant") -> str:
    lang_zh = "zh-Hant" if language in ("zh-Hant","zh") else "zh-Hans"
    en = language == "en"
    if en:
        return {
            "modern": "You are a Zi Wei consultant analyzing the user's current 10-year period. Decade palace, main star influence, assistant stars, 4-transformations, life advice. End with '...entertainment only.'",
            "classical": "Classical master analyzing decade period. Palace+stars, 4-transformations auspiciousness, navigation advice. End with '...entertainment only.'",
            "poetic": "Healing astrologer interpreting decade period. Poetic, 3-5 sentences per paragraph. Uplifting. End with '...entertainment only.'",
        }.get(style, "")
    return {
        "modern": f"紫微斗数命理咨询师。大限宫位/主星特质/辅星加成/四化引动/人生建议。请使用{lang_zh}回答。仅供娱乐参考。",
        "classical": f"传统命师。半文言。大限宫垣星曜/四化吉凶/趋避建议。请使用{lang_zh}回答。仅供娱乐参考。",
        "poetic": f"治愈系命理师。诗意温暖。每段3-5句。请使用{lang_zh}回答。仅供娱乐参考。",
    }.get(style, "")

CITY_PROFILES = {
    "新加坡": "国际金融中心、港口贸易枢纽、花园城市", "吉隆坡": "马来西亚首都、华人活跃、热带气候",
    "曼谷": "泰国首都、旅游大城、华人文化深厚", "雅加达": "印尼首都、华人商业网络发达",
    "马尼拉": "菲律宾首都、BPO外包产业", "胡志明": "越南经济中心、新兴制造业枢纽",
    "台北": "台湾政经文化中心、半导体/ICT产业", "香港": "国际金融中心、中西交汇",
    "澳门": "世界旅游休闲中心、博彩业", "上海": "中国经济金融中心、长三角集群",
    "北京": "政治文化教育中心、互联网/文创", "深圳": "科技之都、大湾区核心",
    "广州": "南大门、千年商都、岭南文化", "杭州": "数字经济重镇、阿里总部",
    "成都": "西南消费中心、文创之都", "高雄": "台湾南部最大城市、港口与重工业",
    "台中": "台湾中部经济文化中心",
    "纽约": "世界金融中心、多元文化大熔炉", "洛杉矶": "娱乐产业之都、好莱坞",
    "旧金山": "硅谷所在地、全球科创发源地", "西雅图": "云计算/航空产业领先",
    "波士顿": "教育之都、哈佛/MIT/生物科技", "芝加哥": "中西部经济中心、大湖区枢纽",
    "华盛顿": "美国政治中心、政府/智库/国际组织", "休斯顿": "能源之都、航天中心/医疗产业",
    "达拉斯": "德州经济中心、电信/物流/金融", "迈阿密": "拉美门户、旅游/贸易/金融",
    "亚特兰大": "美国南方经济中心、媒体/物流/科技", "拉斯维加斯": "世界娱乐之都、旅游/会展",
    "凤凰城": "亚利桑那州首府、半导体/制造业", "奥斯汀": "德州科技新都、SXSW/音乐",
    "波特兰": "西海岸创意之都、户外/科技", "奥兰多": "主题公园之都、迪士尼/环球影城",
    "圣地亚哥": "南加州生物科技/国防产业", "丹佛": "落基山区经济中心、户外/科技",
    "温哥华": "加拿大西岸最大城市、华人社区", "多伦多": "加拿大最大城市、金融中心",
    "蒙特利尔": "加拿大法语区文化中心、AI/游戏产业", "卡尔加里": "加拿大能源之都、牛仔节",
    "渥太华": "加拿大首都、科技/政府产业",
    "伦敦": "全球金融中心、欧洲文化之都", "曼彻斯特": "英国工业革命发源地、足球/音乐文化",
    "爱丁堡": "苏格兰首府、艺术节/金融科技",
    "巴黎": "艺术时尚之都、奢侈品/旅游", "柏林": "德国首都、创业/科技/文化多元",
    "慕尼黑": "南德经济中心、汽车/工程/啤酒节", "法兰克福": "欧洲金融中心、会展/交通枢纽",
    "阿姆斯特丹": "金融/创新枢纽、金融科技", "苏黎世": "全球金融中心、银行业/高端制造",
    "日内瓦": "国际组织之城、外交/钟表/奢侈品", "斯德哥尔摩": "北欧金融中心、科技创新",
    "哥本哈根": "丹麦首都、设计/可再生能源", "奥斯陆": "挪威首都、石油/海洋/极地",
    "赫尔辛基": "芬兰首都、教育/科技/设计", "马德里": "西班牙首都、艺术/旅游/金融",
    "巴塞罗那": "地中海之都、建筑/旅游/科技", "米兰": "意大利时尚设计之都、金融中心",
    "罗马": "意大利首都、文化历史之都、旅游", "维也纳": "奥地利首都、古典音乐/国际组织",
    "布拉格": "捷克首都、旅游/工程/中欧枢纽", "都柏林": "爱尔兰科技之都、硅谷欧洲总部",
    "布鲁塞尔": "欧盟之都、外交/巧克力", "里斯本": "葡萄牙首都、旅游/科技/创业",
    "东京": "东亚经济中心、服务业/科技", "首尔": "韩国首都、韩流文化中心",
    "悉尼": "澳洲最大城市、南太平洋金融中心", "墨尔本": "文化之都、全球最宜居城市",
    "布里斯班": "澳洲第三大城市、矿业/旅游", "珀斯": "澳洲西海岸之星、矿业/资源",
    "奥克兰": "新西兰最大城市、交通枢纽",
    "迪拜": "中东商业旅游中心、免税财富", "开普敦": "南非立法首都、旅游和金融业",
    "孟买": "印度金融之都、宝莱坞/贸易", "班加罗尔": "印度硅谷、IT外包/科技创新",
}
CITY_PROFILES_EN = {
    "新加坡": "Global financial hub, port trade, Garden City",
    "吉隆坡": "Malaysia's capital, tropical, finance/tourism/manufacturing",
    "曼谷": "Thailand's capital, tourism hub, deep Chinese roots",
    "雅加达": "Indonesia's capital, Chinese business networks",
    "马尼拉": "Philippines' capital, BPO/tourism/services",
    "胡志明": "Vietnam's economic center, emerging manufacturing",
    "台北": "Taiwan's center, semiconductors/ICT",
    "香港": "International financial hub, East meets West",
    "澳门": "World tourism/leisure, gaming industry",
    "上海": "China's financial capital, Yangtze River Delta",
    "北京": "Political/cultural center, internet/creative industries",
    "深圳": "China's tech capital, Greater Bay Area",
    "广州": "Southern gateway, millennia-old trade city",
    "杭州": "Digital economy powerhouse, Alibaba HQ",
    "成都": "Southwest consumer hub, laid-back culture",
    "高雄": "Southern Taiwan's largest city, port/industry",
    "台中": "Central Taiwan's economic hub",
    "纽约": "Global financial center, Wall Street, melting pot",
    "洛杉矶": "Entertainment capital, Hollywood",
    "旧金山": "Home to Silicon Valley, global tech innovation",
    "西雅图": "Cloud computing/aerospace, Amazon/MS HQ",
    "波士顿": "Education capital, Harvard/MIT, biotech",
    "芝加哥": "Midwest economic center, Great Lakes",
    "华盛顿": "US political center, government/think tanks",
    "休斯顿": "Energy capital, space center/healthcare",
    "达拉斯": "Texas economic hub, telecom/logistics/finance",
    "迈阿密": "Gateway to Latin America, tourism/trade",
    "亚特兰大": "Southern economic hub, media/logistics/tech",
    "拉斯维加斯": "Entertainment capital, tourism/conventions",
    "凤凰城": "Arizona capital, semiconductor/manufacturing",
    "奥斯汀": "Texas tech hub, SXSW/music scene",
    "波特兰": "West Coast creative hub, outdoor/tech",
    "奥兰多": "Theme park capital, Disney/Universal",
    "圣地亚哥": "Southern California biotech/defense",
    "丹佛": "Rocky Mountain economic center, outdoor/tech",
    "温哥华": "Canada's West Coast, large Chinese community",
    "多伦多": "Canada's largest city, financial center",
    "蒙特利尔": "Quebec's cultural capital, AI/gaming industry",
    "卡尔加里": "Canada's energy capital, tech growth",
    "渥太华": "Canada's capital, tech/government",
    "伦敦": "Global finance, European cultural capital",
    "曼彻斯特": "Industrial revolution birthplace, football/music",
    "爱丁堡": "Scotland's capital, festivals/fintech",
    "巴黎": "Fashion/art capital, luxury/tourism",
    "柏林": "Germany's startup/tech/culture hub",
    "慕尼黑": "Southern Germany's economic heart, automotive/engineering",
    "法兰克福": "European financial hub, trade fair city",
    "阿姆斯特丹": "Finance/innovation hub, fintech",
    "苏黎世": "Global finance, banking/high-end manufacturing",
    "日内瓦": "City of international organizations, diplomacy/luxury",
    "斯德哥尔摩": "Nordic financial hub, tech innovation",
    "哥本哈根": "Danish capital, design/renewable energy",
    "奥斯陆": "Norwegian capital, oil/maritime/polar",
    "赫尔辛基": "Finnish capital, education/tech/design",
    "马德里": "Spanish capital, art/tourism/finance",
    "巴塞罗那": "Mediterranean capital, architecture/tourism/tech",
    "米兰": "Italian fashion/design capital, finance hub",
    "罗马": "Italian capital, cultural heritage, tourism",
    "维也纳": "Austrian capital, classical music/international orgs",
    "布拉格": "Czech capital, tourism/engineering/Central Europe hub",
    "都柏林": "Ireland's tech capital, European Silicon Valley hub",
    "布鲁塞尔": "Capital of the EU, diplomacy/chocolate",
    "里斯本": "Portuguese capital, tourism/tech/startup scene",
    "东京": "Global megacity, services/tech/finance",
    "首尔": "South Korea's capital, Hallyu culture",
    "悉尼": "Australia's largest city, Pacific financial center",
    "墨尔本": "Cultural capital, world's most livable",
    "布里斯班": "Australia's third largest, mining/tourism",
    "珀斯": "Western Australia's star, mining/resources",
    "奥克兰": "New Zealand's largest city, transport hub",
    "迪拜": "Business/tourism hub, tax-free wealth",
    "开普敦": "Legislative capital, tourism/finance",
    "孟买": "India's financial capital, Bollywood/trade",
    "班加罗尔": "India's Silicon Valley, IT/tech innovation",
}

def get_city_context(city: str, language: str = "zh-Hant") -> str:
    if not city: return ""
    if language == "en":
        p = CITY_PROFILES_EN.get(city, "a diverse city")
        return f"\n📍【City Context — {city}】User lives/works in {city}. {p}. Incorporate local context."
    p = CITY_PROFILES.get(city, "多元经济和服务业")
    return f"\n📍【城市定向 — {city}】用户在{city}。{p}。结合当地特点解读。"

# ─── routes ─────────────────────────────────────────────────
_FREE_IPS: set = set()

@app.get("/shop.html")
async def serve_shop():
    p = static_dir / "shop.html"
    if p.exists():
        from fastapi.responses import HTMLResponse
        resp = HTMLResponse(p.read_text(encoding="utf-8"))
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp
    return HTMLResponse("Not found", 404)

@app.get("/about.html")
async def serve_about():
    p = static_dir / "about.html"
    if p.exists():
        from fastapi.responses import HTMLResponse
        resp = HTMLResponse(p.read_text(encoding="utf-8"))
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp
    return HTMLResponse("Not found", 404)

@app.get("/api-docs.html")
async def serve_api_docs():
    p = static_dir / "api-docs.html"
    if p.exists(): return HTMLResponse(p.read_text(encoding="utf-8"))
    return HTMLResponse("Not found", 404)

@app.get("/en/{filename:path}")
async def serve_en_article(filename: str):
    articles_en = static_dir / "articles" / "en"
    # Security: prevent path traversal
    clean = Path(filename).name
    p = articles_en / clean
    if p.exists() and p.is_file():
        return HTMLResponse(p.read_text(encoding="utf-8"))
    return HTMLResponse("Not found", 404)

@app.get("/health")
def root():
    return {"name": "紫微斗数 API", "version": "1.0.0", "docs": "/docs"}

# ─── admin login ───────────────────────────────────────────
ADMIN_PASSWORD = "ziweisanniu"
ADMIN_EMAIL = os.getenv("SMTP_USER", "87549153@qq.com")

# In-memory verification codes
_admin_codes: dict = {}

@app.post("/v1/admin/login")
async def admin_login(password: str = Query(...)):
    if password == ADMIN_PASSWORD:
        token = secrets.token_hex(32)
        return {"success": True, "token": token}
    return {"success": False, "error": "密码错误"}

@app.post("/v1/admin/send-code")
async def admin_send_code():
    """Send verification code to admin email."""
    from smtplib import SMTP
    from email.mime.text import MIMEText
    
    code = f"{random.randint(100000, 999999)}"
    expiry = datetime.now() + timedelta(minutes=10)
    _admin_codes["code"] = code
    _admin_codes["expires_at"] = expiry
    
    try:
        msg = MIMEText(f"您的管理后台验证码是：{code}\n\n有效期为 10 分钟，请勿泄露。", "plain", "utf-8")
        msg["Subject"] = "=?UTF-8?B?5p6c5Z2A5ZCO5Y+w6aqM6K+B56CB?="
        msg["From"] = SMTP_USER
        msg["To"] = ADMIN_EMAIL
        
        server = SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return {"success": True, "message": f"验证码已发送至 {ADMIN_EMAIL[:3]}***@***"}
    except Exception as e:
        return {"success": False, "error": f"邮件发送失败: {str(e)}"}

@app.post("/v1/admin/verify-code")
async def admin_verify_code(code: str = Query(...)):
    """Verify email code and return admin token."""
    expiry = _admin_codes.get("expires_at")
    if not expiry or datetime.now() > expiry:
        return {"success": False, "error": "验证码已过期，请重新获取"}
    if _admin_codes.get("code") != code:
        return {"success": False, "error": "验证码错误"}
    # Clear used code
    _admin_codes.clear()
    token = secrets.token_hex(32)
    return {"success": True, "token": token}

@app.get("/v1/admin/orders")
async def admin_orders(token: str = Query(...)):
    """List pending and recent orders."""
    o = db_conn.execute("""
        SELECT id, package, amount, api_key, buyer_email, status, created_at, paid_at
        FROM orders ORDER BY created_at DESC LIMIT 50
    """).fetchall()
    pn = {k: v["name"] for k, v in PACKAGES.items()}
    for k, v in SEO_PACKAGES.items():
        pn[k] = v["name"]
    return {"success": True, "data": [
        {
            "id": r[0],
            "package_name": pn.get(r[1], r[1]),
            "amount": r[2],
            "api_key": r[3] or "",
            "buyer_email": r[4] or "",
            "status": r[5],
            "created_at": str(r[6]) if r[6] else "",
            "source": "ziwei" if r[1] in PACKAGES else "seo",
        } for r in o
    ]}

@app.get("/v1/admin/settings")
async def admin_settings(token: str = Query(...)):
    """Get admin settings."""
    return {"success": True, "data": {
        "paypal_email": os.getenv("PAYPAL_EMAIL", "admin@example.com"),
        "admin_email": ADMIN_EMAIL,
    }}

@app.post("/v1/admin/confirm")
async def admin_confirm(order_id: str = Query(...), token: str = Query(...)):
    """Confirm payment for an order: generate key + send email."""
    o = db_conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not o:
        return {"success": False, "error": "订单不存在"}
    if o[5] != "pending":
        return {"success": False, "error": "订单已处理"}
    
    pkg = PACKAGES.get(o[2]) or SEO_PACKAGES.get(o[2])
    if not pkg:
        return {"success": False, "error": "套餐不存在"}

    is_seo = o[2] in SEO_PACKAGES
    if is_seo:
        k = "seo_" + secrets.token_hex(16)
        quota = pkg["scans"]
        key_name = f"手动确认-SEO-{pkg['name']}"
    else:
        k = secrets.token_hex(8)
        quota = pkg["quota"]
        key_name = f"手动确认-{pkg['name']}"

    db_conn.execute(
        "INSERT INTO api_keys (key, name, balance) VALUES (?,?,?)",
        (k, key_name, quota)
    )
    db_conn.execute(
        "UPDATE orders SET status='paid', api_key=?, paid_at=datetime('now') WHERE id=?",
        (k, order_id)
    )
    db_conn.commit()

    # Send email if buyer email exists
    buyer_email = o[4]
    if buyer_email:
        try:
            from smtplib import SMTP
            from email.mime.text import MIMEText
            pkg_name = pkg['name']
            pkg_price = pkg['price']
            if is_seo:
                email_body = (
                    f"Thank you for your purchase!\n\n"
                    f"Package: {pkg_name}\n"
                    f"Amount: ${pkg_price}\n"
                    f"API Key: {k}\n"
                    f"Remaining scans: {quota}\n\n"
                    f"Visit https://seo.textools.site and login with this key to use it."
                )
                subject = "=?UTF-8?B?W1NFTyBBdWRpdF0gWW91ciBBUEkgS2V5IGlzIHJlYWR5IQ==?="
            else:
                email_body = (
                    f"感谢您的购买！\n\n"
                    f"套餐：{pkg_name}\n"
                    f"金额：${pkg_price}\n"
                    f"API Key：{k}\n"
                    f"剩余次数：{quota}次\n\n"
                    f"访问 https://seo.textools.site 使用 API Key 登录后即可使用。"
                )
                subject = "=?UTF-8?B?5oKo55qEIEtleSDlt7Llh7rnmoTlj5Hoo4HvvIHvvIE=?="
            msg = MIMEText(email_body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = SMTP_USER
            msg["To"] = buyer_email
            server = SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            server.quit()
        except:
            pass

    return {"success": True, "data": {"key": k, "quota": quota, "package": pkg["name"]}}

# ─── paipan-free ──────────────────────────────────────────────
@app.post("/v1/paipan-free")
def paipan_free(req: PaiPanRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if ip in _FREE_IPS:
        return {"success": True, "data": {"chart": None, "reading": "<div style='text-align:center;padding:10px 0'><div style='font-size:32px;margin-bottom:8px'>🔮</div><div style='color:#e0c8ff;font-size:16px;font-weight:600;margin-bottom:6px'>免费体验已用完</div><div style='color:#6a5a8a;font-size:13px;margin-bottom:14px'>解锁无限次AI解读</div><a href='/shop.html' target='_blank' style='display:inline-block;padding:10px 24px;background:linear-gradient(135deg,#7b68ee,#5a4acd);color:#fff;border-radius:10px;text-decoration:none;font-size:14px;font-weight:600;letter-spacing:1px'>🛒 购买Key解锁完整解读</a></div>", "free_used": True}}
    try:
        chart = run_engine(req.year, req.month, req.day, req.hour, req.gender)
        if not chart.get("success"): return {"success": False, "error": "排盘失败"}
        reading = ""
        if client:
            try:
                prompt = load_style_prompt(req.style, req.language)
                chart_json = json.dumps(chart, ensure_ascii=False, indent=2)
                city_ctx = get_city_context(req.city, req.language)
                user_msg = f"Please interpret this Zi Wei chart (first half preview):\n\n{chart_json}{city_ctx}" if req.language == "en" else f"请解读以下紫微斗数命盘（前半段精华）：\n\n{chart_json}{city_ctx}"
                resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_msg}], temperature=0.7, max_tokens=500, timeout=45)
                full = resp.choices[0].message.content or ""
                reading = full[:200] + ("..." if len(full) > 200 else "")
            except: reading = "AI解读暂时不可用"
        _FREE_IPS.add(ip)
        # Content flywheel: auto-generate chart landing page
        try:
            import sys
            scripts_dir = str(BASE_DIR / "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            from save_chart_page import build_chart_page, add_charts_to_sitemap
            birth_info = {"year": req.year, "month": req.month, "day": req.day, "hour": req.hour, "gender": req.gender}
            pages = build_chart_page(chart, birth_info, reading, req.language, req.city)
            if pages:
                add_charts_to_sitemap()
        except Exception as chart_page_err:
            pass  # silently fail, don't block the user
        return {"success": True, "data": {"chart": chart, "reading": reading, "free_used": False}}
    except Exception as e: return {"success": False, "error": str(e)}

# ─── paipan ──────────────────────────────────────────────────
@app.post("/v1/paipan", response_model=PaiPanResponse)
def paipan(req: PaiPanRequest, key: str = Depends(get_api_key)):
    try:
        chart = run_engine(req.year, req.month, req.day, req.hour, req.gender)
        if not chart.get("success"): return PaiPanResponse(success=False, error="排盘失败")
        reading = ""
        if client:
            try:
                prompt = load_style_prompt(req.style, req.language)
                chart_json = json.dumps(chart, ensure_ascii=False, indent=2)
                city_ctx = get_city_context(req.city, req.language)
                user_msg = f"Please interpret this Zi Wei chart:\n\n{chart_json}{city_ctx}" if req.language == "en" else f"请解读以下紫微斗数命盘：\n\n{chart_json}{city_ctx}"
                resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_msg}], temperature=0.7, max_tokens=2000, timeout=45)
                reading = resp.choices[0].message.content or ""
                it = resp.usage.prompt_tokens if resp.usage else 0
                ot = resp.usage.completion_tokens if resp.usage else 0
                cost = 1
                log_usage(key, "paipan", cost, it, ot); deduct_balance(key, cost)
            except Exception as e:
                reading = f"[AI不可用: {str(e)}]"
                log_usage(key, "paipan", 1)
                deduct_balance(key, 1)
        else:
            log_usage(key, "paipan", 1)
            deduct_balance(key, 1)
        return PaiPanResponse(success=True, data={"chart": chart, "reading": reading})
    except Exception as e: return PaiPanResponse(success=False, error=str(e))

# ─── paipan-only ──────────────────────────────────────────────
@app.post("/v1/paipan-only", response_model=PaiPanResponse)
def paipan_only(req: PaiPanRequest, key: str = Depends(get_api_key)):
    try:
        chart = run_engine(req.year, req.month, req.day, req.hour, req.gender)
        if not chart.get("success"): return PaiPanResponse(success=False, error="排盘失败")
        log_usage(key, "paipan-only", 1)
        deduct_balance(key, 1)
        return PaiPanResponse(success=True, data={"chart": chart})
    except Exception as e: return PaiPanResponse(success=False, error=str(e))

# ─── daily ─────────────────────────────────────────────────
class DailyRequest(BaseModel):
    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: float = Field(..., ge=0, le=23)
    gender: str = Field(..., pattern="^(male|female)$")
    style: str = Field("modern", pattern="^(modern|classical|poetic)$")
    city: str = Field("", max_length=100)
    language: str = Field("zh-Hant", pattern="^(zh-Hant|zh-Hans|en|zh)$")

class DailyResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None

@app.post("/v1/daily", response_model=DailyResponse)
def daily_fortune(req: DailyRequest, key: str = Depends(get_api_key)):
    try:
        today = date.today()
        chart = run_engine(req.year, req.month, req.day, req.hour, req.gender)
        if not chart.get("success"): return DailyResponse(success=False, error="排盘失败")
        lr = jmod.dumps({"year": today.year, "month": today.month, "day": today.day, "hour": 12, "gender": "male"})
        proc = subprocess.run([_NODE, str(ENGINE_PATH)], input=lr, capture_output=True, text=True, timeout=10, cwd=str(BASE_DIR))
        tc = jmod.loads(proc.stdout) if proc.returncode == 0 else {}
        ti = tc.get("基本信息", {})
        context = {"日期": f"{today.year}年{today.month}月{today.day}日", "农历": ti.get("农历",""), "干支": ti.get("八字","").split(" ")[0] if ti.get("八字") else "", "星期": "日一二三四五六"[today.weekday()]}
        city_ctx = get_city_context(req.city, req.language)
        reading = ""
        if client:
            try:
                cj = jmod.dumps({"基本资料": chart.get("基本信息"), "命盘": chart.get("命盘"), "大限": chart.get("大限")}, ensure_ascii=False, indent=2)
                prompt = load_daily_prompt(req.style, req.language)
                user_msg = f"My birth chart:\n{cj}\n\nToday: {context['日期']} ({context['星期']})\nLunar: {context['农历']}\nStem-Branch: {context['干支']}\n{city_ctx}\nAnalyze today's fortune." if req.language == "en" else f"我的命盘：\n{cj}\n\n今天的日期：{context['日期']}（{context['星期']}）\n农历：{context['农历']}\n流日干支：{context['干支']}\n{city_ctx}\n请分析今日运势。"
                resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_msg}], temperature=0.7, max_tokens=800, timeout=45)
                reading = resp.choices[0].message.content or ""
                it = resp.usage.prompt_tokens if resp.usage else 0; ot = resp.usage.completion_tokens if resp.usage else 0
                cost = 1
                log_usage(key, "daily", cost, it, ot); deduct_balance(key, cost)
            except Exception as e:
                reading = f"[AI不可用: {str(e)}]"
                log_usage(key, "daily", 1); deduct_balance(key, 1)
        else:
            log_usage(key, "daily", 1); deduct_balance(key, 1)
        return DailyResponse(success=True, data={"context": context, "reading": reading})
    except Exception as e: return DailyResponse(success=False, error=str(e))

# ─── unsubscribe ──────────────────────────────────────────────
class UnsubRequest(BaseModel):
    email: str

# ─── daxian ─────────────────────────────────────────────────
class DaXianRequest(BaseModel):
    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: float = Field(..., ge=0, le=23)
    gender: str = Field(..., pattern="^(male|female)$")
    style: str = Field("modern", pattern="^(modern|classical|poetic)$")
    city: str = Field("", max_length=100)
    language: str = Field("zh-Hant", pattern="^(zh-Hant|zh-Hans|en|zh)$")

class DaXianResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None

JI_STARS = {'紫微','天府','天相','天梁','太阳','太阴','天同','武曲','左辅','右弼','文昌','文曲','天魁','天钺','禄存'}
SHA_STARS = {'七杀','破军','擎羊','陀罗'}
DI_ZHI = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']

@app.post("/v1/daxian", response_model=DaXianResponse)
def daxian_analysis(req: DaXianRequest, key: str = Depends(get_api_key)):
    try:
        today = date.today()
        chart = run_engine(req.year, req.month, req.day, req.hour, req.gender)
        if not chart.get("success"): return DaXianResponse(success=False, error="排盘失败")
        age = today.year - req.year
        if today.month < req.month or (today.month == req.month and today.day < req.day): age -= 1
        cdx = None
        for dx in chart.get("大限", []):
            a = dx["年龄"].replace("岁","").split("~")
            if int(a[0]) <= age <= int(a[1]): dx["当前年龄"] = age; cdx = dx; break
        if not cdx: return DaXianResponse(success=False, error="无法确定当前大限")
        pn = cdx["大限"]; p = chart.get("命盘",{}).get(pn,{})
        ms = p.get("主星",[]); mis = p.get("辅星",[]); h = p.get("四化",[])
        jl = [s for s in ms+mis if s in JI_STARS] + [x for x in h if x in ('化禄','化权','化科')]
        sl = [s for s in ms+mis if s in SHA_STARS] + [x for x in h if x == '化忌']
        zl = [s for s in ms+mis if s not in JI_STARS and s not in SHA_STARS]
        dd = {"当前年龄":age,"当前大限":pn,"大限年龄范围":cdx["年龄"],"宫位地支":DI_ZHI[p.get("地支",0)],"主星":ms,"辅星":mis,"四化":h,"吉星":jl,"煞星":sl,"中性星":zl,"吉凶评价":"大吉"if len(jl)>=2 and len(sl)==0 else "吉"if len(jl)>len(sl) else "平"if len(jl)==len(sl) else "凶"}
        reading = ""
        if client:
            try:
                prompt = load_daxian_prompt(req.style, req.language)
                city_ctx = get_city_context(req.city, req.language)
                cj = jmod.dumps({"基本资料":chart.get("基本信息"),"当前大限详情":dd}, ensure_ascii=False, indent=2)
                user_msg = f"My chart and current decade:\n{cj}\n\nAnalyze my 10-year pattern - stars, transformations, life advice. {city_ctx}" if req.language == "en" else f"我的命盘和当前大限：\n{cj}\n\n详细分析十年大限格局。{city_ctx}"
                resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role":"system","content":prompt},{"role":"user","content":user_msg}], temperature=0.7, max_tokens=800, timeout=45)
                reading = resp.choices[0].message.content or ""
                it = resp.usage.prompt_tokens if resp.usage else 0; ot = resp.usage.completion_tokens if resp.usage else 0
                cost = 5
                log_usage(key, "daxian", cost, it, ot); deduct_balance(key, cost)
            except:
                reading = "[AI不可用]"
                log_usage(key, "daxian", 5); deduct_balance(key, 5)
        else:
            log_usage(key, "daxian", 5); deduct_balance(key, 5)
        return DaXianResponse(success=True, data={"daxian": dd, "reading": reading})
    except Exception as e: return DaXianResponse(success=False, error=str(e))

# ─── daily-free ──────────────────────────────────────────────
_DAILY_FREE_LIMIT: dict = {}

@app.post("/v1/daily-free")
def daily_free(req: DailyRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    tk = f"{ip}:{date.today().isoformat()}"
    if tk in _DAILY_FREE_LIMIT:
        return {"success": True, "data": {"free_used": True, "context": {}, "reading": '<div style="text-align:center;padding:10px 0"><div style="font-size:32px;margin-bottom:8px">🌅</div><div style="color:#e0c8ff;font-size:16px;font-weight:600;margin-bottom:6px">今日免费运势已使用</div><div style="color:#6a5a8a;font-size:13px;margin-bottom:14px">解锁无限次每日运势</div><a href="/shop.html" target="_blank" style="display:inline-block;padding:10px 24px;background:linear-gradient(135deg,#2a8a5a,#1a6a40);color:#fff;border-radius:10px;text-decoration:none;font-size:14px;font-weight:600;letter-spacing:1px">🛒 购买Key解锁</a></div>'}}
    _DAILY_FREE_LIMIT[tk] = True
    try:
        today = date.today()
        chart = run_engine(req.year, req.month, req.day, req.hour, req.gender)
        tc = {}
        if chart.get("success"):
            lr = jmod.dumps({"year":today.year,"month":today.month,"day":today.day,"hour":12,"gender":"male"})
            r2 = subprocess.run([_NODE,str(ENGINE_PATH)],input=lr,capture_output=True,text=True,timeout=10,cwd=str(BASE_DIR))
            if r2.returncode==0: tc=jmod.loads(r2.stdout)
        ti=tc.get("基本信息",{})
        ctx={"日期":f"{today.year}年{today.month}月{today.day}日","农历":ti.get("农历",""),"干支":ti.get("八字","").split(" ")[0] if ti.get("八字") else "","星期":"日一二三四五六"[today.weekday()]}
        reading=""
        if client:
            try:
                cj=jmod.dumps({"基本资料":chart.get("基本信息"),"命盘":chart.get("命盘"),"大限":chart.get("大限")},ensure_ascii=False,indent=2)
                prompt=load_daily_prompt(req.style, req.language)
                city_ctx=get_city_context(req.city, req.language)
                user_msg=f"My birth chart:\n{cj}\n\nToday: {ctx['日期']} ({ctx['星期']})\nLunar: {ctx['农历']}\nStem-Branch: {ctx['干支']}\n{city_ctx}\nGive today's fortune (200 char preview)." if req.language=="en" else f"我的命盘：\n{cj}\n\n今天的日期：{ctx['日期']}（{ctx['星期']}）\n农历：{ctx['农历']}\n流日干支：{ctx['干支']}\n{city_ctx}\n请给出今日运势分析（前200字精华预览）。"
                resp=client.chat.completions.create(model="deepseek-chat",messages=[{"role":"system","content":prompt},{"role":"user","content":user_msg}],temperature=0.7,max_tokens=400,timeout=45)
                full=resp.choices[0].message.content or ""
                reading=full[:200]+("..." if len(full)>200 else "")+'<div style="margin-top:16px;padding-top:14px;border-top:1px solid rgba(100,255,180,.15);text-align:center"><div style="font-size:12px;color:#5a9a7a;margin-bottom:10px">🔒 免费预览（200字）· 每日1次</div><a href="/shop.html" target="_blank" style="display:inline-block;padding:10px 24px;background:linear-gradient(135deg,#2a8a5a,#1a6a40);color:#fff;border-radius:10px;text-decoration:none;font-size:14px;font-weight:600;letter-spacing:1px">🛒 购买Key解锁完整运势</a></div>'
            except: reading="AI解读暂时不可用"
        return {"success":True,"data":{"context":ctx,"reading":reading,"free_used":False}}
    except Exception as e: return {"success":False,"error":str(e)}

# ─── daxian-free ──────────────────────────────────────────────
_DAXIAN_FREE_LIMIT: set = set()

@app.post("/v1/daxian-free")
def daxian_free(req: DaXianRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if ip in _DAXIAN_FREE_LIMIT:
        return {"success": True, "data": {"daxian": None, "reading": '<div style="text-align:center;padding:10px 0"><div style="font-size:32px;margin-bottom:8px">⏳</div><div style="color:#e0c8ff;font-size:16px;font-weight:600;margin-bottom:6px">免费大限已使用</div><div style="color:#6a5a8a;font-size:13px;margin-bottom:14px">解锁无限次大限详解</div><a href="/shop.html" target="_blank" style="display:inline-block;padding:10px 24px;background:linear-gradient(135deg,#7b68ee,#5a4acd);color:#fff;border-radius:10px;text-decoration:none;font-size:14px;font-weight:600;letter-spacing:1px">🛒 购买Key解锁</a></div>', "free_used": True}}
    try:
        today = date.today()
        chart = run_engine(req.year, req.month, req.day, req.hour, req.gender)
        if not chart.get("success"): return {"success": False, "error": "排盘失败"}
        age = today.year - req.year
        if today.month < req.month or (today.month == req.month and today.day < req.day): age -= 1
        cdx = None
        for dx in chart.get("大限", []):
            a = dx["年龄"].replace("岁","").split("~")
            if int(a[0]) <= age <= int(a[1]): dx["当前年龄"] = age; cdx = dx; break
        if not cdx: return {"success": False, "error": "无法确定当前大限"}
        pn = cdx["大限"]; p = chart.get("命盘",{}).get(pn,{})
        ms = p.get("主星",[]); mis = p.get("辅星",[]); h = p.get("四化",[])
        jl = [s for s in ms+mis if s in JI_STARS] + [x for x in h if x in ('化禄','化权','化科')]
        sl = [s for s in ms+mis if s in SHA_STARS] + [x for x in h if x == '化忌']
        zl = [s for s in ms+mis if s not in JI_STARS and s not in SHA_STARS]
        dd = {"当前年龄":age,"当前大限":pn,"大限年龄范围":cdx["年龄"],"宫位地支":DI_ZHI[p.get("地支",0)],"主星":ms,"辅星":mis,"四化":h,"吉星":jl,"煞星":sl,"中性星":zl,"吉凶评价":"大吉"if len(jl)>=2 and len(sl)==0 else "吉"if len(jl)>len(sl) else "平"if len(jl)==len(sl) else "凶"}
        reading=""
        if client:
            try:
                prompt=load_daxian_prompt(req.style, req.language)
                city_ctx=get_city_context(req.city, req.language)
                cj=jmod.dumps({"基本资料":chart.get("基本信息"),"当前大限详情":dd},ensure_ascii=False,indent=2)
                user_msg=f"My decade period info:\n{cj}{city_ctx}\n\nFirst 200 chars preview." if req.language=="en" else f"我的命盘大限信息：\n{cj}{city_ctx}\n\n请给出前200字精华预览。"
                resp=client.chat.completions.create(model="deepseek-chat",messages=[{"role":"system","content":prompt},{"role":"user","content":user_msg}],temperature=0.7,max_tokens=400,timeout=45)
                full=resp.choices[0].message.content or ""
                reading=full[:200]+("..." if len(full)>200 else "")+'<div style="margin-top:16px;padding-top:14px;border-top:1px solid rgba(255,200,80,.15);text-align:center"><div style="font-size:12px;color:#8a7a5a;margin-bottom:10px">🔒 免费预览（200字）· 仅限1次</div><a href="/shop.html" target="_blank" style="display:inline-block;padding:10px 24px;background:linear-gradient(135deg,#7b68ee,#5a4acd);color:#fff;border-radius:10px;text-decoration:none;font-size:14px;font-weight:600;letter-spacing:1px">🛒 购买Key解锁完整大限解读</a></div>'
            except: reading="AI解读暂时不可用"
        _DAXIAN_FREE_LIMIT.add(ip)
        return {"success":True,"data":{"daxian":dd,"reading":reading,"free_used":False}}
    except Exception as e: return {"success":False,"error":str(e)}

# ─── referral/stats ──────────────────────────────────────────
@app.get("/v1/referral/bonus")
def referral_bonus(key: str = Depends(get_api_key)):
    return {"success": True, "bonus": 0, "message": "推荐好友购买可获10%返利（即将上线）"}

@app.post("/v1/referral/link")
def referral_link(key: str = Depends(get_api_key)):
    return {"success": True, "link": f"/shop.html?ref={key[:8]}"}

@app.get("/v1/stats")
def public_stats():
    tk = db_conn.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]
    tu = db_conn.execute("SELECT COUNT(*) FROM usage_log").fetchone()[0]
    return {"success": True, "data": {"total_keys": tk, "total_calls": tu, "已服务人次": tu}}

@app.get("/v1/lunar")
def get_lunar(year: int, month: int, day: int):
    """阳历转农历（含干支年、生肖）"""
    try:
        from lunarcalendar import Converter, Solar, Lunar
        solar = Solar(year, month, day)
        lunar = Converter.Solar2Lunar(solar)
        # 天干地支计算
        stems = ['甲','乙','丙','丁','戊','己','庚','辛','壬','癸']
        branches = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
        animals = ['🐭鼠','🐮牛','🐯虎','🐰兔','🐲龙','🐍蛇','🐴马','🐏羊','🐵猴','🐔鸡','🐶狗','🐷猪']
        stem_idx = (lunar.year - 4) % 10
        branch_idx = (lunar.year - 4) % 12
        gan = stems[stem_idx]
        zhi = branches[branch_idx]
        animal = animals[branch_idx]
        month_names = ['正月','二月','三月','四月','五月','六月','七月','八月','九月','十月','冬月','腊月']
        day_names = ['初一','初二','初三','初四','初五','初六','初七','初八','初九','初十',
                     '十一','十二','十三','十四','十五','十六','十七','十八','十九','二十',
                     '廿一','廿二','廿三','廿四','廿五','廿六','廿七','廿八','廿九','三十']
        month_name = month_names[lunar.month - 1] if 1 <= lunar.month <= 12 else f'{lunar.month}月'
        day_name = day_names[lunar.day - 1] if 1 <= lunar.day <= 30 else f'{lunar.day}日'
        full_text = f'{gan}{zhi}年 {animal} · {month_name}{day_name}'
        return {"success": True, "data": {
            "lunar_year": lunar.year, "lunar_month": lunar.month, "lunar_day": lunar.day,
            "is_leap": lunar.isleap, "gan": gan, "zhi": zhi, "animal": animal,
            "month_name": month_name, "day_name": day_name,
            "text": full_text, "short": f'农历{lunar.month}月{lunar.day}日'
        }}
    except:
        return {"success": False, "error": "Conversion failed"}

# ─── shop ────────────────────────────────────────────────────
PACKAGES = {"starter":{"name":"探运包","price":9.9,"quota":3,"df":7},"standard":{"name":"知命包","price":29.9,"quota":30,"df":30},"pro":{"name":"掌运包","price":119,"quota":200,"df":90},"enterprise":{"name":"天命包","price":1288,"quota":1888,"df":365}}

# ─── subscription plans ─────────────────────────────────────
SUB_PLANS = {
    "monthly": {"name":"月度星伴","name_en":"Monthly Star","price":5.9,"renew_price":8.9,"days":30},
    "yearly":  {"name":"年度星伴","name_en":"Yearly Star","price":39.9,"renew_price":0,"days":365},
}

class SubscribeRequest(BaseModel):
    email: str = Field(..., max_length=200)
    plan: str = Field(..., pattern="^(monthly|yearly)$")
    name: str = Field("", max_length=50)
    birth_year: int = Field(..., ge=1900, le=2100)
    birth_month: int = Field(..., ge=1, le=12)
    birth_day: int = Field(..., ge=1, le=31)
    birth_hour: float = Field(..., ge=0, le=23)
    gender: str = Field(..., pattern="^(male|female)$")
    language: str = Field("zh", max_length=10)
    source: str = Field("", max_length=100)
    marketing_consent: bool = False

@app.post("/v1/subscribe")
def subscribe(req: SubscribeRequest):
    """订阅每日运势——存储出生信息+创建USDT订单"""
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Invalid email")
    if req.plan not in SUB_PLANS:
        raise HTTPException(400, "Invalid plan")
    sp = SUB_PLANS[req.plan]
    # 金额互斥锁：同一价格同时只能有一笔pending USDT订单
    existing_pending = db_conn.execute(
        "SELECT id FROM orders WHERE amount=? AND pay_method='usdt' AND status='pending' AND datetime(created_at) > datetime('now', '-5 minutes')",
        (sp["price"],)
    ).fetchone()
    if existing_pending:
        raise HTTPException(409, f"当前 ${sp['price']} 的支付订单已在处理中，请等待完成后重试")
    # 创建或更新用户（存储出生信息）
    existing = db_conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        db_conn.execute("UPDATE users SET name=?, birth_year=?, birth_month=?, birth_day=?, birth_hour=?, gender=?, language=?, marketing_consent=?, source=? WHERE email=?",
            (req.name, req.birth_year, req.birth_month, req.birth_day, req.birth_hour, req.gender, req.language, 1 if req.marketing_consent else 0, req.source, email))
    else:
        db_conn.execute("INSERT INTO users (email, name, birth_year, birth_month, birth_day, birth_hour, gender, language, marketing_consent, source) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (email, req.name, req.birth_year, req.birth_month, req.birth_day, req.birth_hour, req.gender, req.language, 1 if req.marketing_consent else 0, req.source))
    db_conn.commit()
    # 创建USDT订单（pending状态，等待链上确认）
    oid = f"SUB{secrets.token_hex(8)}"
    db_conn.execute("INSERT INTO orders (id, package, amount, pay_method, status, buyer_email, source, marketing_consent) VALUES (?,?,?,?,?,?,?,?)",
        (oid, "sub_"+req.plan, sp["price"], "usdt", "pending", email, req.source, 1 if req.marketing_consent else 0))
    db_conn.commit()
    return {
        "success": True, "data": {
            "order_id": oid,
            "amount": sp["price"],
            "wallet": USDT_WALLET,
            "plan": req.plan,
        }
    }

# ─── register ──────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=200)
    name: str = Field("", max_length=50)
    birth_year: int = Field(..., ge=1900, le=2100)
    birth_month: int = Field(..., ge=1, le=12)
    birth_day: int = Field(..., ge=1, le=31)
    birth_hour: float = Field(..., ge=0, le=23)
    gender: str = Field(..., pattern="^(male|female)$")
    city: str = Field("", max_length=100)
    language: str = Field("zh", max_length=10)

@app.post("/v1/register")
def register(req: RegisterRequest, request: Request):
    """注册用户：创建账号 + 赠试用Key + 返回排盘数据"""
    email = req.email.strip().lower()
    ip = request.client.host if request.client else "unknown"

    # 检查邮箱是否已注册
    existing = db_conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        raise HTTPException(400, "该邮箱已注册，请直接登录")

    # 创建用户
    cursor = db_conn.execute(
        "INSERT INTO users (email, name, birth_year, birth_month, birth_day, birth_hour, gender, city, language) VALUES (?,?,?,?,?,?,?,?,?)",
        (email, req.name.strip(), req.birth_year, req.birth_month, req.birth_day, req.birth_hour, req.gender, req.city.strip(), req.language)
    )
    user_id = cursor.lastrowid
    db_conn.commit()

    # 生成试用Key（3次解读）
    trial_key = "zw_" + secrets.token_hex(16)
    db_conn.execute("INSERT INTO api_keys (key, name, balance) VALUES (?,?,?)", (trial_key, f"注册试用-{req.name or email}", 3))
    db_conn.commit()

    # 排盘
    chart = run_engine(req.birth_year, req.birth_month, req.birth_day, req.birth_hour, req.gender)

    return {
        "success": True,
        "data": {
            "user_id": user_id,
            "email": email,
            "name": req.name,
            "trial_key": trial_key,
            "chart": chart if chart.get("success") else None,
        }
    }


@app.get("/v1/packages")
def get_packages():
    return {"success":True,"data":PACKAGES}

@app.post("/v1/key/create")
def create_key(req: KeyCreateRequest):
    k = "zw_" + secrets.token_hex(16)
    db_conn.execute("INSERT INTO api_keys (key, name, balance) VALUES (?,?,?)",(k,req.name,req.quota))
    db_conn.commit()
    return {"success":True,"data":{"key":k,"balance":req.quota}}

@app.post("/v1/order/create")
def create_order(package: str, pay_method: str = "stripe"):
    if package not in PACKAGES: raise HTTPException(400,"Invalid")
    pkg = PACKAGES[package]
    oid = f"ORD{secrets.token_hex(16)}"
    db_conn.execute("INSERT INTO orders (id, package, amount, pay_method) VALUES (?,?,?,?)",(oid,package,pkg["price"],pay_method))
    db_conn.commit()
    return {"success":True,"data":{"order_id":oid,"amount":pkg["price"],"package":package,"package_name":pkg["name"]}}

@app.post("/v1/order/pay")
def pay_order(order_id: str):
    o = db_conn.execute("SELECT * FROM orders WHERE id=?",(order_id,)).fetchone()
    if not o: raise HTTPException(404,"Not found")
    if o[5] != "pending": raise HTTPException(400,"Already paid")
    pkg = PACKAGES.get(o[2])
    if not pkg: raise HTTPException(400,"Invalid package")
    k = "zw_" + secrets.token_hex(16)
    db_conn.execute("INSERT INTO api_keys (key, name, balance) VALUES (?,?,?)",(k,f"自动创建-{pkg['name']}",pkg["quota"]))
    db_conn.execute("UPDATE orders SET status='paid', api_key=?, paid_at=datetime('now') WHERE id=?",(k,order_id))
    db_conn.commit()
    return {"success":True,"data":{"key":k,"quota":pkg["quota"],"package":pkg["name"]}}

@app.get("/v1/key/balance")
def check_balance(key: str = Depends(get_api_key)):
    r = db_conn.execute("SELECT balance FROM api_keys WHERE key=?",(key,)).fetchone()
    return {"success":True,"balance":r[0] if r else 0}

@app.get("/v1/usage")
def check_usage(key: str = Depends(get_api_key), limit: int = 20):
    rs = db_conn.execute("SELECT endpoint, cost, created_at FROM usage_log WHERE api_key=? ORDER BY created_at DESC LIMIT ?",(key,limit)).fetchall()
    return {"success":True,"data":[{"endpoint":r[0],"cost":r[1],"time":r[2]} for r in rs]}

@app.get("/v1/redeem")
def redeem(code: str):
    q = {"TEST10":10,"VIP50":50}.get(code)
    if not q: raise HTTPException(400,"Invalid code")

@app.post("/v1/checkout/stripe")
def stripe_checkout(package: str):
    if package not in PACKAGES: raise HTTPException(400,"Invalid package")
    pkg = PACKAGES[package]
    if not STRIPE_SECRET_KEY:
        return {"success":False,"error":"Stripe not configured","mock":True,"package":package}
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        oid = f"ORD{secrets.token_hex(16)}"
        db_conn.execute("INSERT INTO orders (id, package, amount, pay_method) VALUES (?,?,?,?)",(oid,package,pkg["price"],"stripe"))
        db_conn.commit()
        session = stripe.checkout.Session.create(
            line_items=[{"price_data":{"currency":"usd","product_data":{"name":f"{pkg['name']} - {pkg['quota']} calls"},"unit_amount":int(pkg["price"]*100)},"quantity":1}],
            mode="payment",
            success_url=f"{BASE_URL}/shop.html?order_id={oid}&success=1",
            cancel_url=f"{BASE_URL}/shop.html",
            metadata={"order_id":oid,"package":package}
        )
        return {"success":True,"data":{"url":session.url,"order_id":oid,"amount":pkg["price"],"package":package}}
    except Exception as e:
        return {"success":False,"error":str(e)}

@app.post("/v1/checkout/lemonsqueezy")
def lemonsqueezy_checkout(package: str):
    if package not in PACKAGES: raise HTTPException(400,"Invalid package")
    pkg = PACKAGES[package]
    if not LEMONSQUEEZY_API_KEY:
        return {"success":False,"error":"LemonSqueezy not configured","mock":True,"package":package}
    try:
        import requests
        oid = f"ORD{secrets.token_hex(16)}"
        db_conn.execute("INSERT INTO orders (id, package, amount, pay_method) VALUES (?,?,?,?)",(oid,package,pkg["price"],"lemonsqueezy"))
        db_conn.commit()
        headers = {"Accept":"application/vnd.api+json","Content-Type":"application/vnd.api+json","Authorization":f"Bearer {LEMONSQUEEZY_API_KEY}"}
        body = {"data":{"type":"checkouts","attributes":{"product_options":{"redirect_url":f"{BASE_URL}/shop.html?order_id={oid}&success=1"},"checkout_data":{"custom":{"order_id":oid}}},"relationships":{"store":{"data":{"type":"stores","id":LEMONSQUEEZY_STORE_ID}}}}}
        r = requests.post("https://api.lemonsqueezy.com/v1/checkouts",json=body,headers=headers,timeout=10)
        d = r.json()
        url = d.get("data",{}).get("attributes",{}).get("url","")
        if url:
            return {"success":True,"data":{"url":url,"order_id":oid,"amount":pkg["price"],"package":package}}
        return {"success":False,"error":"Failed to create LemonSqueezy checkout"}
    except Exception as e:
        return {"success":False,"error":str(e)}


def _activate_df_gift(email: str, days: int, plan_label: str = "gift"):
    """购买套餐后，激活赠送的每日运势订阅"""
    try:
        email = email.strip().lower()
        if not email or "@" not in email: return
        end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        existing = db_conn.execute("SELECT id FROM subscriptions WHERE email=?", (email,)).fetchone()
        if existing:
            db_conn.execute(
                "UPDATE subscriptions SET plan=?, status='active', subscribed_at=datetime('now'), end_date=? WHERE email=?",
                (plan_label, end_date, email))
        else:
            db_conn.execute(
                "INSERT INTO subscriptions (email, plan, status, end_date) VALUES (?,?,?,?)",
                (email, plan_label, 'active', end_date))
        db_conn.commit()
        # Detect user language
        user = db_conn.execute("SELECT language FROM users WHERE email=?", (email,)).fetchone()
        is_en = user and user[0] and user[0].startswith("en")
        # Send bilingual welcome email
        subject = f"🎉 Daily Fortune Activated · {days}-day Gift" if is_en else f"🎉 每日运势已激活 · 赠送{days}天"
        body_zh = f"""<div style="max-width:560px;margin:0 auto;font-family:'PingFang SC','Microsoft YaHei',sans-serif;background:#1a1210;color:#f0e0c8;padding:30px;border-radius:16px">
<div style="font-size:40px;text-align:center;margin-bottom:10px">🌅</div>
<h2 style="text-align:center;color:#f0c060;margin-bottom:8px">每日运势已激活！</h2>
<p style="text-align:center;color:#9a7850;font-size:13px;margin-bottom:20px">你购买的套餐赠送了 {days} 天每日运势推送</p>
<div style="background:#1e1612;border:1px solid #3a2a1e;border-radius:12px;padding:20px;margin-bottom:16px">
<p style="margin:4px 0;font-size:14px;color:#e0d0b8">✅ 每天一封运势邮件推送到此邮箱</p>
<p style="margin:4px 0;font-size:14px;color:#e0d0b8">📅 有效期至：{end_date[:10]}</p>
<p style="margin:4px 0;font-size:14px;color:#e0d0b8">🔔 到期前会有续费提醒</p>
</div>
<p style="text-align:center;font-size:12px;color:#5a4020">紫微斗数 · 仅供娱乐参考</p>
</div>"""
        body_en = f"""<div style="max-width:560px;margin:0 auto;font-family:system-ui,-apple-system,sans-serif;background:#1a1210;color:#f0e0c8;padding:30px;border-radius:16px">
<div style="font-size:40px;text-align:center;margin-bottom:10px">🌅</div>
<h2 style="text-align:center;color:#f0c060;margin-bottom:8px">Daily Fortune Activated!</h2>
<p style="text-align:center;color:#9a7850;font-size:13px;margin-bottom:20px">Your package includes a {days}-day daily fortune subscription</p>
<div style="background:#1e1612;border:1px solid #3a2a1e;border-radius:12px;padding:20px;margin-bottom:16px">
<p style="margin:4px 0;font-size:14px;color:#e0d0b8">✅ Daily fortune sent to your email every morning</p>
<p style="margin:4px 0;font-size:14px;color:#e0d0b8">📅 Valid until: {end_date[:10]}</p>
<p style="margin:4px 0;font-size:14px;color:#e0d0b8">🔔 Renewal reminder before expiry</p>
</div>
<p style="text-align:center;font-size:12px;color:#5a4020">Zi Wei Dou Shu · For entertainment only</p>
</div>"""
        body = body_en if is_en else body_zh
        send_email(email, subject, body)
    except Exception as e:
        print(f"[df_gift] Error activating for {email}: {e}")


@app.post("/v1/checkout/mock")
def mock_checkout(package: str = Body(None, embed=True), buyer_email: str = "", buyer_name: str = ""):
    """Mock checkout - creates key without real payment (for demo)"""
    if not package: raise HTTPException(400, "package is required")
    if package not in PACKAGES: raise HTTPException(400,"Invalid package")
    pkg = PACKAGES[package]
    oid = f"ORD{secrets.token_hex(16)}"
    db_conn.execute("INSERT INTO orders (id, package, amount, pay_method, status, buyer_email) VALUES (?,?,?,?,?,?)",(oid,package,pkg["price"],"mock","paid",buyer_email))
    k = "zw_" + secrets.token_hex(16)
    db_conn.execute("INSERT INTO api_keys (key, name, balance) VALUES (?,?,?)",(k,f"Mock-{pkg['name']}",pkg["quota"]))
    db_conn.execute("UPDATE orders SET status='paid', api_key=?, paid_at=datetime('now') WHERE id=?",(k,oid))
    db_conn.commit()
    # Activate daily fortune gift
    if buyer_email and pkg.get("df", 0) > 0:
        _activate_df_gift(buyer_email, pkg["df"], f"gift_{pkg['name']}")
    return {"success":True,"data":{"key":k,"quota":pkg["quota"],"package":pkg["name"],"order_id":oid,"mock":True}}

# ─── PayPal helper ──────────────────────────────────────────
def _paypal_get_token():
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        return None
    import base64, requests
    auth = base64.b64encode(f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}".encode()).decode()
    r = requests.post(f"{PAYPAL_API}/v1/oauth2/token",
        headers={"Authorization":f"Basic {auth}","Accept":"application/json"},
        data={"grant_type":"client_credentials"}, timeout=10)
    return r.json().get("access_token") if r.ok else None

def _paypal_create_order(amount: float, desc: str, oid: str):
    """Create PayPal order, return approval URL or None"""
    token = _paypal_get_token()
    if not token:
        return None  # fallback to mock
    import requests, json
    r = requests.post(f"{PAYPAL_API}/v2/checkout/orders",
        headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},
        json={
            "intent":"CAPTURE",
            "purchase_units":[{"reference_id":oid,"description":desc,"amount":{"currency_code":"USD","value":f"{amount:.2f}"}}],
            "payment_source":{"paypal":{"experience_context":{"return_url":f"{BASE_URL}/shop.html?order_id={oid}&success=1","cancel_url":f"{BASE_URL}/shop.html"}}}
        }, timeout=10)
    if r.ok:
        data = r.json()
        for link in data.get("links",[]):
            if link.get("rel") == "payer-action":
                return link["href"]
    return None

# ─── PayPal 套餐支付 ─────────────────────────────────────────
@app.post("/v1/checkout/paypal")
def paypal_checkout(package: str, buyer_email: str = "", buyer_name: str = ""):
    if package not in PACKAGES: raise HTTPException(400,"Invalid package")
    pkg = PACKAGES[package]
    oid = f"ORD{secrets.token_hex(16)}"
    db_conn.execute("INSERT INTO orders (id, package, amount, pay_method, buyer_email) VALUES (?,?,?,?,?)",(oid,package,pkg["price"],"paypal",buyer_email))
    db_conn.commit()
    # Try real PayPal
    url = _paypal_create_order(pkg["price"], f"{pkg['name']} - {pkg['quota']} calls", oid)
    if url:
        return {"success":True,"data":{"url":url,"order_id":oid,"amount":pkg["price"],"package":package}}
    # Mock mode (PayPal not configured yet)
    mock_url = f"{BASE_URL}/shop.html?order_id={oid}&success=1"
    return {"success":True,"data":{"url":mock_url,"order_id":oid,"amount":pkg["price"],"package":package,"mock":True}}

@app.post("/v1/checkout/paypal-return")
def paypal_return(order_id: str):
    o = db_conn.execute("SELECT * FROM orders WHERE id=?",(order_id,)).fetchone()
    if not o: return {"success":False,"error":"Not found"}
    if o[5] == "paid":
        return {"success":True,"data":{"key":o[6],"package":o[2],"quota":PACKAGES.get(o[2],{}).get("quota",0)}}
    pkg = PACKAGES.get(o[2])
    if not pkg: return {"success":False,"error":"Invalid package"}
    k = "zw_" + secrets.token_hex(16)
    db_conn.execute("INSERT INTO api_keys (key, name, balance) VALUES (?,?,?)",(k,f"PayPal-{pkg['name']}",pkg["quota"]))
    db_conn.execute("UPDATE orders SET status='paid', api_key=?, paid_at=datetime('now') WHERE id=?",(k,order_id))
    db_conn.commit()
    # Activate daily fortune gift using buyer_email stored in order (column index 9 after migration)
    buyer_email = o[9] if len(o) > 9 else ""
    if buyer_email and pkg.get("df", 0) > 0:
        _activate_df_gift(buyer_email, pkg["df"], f"gift_{pkg['name']}")
    return {"success":True,"data":{"key":k,"quota":pkg["quota"],"package":pkg["name"]}}

# ─── PayPal 订阅支付 ─────────────────────────────────────────
class SubPayPalRequest(BaseModel):
    plan: str
    email: str
    name: str = ""
    birth_year: str = ""
    birth_month: str = ""
    birth_day: str = ""
    birth_hour: str = ""
    birth_gender: str = ""

@app.post("/v1/checkout/subscribe-paypal")
def subscribe_paypal_checkout(req: SubPayPalRequest):
    plan = req.plan
    email = req.email.strip().lower()
    if plan not in SUB_PLANS: raise HTTPException(400,"Invalid plan")
    if not email or "@" not in email: raise HTTPException(400,"Invalid email")
    sp = SUB_PLANS[plan]
    oid = f"SUB{secrets.token_hex(16)}"
    # Add columns if missing
    try: db_conn.execute("ALTER TABLE orders ADD COLUMN buyer_name TEXT")
    except: pass
    try: db_conn.execute("ALTER TABLE orders ADD COLUMN sub_birth_info TEXT")
    except: pass
    birth_info = json.dumps({"year":req.birth_year,"month":req.birth_month,"day":req.birth_day,"hour":req.birth_hour,"gender":req.birth_gender})
    db_conn.execute("INSERT INTO orders (id, package, amount, pay_method, buyer_email, buyer_name) VALUES (?,?,?,?,?,?)",(oid,"sub_"+plan,sp["price"],"paypal",email,req.name))
    db_conn.execute("UPDATE orders SET sub_birth_info=? WHERE id=?",(birth_info,oid))
    db_conn.commit()
    url = _paypal_create_order(sp["price"], f"Daily Fortune - {sp['name_en']}", oid)
    if url:
        return {"success":True,"data":{"url":url,"order_id":oid,"amount":sp["price"],"plan":plan}}
    # Mock mode
    mock_url = f"{BASE_URL}/shop.html?order_id={oid}&success=1&sub_email={email}&sub_plan={plan}&sub_name={req.name}&sub_by={req.birth_year}&sub_bm={req.birth_month}&sub_bd={req.birth_day}&sub_bh={req.birth_hour}&sub_bg={req.birth_gender}"
    return {"success":True,"data":{"url":mock_url,"order_id":oid,"amount":sp["price"],"plan":plan,"mock":True}}

@app.post("/v1/checkout/subscribe-return")
def subscribe_return(order_id: str, sub_email: str = "", sub_plan: str = ""):
    o = db_conn.execute("SELECT * FROM orders WHERE id=?",(order_id,)).fetchone()
    if not o: return {"success":False,"error":"Order not found"}
    if o[5] != "pending":
        return {"success":True,"data":{"email":sub_email,"plan":sub_plan,"status":"already_paid"}}
    plan = sub_plan or o[2].replace("sub_","")
    email = sub_email
    sp = SUB_PLANS.get(plan)
    if not sp: return {"success":False,"error":"Invalid plan"}
    end_date = (datetime.now() + timedelta(days=sp["days"])).strftime("%Y-%m-%d %H:%M:%S")
    db_conn.execute("UPDATE orders SET status='paid', paid_at=datetime('now') WHERE id=?",(order_id,))
    if email:
        existing = db_conn.execute("SELECT * FROM subscriptions WHERE email=?",(email,)).fetchone()
        if existing:
            db_conn.execute("UPDATE subscriptions SET plan=?, status='active', subscribed_at=datetime('now'), end_date=? WHERE email=?",(plan,end_date,email))
        else:
            db_conn.execute("INSERT INTO subscriptions (email, plan, status, end_date) VALUES (?,?,?,?)",(email,plan,'active',end_date))
        db_conn.commit()
    return {"success":True,"data":{"email":email,"plan":plan,"end_date":end_date,"status":"active"}}

@app.post("/v1/webhook/stripe")
async def stripe_webhook(request: Request):
    if not STRIPE_WEBHOOK_SECRET:
        return {"error":"Webhook not configured"}
    import stripe
    payload = await request.body()
    sig = request.headers.get("stripe-signature","")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        if event["type"] == "checkout.session.completed":
            sess = event["data"]["object"]
            oid = sess["metadata"]["order_id"]
            pkg_name = sess["metadata"]["package"]
            pkg = PACKAGES.get(pkg_name)
            if not pkg: return {"error":"Invalid package"}
            k = "zw_" + secrets.token_hex(16)
            db_conn.execute("INSERT INTO api_keys (key, name, balance) VALUES (?,?,?)",(k,f"Stripe-{pkg['name']}",pkg["quota"]))
            db_conn.execute("UPDATE orders SET status='paid', api_key=?, paid_at=datetime('now') WHERE id=?",(k,oid))
            db_conn.commit()
        return {"received":True}
    except Exception as e:
        return {"error":str(e)}

@app.post("/v1/webhook/lemonsqueezy")
async def lemonsqueezy_webhook(request: Request):
    body = await request.json()
    try:
        evt_name = body.get("meta",{}).get("event_name","")
        if "order_created" in evt_name:
            custom = body.get("data",{}).get("attributes",{}).get("first_order_item",{}).get("product_options",{}).get("custom",{})
            oid = custom.get("order_id","")
            if oid:
                o = db_conn.execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone()
                if o and o[5] == "pending":
                    pkg = PACKAGES.get(o[2])
                    if pkg:
                        k = "zw_" + secrets.token_hex(16)
                        db_conn.execute("INSERT INTO api_keys (key, name, balance) VALUES (?,?,?)",(k,f"LS-{pkg['name']}",pkg["quota"]))
                        db_conn.execute("UPDATE orders SET status='paid', api_key=?, paid_at=datetime('now') WHERE id=?",(k,oid))
                        db_conn.commit()
        return {"received":True}
    except Exception as e:
        return {"error":str(e)}


# Rate limiter: max 5 order status lookups per IP per minute
_order_status_limits = {}
def _check_order_rate(ip: str):
    now = __import__("time").time()
    if ip in _order_status_limits:
        last, count = _order_status_limits[ip]
        if now - last < 60:
            if count >= 5:
                raise HTTPException(429, "Too many requests. Try again later.")
            _order_status_limits[ip] = (last, count + 1)
        else:
            _order_status_limits[ip] = (now, 1)
    else:
        _order_status_limits[ip] = (now, 1)
@app.get("/v1/order/status")
def order_status(order_id: str, request: Request):
    # Rate limit: max 5 lookups per IP per minute
    client_ip = request.client.host if request.client else "unknown"
    _check_order_rate(client_ip)
    o = db_conn.execute("SELECT * FROM orders WHERE id=?",(order_id,)).fetchone()
    if not o: return {"success":False,"error":"Not found"}
    pkg = PACKAGES.get(o[2])
    return {"success":True,"data":{"status":o[5],"api_key":o[6],"package":o[2],"amount":o[3],"quota":pkg["quota"] if pkg else 0}}

@app.post("/v1/unsubscribe")
def unsubscribe(req: UnsubRequest):
    try:
        email = req.email.strip().lower()
        if not email:
            return {"success": False, "error": "Email is required"}
        db_conn.execute("UPDATE users SET is_active=0 WHERE email=?", (email,))
        db_conn.execute("""
            UPDATE subscriptions SET status='cancelled', cancelled_at=datetime('now')
            WHERE user_id=(SELECT id FROM users WHERE email=?) AND status IN ('active','trial')
        """, (email,))
        db_conn.commit()
        return {"success": True, "data": {"email": email, "status": "unsubscribed"}}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── 每日运势推送（供 cron 调用） ─────────────────────────
def _generate_daily_fortune(year: int, month: int, day: int, hour: float, gender: str, city: str = "", language: str = "zh-Hant") -> str:
    """生成单用户每日运势HTML"""
    chart = run_engine(year, month, day, hour, gender)
    if not chart.get("success"): return ""
    today = date.today()
    lr = json.dumps({"year": today.year, "month": today.month, "day": today.day, "hour": 12, "gender": "male"})
    proc = subprocess.run([_NODE, str(ENGINE_PATH)], input=lr, capture_output=True, text=True, timeout=10, cwd=str(BASE_DIR))
    tc = json.loads(proc.stdout) if proc.returncode == 0 else {}
    ti = tc.get("基本信息", {})
    context = {"日期": f"{today.year}年{today.month}月{today.day}日", "农历": ti.get("农历",""), "干支": ti.get("八字","").split(" ")[0] if ti.get("八字") else "", "星期": "日一二三四五六"[today.weekday()]}
    city_ctx = get_city_context(city, language)
    style = "modern"
    lang = "zh-Hant" if language in ("zh-Hant","zh") else "en"
    prompt = load_daily_prompt(style, language)
    user_msg = f"My birth chart:\n{json.dumps(chart, ensure_ascii=False, indent=2)}\n\nToday: {context['日期']} ({context['星期']})\nLunar: {context['农历']}\nStem-Branch: {context['干支']}\n{city_ctx}\nAnalyze today's fortune." if lang == "en" else f"我的命盘：\n{json.dumps(chart, ensure_ascii=False, indent=2)}\n\n今天的日期：{context['日期']}（{context['星期']}）\n农历：{context['农历']}\n流日干支：{context['干支']}\n{city_ctx}\n请分析今日运势。"
    reading = ""
    from openai import OpenAI
    ai_key = os.getenv("DEEPSEEK_API_KEY", "")
    if ai_key and ai_key != "***":
        llm = OpenAI(api_key=ai_key, base_url="https://api.deepseek.com")
        try:
            resp = llm.chat.completions.create(model="deepseek-chat", messages=[{"role":"system","content":prompt},{"role":"user","content":user_msg}], temperature=0.7, max_tokens=600, timeout=30)
            reading = resp.choices[0].message.content or ""
        except:
            reading = "运势生成暂不可用，请稍后再试。" if not lang == "en" else "Fortune generation unavailable. Please try again later."
    else:
        reading = "今日运势：宜保持积极心态，关注人际关系。紫色系有利。出行注意安全。" if not lang == "en" else "Today's fortune: Stay positive and focus on relationships. Purple shades bring luck. Travel safely."
    is_en = lang == "en"
    if is_en:
        day_names_en = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        html = f"""<div style="max-width:560px;margin:0 auto;font-family:system-ui,-apple-system,sans-serif;background:#1a1210;color:#f0e0c8;padding:30px;border-radius:16px">
<div style="text-align:center;margin-bottom:16px">
<div style="font-size:32px;margin-bottom:4px">🌅</div>
<div style="font-size:20px;font-weight:700;color:#f0c060">{today.year}/{today.month}/{today.day} {day_names_en[today.weekday()]}</div>
<div style="font-size:13px;color:#9a7850;margin-top:2px">Your Daily Fortune</div>
</div>
<div style="background:#1e1612;border:1px solid #3a2a1e;border-radius:12px;padding:20px;line-height:1.8;font-size:14px">{reading}</div>
<div style="text-align:center;margin-top:16px;font-size:11px;color:#5a4020">Zi Wei Dou Shu · For entertainment only<br>Reply to unsubscribe</div>
</div>"""
    else:
        day_names = ["日", "一", "二", "三", "四", "五", "六"]
        html = f"""<div style="max-width:560px;margin:0 auto;font-family:'PingFang SC','Microsoft YaHei',sans-serif;background:#1a1210;color:#f0e0c8;padding:30px;border-radius:16px">
<div style="text-align:center;margin-bottom:16px">
<div style="font-size:32px;margin-bottom:4px">🌅</div>
<div style="font-size:20px;font-weight:700;color:#f0c060">{today.year}年{today.month}月{today.day}日 星期{day_names[today.weekday()]}</div>
<div style="font-size:13px;color:#9a7850;margin-top:2px">{context['农历']} · {context['干支']}</div>
</div>
<div style="background:#1e1612;border:1px solid #3a2a1e;border-radius:12px;padding:20px;line-height:1.8;font-size:14px">{reading}</div>
<div style="text-align:center;margin-top:16px;font-size:11px;color:#5a4020">紫微斗数 · 仅供娱乐参考<br>如需退订请回复邮件</div>
</div>"""
    return html


@app.post("/v1/daily-push")
def daily_push():
    """推送今日运势给所有活跃订阅用户（供 cron 调用）"""
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = db_conn.execute(
            "SELECT s.email, s.plan, u.birth_year, u.birth_month, u.birth_day, u.birth_hour, u.gender, u.city, COALESCE(u.language,'zh') as lang "
            "FROM subscriptions s LEFT JOIN users u ON s.email=u.email "
            "WHERE s.status='active' AND (s.end_date IS NULL OR s.end_date > ?)", (now,)).fetchall()
        sent = 0
        failed = 0
        for row in rows:
            email, plan, by, bm, bd, bh, gender, city, lang = row
            # Skip if no birth data
            if not all([by, bm, bd, bh, gender]):
                print(f"[daily_push] Skipping {email}: no birth data")
                failed += 1
                continue
            try:
                html = _generate_daily_fortune(int(by), int(bm), int(bd), float(bh), gender, city or "", lang)
                if not html:
                    failed += 1
                    continue
                is_en = lang and lang.startswith("en")
                subject = f"🌅 Your Daily Fortune - {date.today().month}/{date.today().day}" if is_en else f"🌅 {date.today().month}月{date.today().day}日 · 你的每日运势已送达"
                ok = send_email(email, subject, html)
                if ok: sent += 1
                else: failed += 1
            except Exception as e:
                print(f"[daily_push] Error for {email}: {e}")
                failed += 1
        return {"success": True, "data": {"sent": sent, "failed": failed, "total": len(rows)}}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/v1/config")
def get_config():
    """返回前端需要的配置信息"""
    return {"success": True, "data": {
        "paypal_email": "",
        "paypal_client_id": PAYPAL_CLIENT_ID or "",
        "mock_mode": not bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET),
    }}


# ─── SEO Scan Credits ─────────────────────────────────
SEO_PACKAGES = {
    "seo_starter": {"name": "Starter Pack", "price": 14.9, "scans": 5},
    "seo_growth": {"name": "Growth Pack", "price": 49, "scans": 25},
    "seo_pro": {"name": "Pro Pack", "price": 149, "scans": 150},
    "seo_monthly": {"name": "Weekly Subscription", "price": 9.9, "scans": 0},
}

@app.post("/v1/seo/checkout")
async def seo_checkout(request: Request, package: str = Body(..., embed=True), buyer_email: str = Body("", embed=True)):
    """Purchase SEO scan credits. Returns a seo_xxx key."""
    if package not in SEO_PACKAGES:
        raise HTTPException(400, f"Invalid package: {package}")
    pkg = SEO_PACKAGES[package]
    if not buyer_email or "@" not in buyer_email:
        raise HTTPException(400, "Valid email is required")
    buyer_email = buyer_email.strip().lower()
    ip = request.client.host if request.client else "unknown"
    oid = f"SEO{secrets.token_hex(8)}"
    k = "seo_" + secrets.token_hex(16)
    db_conn.execute("INSERT INTO api_keys (key, name, balance) VALUES (?,?,?)",
        (k, f"SEO-{pkg['name']}", pkg["scans"]))
    db_conn.execute("INSERT INTO orders (id, package, amount, pay_method, status, api_key, paid_at, buyer_email) VALUES (?,?,?,?,?,?,datetime('now'),?)",
        (oid, package, pkg["price"], "seo", "paid", k, buyer_email))
    db_conn.commit()
    # Send email with key
    if SMTP_HOST and SMTP_USER and SMTP_PASS and buyer_email:
        try:
            html = f"""<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px">
<h2 style="color:#89b4fa">🔍 Your SEO Audit Key</h2>
<p style="color:#cdd6f4">Package: <strong>{pkg['name']}</strong></p>
<p style="color:#cdd6f4">Scans: <strong>{pkg['scans']}</strong></p>
<div style="background:#1e1e2e;border:1px solid #313244;border-radius:8px;padding:12px;margin:16px 0;text-align:center">
<code style="font-size:16px;color:#a6e3a1">{k}</code>
</div>
<p style="color:#585b70;font-size:13px">Use this key on <a href="https://seo.textools.site" style="color:#89b4fa">seo.textools.site</a> to run full audits and register URLs for weekly monitoring.</p>
<hr style="border:none;border-top:1px solid #313244;margin:16px 0">
<p style="color:#45475a;font-size:11px">Order: {oid} · seo.textools.site</p>
</div>"""
            from email.mime.multipart import MIMEMultipart
            msg = MIMEMultipart('alternative')
            msg['From'] = f"SEO Audit <{SMTP_FROM}>"
            msg['To'] = buyer_email
            msg['Subject'] = f"Your SEO Audit Key — {pkg['name']}"
            msg.attach(MIMEText(html, 'html', 'utf-8'))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        except Exception as e:
            print(f"[seo] Email failed: {e}")
    return {"success": True, "data": {"key": k, "scans": pkg["scans"], "package": pkg["name"], "order_id": oid}}

@app.post("/v1/seo/audit")
async def seo_paid_audit(request: Request):
    """Run a paid SEO audit. Deducts 1 scan from key balance."""
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        api_key = body.get("key", "").strip()
        if not url:
            return {"success": False, "error": "URL is required"}
        if not api_key:
            return {"success": False, "error": "API key is required"}
        if not api_key.startswith("seo_"):
            return {"success": False, "error": "Invalid SEO key"}
        cur = db_conn.execute("SELECT balance, active FROM api_keys WHERE key=?", (api_key,))
        row = cur.fetchone()
        if not row:
            return {"success": False, "error": "Key not found"}
        if not row[1]:
            return {"success": False, "error": "Key is disabled"}
        if row[0] < 1:
            return {"success": False, "error": "Insufficient scans. Purchase more credits."}
        result = _run_seo_audit(url)
        db_conn.execute("UPDATE api_keys SET balance = balance - 1 WHERE key=?", (api_key,))
        db_conn.commit()
        result["scan_balance"] = row[0] - 1
        # Save anonymized audit data
        try:
            summary = result.get("summary", {})
            issues_list = result.get("issues", [])
            domain_hash = hashlib.md5(url.split("//")[-1].split("/")[0].encode()).hexdigest()[:8]
            high = sum(1 for i in issues_list if i.get("severity") == "high")
            med = sum(1 for i in issues_list if i.get("severity") == "medium")
            low = sum(1 for i in issues_list if i.get("severity") == "low")
            content_type = "paid"
            db_conn.execute("""INSERT INTO audit_logs (domain_hash, score, total_checks, passed, warnings, failed, high_issues, med_issues, low_issues, word_count, content_type) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (domain_hash, result.get("score", 0), summary.get("total_checks", 0), summary.get("passed", 0), summary.get("warnings", 0), summary.get("failed", 0), high, med, low, summary.get("word_count", 0), content_type))
            db_conn.commit()
        except Exception as e:
            print(f"[audit_log] Save failed: {e}")
        # Log scan for anti-abuse tracking
        try:
            client_ip = request.client.host if request.client else ""
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
            db_conn.execute("INSERT INTO scan_logs (key_hash, url, score, ip) VALUES (?,?,?,?)",
                (key_hash, url, result.get("score", 0), client_ip))
            db_conn.commit()
        except Exception as e:
            print(f"[scan_log] Save failed: {e}")
        return {"success": True, "report": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/v1/seo/register")
async def seo_register_url(request: Request):
    """Register a URL for weekly auto-scans. Deducts first scan."""
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        api_key = body.get("key", "").strip()
        if not url or not api_key:
            return {"success": False, "error": "URL and key are required"}
        if not api_key.startswith("seo_"):
            return {"success": False, "error": "Invalid SEO key"}
        cur = db_conn.execute("SELECT balance, active FROM api_keys WHERE key=?", (api_key,))
        row = cur.fetchone()
        if not row or not row[1]:
            return {"success": False, "error": "Key not found or disabled"}
        if row[0] < 1:
            return {"success": False, "error": "Insufficient scans"}
        # Check if already registered
        existing = db_conn.execute("SELECT id FROM seo_urls WHERE api_key=? AND url=?", (api_key, url)).fetchone()
        if existing:
            return {"success": False, "error": "This URL is already registered for auto-scans"}
        db_conn.execute("INSERT INTO seo_urls (api_key, url, last_scan) VALUES (?,?,datetime('now'))", (api_key, url))
        db_conn.commit()
        return {"success": True, "message": "URL registered for weekly scans", "url": url}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/v1/seo/stats")
async def seo_stats():
    """Global SEO audit stats."""
    try:
        total_audits = db_conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
        total_issues = db_conn.execute("SELECT COALESCE(SUM(high_issues+med_issues+low_issues),0) FROM audit_logs").fetchone()[0]
        total_fixes = db_conn.execute("SELECT COALESCE(SUM(total_checks-passed),0) FROM audit_logs").fetchone()[0]
        return {"success": True, "data": {"sites": total_audits, "issues": total_issues, "fixes": total_fixes}}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/v1/seo/balance")
async def seo_balance(api_key: str):
    """Check remaining scans for a key."""
    if not api_key.startswith("seo_"):
        return {"success": False, "error": "Invalid SEO key"}
    cur = db_conn.execute("SELECT balance, name FROM api_keys WHERE key=?", (api_key,))
    row = cur.fetchone()
    if not row:
        return {"success": False, "error": "Key not found"}
    return {"success": True, "data": {"key": api_key, "balance": row[0], "package": row[1]}}

@app.post("/v1/seo/email-report")
async def seo_email_report(request: Request):
    """Run scan + email full report (score, issues, fix solutions) to the user."""
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        api_key = body.get("key", "").strip()
        if not url or not api_key:
            return {"success": False, "error": "URL and key are required"}
        if not api_key.startswith("seo_"):
            return {"success": False, "error": "Invalid SEO key"}
        cur = db_conn.execute("SELECT balance, active FROM api_keys WHERE key=?", (api_key,))
        row = cur.fetchone()
        if not row or not row[1]:
            return {"success": False, "error": "Key not found or disabled"}
        if row[0] < 1:
            return {"success": False, "error": "Insufficient scans"}
        # Look up buyer email from orders
        o = db_conn.execute("SELECT buyer_email FROM orders WHERE api_key=? AND buyer_email IS NOT NULL AND buyer_email!='' ORDER BY paid_at DESC LIMIT 1", (api_key,)).fetchone()
        buyer_email = (body.get("email", "") or (o[0] if o else "")).strip()
        if not buyer_email or "@" not in buyer_email:
            return {"success": False, "error": "No email on file. Provide one in the request."}
        # Run the audit
        result = _run_seo_audit(url)
        score = result.get("score", 0)
        issues = result.get("issues", [])
        checks = result.get("checks", [])
        summary = result.get("summary", {})
        # Get previous score for trend
        prev = db_conn.execute("SELECT last_score FROM seo_urls WHERE api_key=? AND url=?", (api_key, url)).fetchone()
        prev_score = prev[0] if prev else None
        delta = score - prev_score if prev_score is not None else None
        delta_str = f"↑ +{delta}" if delta and delta > 0 else (f"↓ {delta}" if delta and delta < 0 else "— unchanged") if delta is not None else "first scan"
        # Deduct scan
        db_conn.execute("UPDATE api_keys SET balance = balance - 1 WHERE key=?", (api_key,))
        new_balance = row[0] - 1
        # Update seo_urls
        db_conn.execute("UPDATE seo_urls SET last_scan=datetime('now'), last_score=? WHERE api_key=? AND url=?", (score, api_key, url))
        # Save audit_logs
        try:
            domain_hash = hashlib.md5(url.split("//")[-1].split("/")[0].encode()).hexdigest()[:8]
            high = sum(1 for i in issues if i.get("severity") == "high")
            med = sum(1 for i in issues if i.get("severity") == "medium")
            low = sum(1 for i in issues if i.get("severity") == "low")
            db_conn.execute("INSERT INTO audit_logs (domain_hash, score, total_checks, passed, warnings, failed, high_issues, med_issues, low_issues, word_count, content_type) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (domain_hash, score, summary.get("total_checks", 0), summary.get("passed", 0), summary.get("warnings", 0), summary.get("failed", 0), high, med, low, summary.get("word_count", 0), "email"))
        except: pass
        db_conn.commit()
        # Build HTML email
        domain = url.split("//")[-1].split("/")[0]
        score_color = "#a6e3a1" if score >= 80 else ("#f9e2af" if score >= 60 else "#f38ba8")
        issues_html = ""
        for i, iss in enumerate(issues[:15], 1):
            sev_color = {"high": "#f38ba8", "medium": "#f9e2af", "low": "#585b70"}.get(iss.get("severity", "low"), "#585b70")
            sev_label = iss.get("severity", "low").upper()
            fix_code = (iss.get("suggestion", "") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
            issues_html += f"""<tr><td style="padding:10px 12px;border-bottom:1px solid #313244;vertical-align:top;width:3px"><div style="width:3px;height:36px;border-radius:2px;background:{sev_color}"></div></td>
<td style="padding:10px 12px;border-bottom:1px solid #313244">
<div style="font-size:13px;color:#cdd6f4;font-weight:600">{i}. {iss.get("title","").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}</div>
<div style="font-size:10px;color:{sev_color};margin-top:2px">{sev_label} priority</div>
<div style="margin-top:6px;padding:8px;background:#181825;border-radius:4px;font-family:monospace;font-size:11px;color:#89b4fa;line-height:1.5">{fix_code[:200]}</div>
</td></tr>"""
        checks_passed = summary.get("passed", 0)
        checks_total = summary.get("total_checks", 0)
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#1e1e2e;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 16px">
<table width="480" cellpadding="0" cellspacing="0" style="max-width:480px">
<tr><td style="text-align:center;padding:20px 0"><div style="font-size:22px;margin-bottom:4px">🔍</div>
<div style="font-size:14px;font-weight:700;color:#cdd6f4">SEO Audit <span style="color:#89b4fa">Weekly Report</span></div></td></tr>
<!-- Score Card -->
<tr><td style="background:#181825;border:1px solid #313244;border-radius:10px;padding:20px;text-align:center">
<div style="display:inline-block;width:80px;height:80px;border-radius:50%;background:conic-gradient({score_color} 0deg {score/100*360}deg,#313244 {score/100*360}deg 360deg);position:relative;margin-bottom:8px">
<div style="position:absolute;top:5px;left:5px;right:5px;bottom:5px;background:#181825;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center">
<div style="font-size:24px;font-weight:800;color:{score_color}">{score}</div>
<div style="font-size:9px;color:#585b70">Score</div></div></div>
<div style="font-size:16px;font-weight:700;color:#cdd6f4;margin-bottom:2px">{domain}</div>
<div style="font-size:11px;color:#585b70;margin-bottom:8px">{delta_str} · {checks_passed}/{checks_total} checks passed · {len(issues)} issues</div>
<div style="font-size:10px;color:#45475a">🔑 Remaining scans: {new_balance}</div>
</td></tr>
<!-- Checks Summary -->
<tr><td style="padding:16px 0"><table width="100%" cellpadding="10" cellspacing="0"><tr>
<td style="width:33%;background:rgba(166,227,161,.08);border-radius:6px;text-align:center;padding:10px"><div style="font-size:18px;font-weight:700;color:#a6e3a1">{summary.get("passed",0)}</div><div style="font-size:10px;color:#585b70">Passed</div></td>
<td style="width:33%;background:rgba(249,226,175,.06);border-radius:6px;text-align:center;padding:10px"><div style="font-size:18px;font-weight:700;color:#f9e2af">{summary.get("warnings",0)}</div><div style="font-size:10px;color:#585b70">Warnings</div></td>
<td style="width:33%;background:rgba(243,139,168,.08);border-radius:6px;text-align:center;padding:10px"><div style="font-size:18px;font-weight:700;color:#f38ba8">{summary.get("failed",0)}</div><div style="font-size:10px;color:#585b70">Failed</div></td>
</tr></table></td></tr>
<!-- Issues + Fixes -->
<tr><td style="background:#181825;border:1px solid #313244;border-radius:10px;padding:16px">
<div style="font-size:13px;font-weight:600;color:#cdd6f4;margin-bottom:10px">🔴 Issues &amp; Fix Solutions</div>
<table width="100%" cellpadding="0" cellspacing="0">{issues_html if issues_html else '<tr><td style="padding:12px;text-align:center;color:#a6e3a1;font-size:13px">✅ No critical issues found!</td></tr>'}</table>
</td></tr>
<!-- Footer -->
<tr><td style="text-align:center;padding:16px 0;color:#45475a;font-size:10px">
<a href="https://seo.textools.site" style="color:#585b70;text-decoration:none">seo.textools.site</a> ·
<a href="https://seo.textools.site/#pricing" style="color:#585b70;text-decoration:none">Buy more scans</a><br>
This is an automated weekly report. To stop, disable your key or remove registered URLs.
</td></tr>
</table></td></tr></table>
</body></html>"""
        # Send email
        if SMTP_HOST and SMTP_USER and SMTP_PASS:
            try:
                from email.mime.multipart import MIMEMultipart
                msg = MIMEMultipart('alternative')
                msg['From'] = f"SEO Audit <{SMTP_FROM}>"
                msg['To'] = buyer_email
                msg['Subject'] = f"🔍 SEO Weekly Report — {domain} — Score: {score}/100"
                msg.attach(MIMEText(html, 'html', 'utf-8'))
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                    s.starttls()
                    s.login(SMTP_USER, SMTP_PASS)
                    s.send_message(msg)
                return {"success": True, "email": buyer_email, "score": score, "issues": len(issues), "balance": new_balance}
            except Exception as e:
                return {"success": False, "error": f"Audit done but email failed: {e}", "score": score}
        else:
            return {"success": True, "email": buyer_email, "score": score, "issues": len(issues), "balance": new_balance, "note": "SMTP not configured, email not sent"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/v1/seo/pdf-report")
async def seo_pdf_report(request: Request):
    """Run scan + return PDF report for download."""
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        api_key = body.get("key", "").strip()
        if not url or not api_key:
            return {"success": False, "error": "URL and key are required"}
        if not api_key.startswith("seo_"):
            return {"success": False, "error": "Invalid SEO key"}
        cur = db_conn.execute("SELECT balance, active FROM api_keys WHERE key=?", (api_key,))
        row = cur.fetchone()
        if not row or not row[1]:
            return {"success": False, "error": "Key not found or disabled"}
        if row[0] < 1:
            return {"success": False, "error": "Insufficient scans"}
        result = _run_seo_audit(url)
        score = result.get("score", 0)
        issues = result.get("issues", [])
        checks = result.get("checks", [])
        summary = result.get("summary", {})
        db_conn.execute("UPDATE api_keys SET balance = balance - 1 WHERE key=?", (api_key,))
        new_balance = row[0] - 1
        db_conn.commit()
        # Build HTML (same style as email report but printable)
        domain = url.split("//")[-1].split("/")[0]
        score_color = "#a6e3a1" if score >= 80 else ("#f9e2af" if score >= 60 else "#f38ba8")
        checks_rows = ""
        for c in checks:
            icon = "✅" if c["pass"] else ("⚠️" if c.get("warn") else "❌")
            st = "PASS" if c["pass"] else ("WARN" if c.get("warn") else "FAIL")
            st_bg = {'PASS': 'rgba(166,227,161,.12)', 'WARN': 'rgba(249,226,175,.1)', 'FAIL': 'rgba(243,139,168,.12)'}[st]
            st_clr = {'PASS': '#a6e3a1', 'WARN': '#f9e2af', 'FAIL': '#f38ba8'}[st]
            checks_rows += f'<div class="tr"><span class="nm">{icon} {c["name"]}</span><span class="st" style="background:{st_bg};color:{st_clr}">{st}</span></div>'
        issues_html = ""
        for i, iss in enumerate(issues[:15], 1):
            sev_color = {"high": "#f38ba8", "medium": "#f9e2af", "low": "#585b70"}.get(iss.get("severity", "low"), "#585b70")
            sev_label = iss.get("severity", "low").upper()
            fix_code = (iss.get("suggestion", "") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            issues_html += f'<div class="issue"><div class="t">{i}. {iss.get("title","").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}</div><div class="s" style="color:{sev_color}">{sev_label}</div><div class="d">{fix_code[:200]}</div></div>'
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@page {{ margin: 10mm 8mm; size: A4; }}
body {{ margin:0;padding:0;background:#1e1e2e;color:#cdd6f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:10px;line-height:1.4 }}
h2 {{ font-size:12px;margin:8px 0 4px;color:#a6adc8;border-bottom:1px solid #313244;padding-bottom:3px }}
table {{ width:100%;border-collapse:collapse }}
.score-wrap {{ display:flex;align-items:center;gap:12px;background:#181825;border:1px solid #313244;border-radius:6px;padding:8px 12px;margin-bottom:5px }}
.score-ring {{ flex-shrink:0;width:48px;height:48px;border-radius:50%;position:relative }}
.score-ring .inner {{ position:absolute;top:3px;left:3px;right:3px;bottom:3px;background:#1e1e2e;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center }}
.score-ring .inner .num {{ font-size:16px;font-weight:800;line-height:1 }}
.score-ring .inner .label {{ font-size:6px;color:#585b70 }}
.stats {{ display:flex;gap:4px;flex:1 }}
.stat {{ flex:1;text-align:center;background:rgba(24,24,37,.5);border-radius:4px;padding:4px 2px }}
.stat .n {{ font-size:14px;font-weight:700 }}
.stat .l {{ font-size:7px;color:#585b70 }}
.tr {{ display:flex;padding:2px 4px;border-bottom:1px solid rgba(49,50,68,.5);align-items:center }}
.tr .nm {{ flex:1;font-size:8px;color:#cdd6f4 }}
.tr .st {{ font-size:7px;padding:1px 5px;border-radius:3px;font-weight:600;flex-shrink:0 }}
.issue {{ margin-bottom:3px;background:#181825;border-radius:4px;padding:4px 6px }}
.issue .t {{ font-size:8px;color:#cdd6f4;font-weight:600 }}
.issue .s {{ font-size:7px;color:#585b70;margin-top:1px }}
.issue .d {{ margin-top:2px;padding:3px 4px;background:#11111b;border-radius:3px;font-family:monospace;font-size:7px;color:#89b4fa;line-height:1.2;word-break:break-all }}
.footer {{ text-align:center;padding:4px 0;color:#45475a;font-size:7px }}
@media print {{ body {{ background:#1e1e2e!important }} }}
</style></head>
<body style="margin:0;padding:0;background:#1e1e2e">
<div style="max-width:180mm;margin:0 auto;padding:4mm">

<div class="score-wrap">
  <div class="score-ring" style="background:conic-gradient({score_color} 0deg {score/100*360}deg,#313244 {score/100*360}deg 360deg)">
    <div class="inner"><div class="num" style="color:{score_color}">{score}</div><div class="label">Score</div></div>
  </div>
  <div style="flex:1">
    <div style="font-size:11px;font-weight:700;color:#cdd6f4">{domain}</div>
    <div style="font-size:8px;color:#585b70">{summary.get('passed',0)}/{summary.get('total_checks',0)} checks passed · {len(issues)} issues · {datetime.now(timezone.utc).strftime('%Y-%m-%d')} · Remaining: {new_balance}</div>
  </div>
  <div class="stats">
    <div class="stat"><div class="n" style="color:#a6e3a1">{summary.get("passed",0)}</div><div class="l">Passed</div></div>
    <div class="stat"><div class="n" style="color:#f9e2af">{summary.get("warnings",0)}</div><div class="l">Warnings</div></div>
    <div class="stat"><div class="n" style="color:#f38ba8">{summary.get("failed",0)}</div><div class="l">Failed</div></div>
  </div>
</div>

<h2>📋 All Checks</h2>
{checks_rows}

<h2>🔴 Issues & Fixes</h2>
{issues_html if issues_html else '<div style="padding:6px;text-align:center;color:#a6e3a1;font-size:9px">✅ No issues found!</div>'}

<div class="footer">Fix your SEO in minutes, not months. · seo.textools.site — Free scan + AI Visibility check</div>
</div>
</body></html>"""
        from weasyprint import HTML as WeasyHTML
        pdf_bytes = WeasyHTML(string=html).write_pdf()
        from fastapi.responses import Response
        safe_domain = domain.replace("/", "_").replace(":", "_")
        filename = f"{safe_domain}_{datetime.now(timezone.utc).strftime('%Y%m%d')}_seo_report.pdf"
        return Response(content=pdf_bytes, media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except Exception as e:
        return {"success": False, "error": str(e)}

# ─── SEO Audit Tool ─────────────────────────────────────
from .seo_audit import run_audit as _run_seo_audit

@app.post("/v1/seo-audit")
async def seo_audit(request: Request):
    """Run an SEO audit on a given URL."""
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        if not url:
            return {"success": False, "error": "URL is required"}
        result = _run_seo_audit(url)
        return {"success": True, "report": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ─── SEO Article Generator ─────────────────────────────────
from .article_generator import generate_article as _generate_article, add_article_to_indexes as _add_article_to_indexes

@app.post("/v1/seo/generate-article")
async def seo_generate_article(request: Request):
    """Generate an anonymized SEO case study article from audit results."""
    try:
        body = await request.json()
        report = body.get("report", {})
        domain = body.get("domain", "").strip()
        if not report or not domain:
            return {"success": False, "error": "report and domain are required"}
        result = _generate_article(domain, report)
        if result.get("success"):
            _add_article_to_indexes(result["filename"], result["title"])
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

# ─── GEO / AI Visibility ──────────────────────────────────────
CLARITY_MAP_FILE = "/home/ubuntu/ziwei-api/clarity_map.json"

def _load_clarity_map():
    if os.path.exists(CLARITY_MAP_FILE):
        with open(CLARITY_MAP_FILE) as f:
            return json.load(f)
    return {}

def _save_clarity_map(data):
    with open(CLARITY_MAP_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.post("/v1/geo/check-clarity")
async def geo_check_clarity(request: Request):
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        if not url:
            return {"success": False, "error": "URL required"}
        # Normalize to base domain
        from urllib.parse import urlparse
        parsed = urlparse(url if "://" in url else "https://" + url)
        domain = parsed.netloc
        # Try to fetch the page (with fallback to stored data)
        import urllib.request
        fetch_headers = {
            "User-Agent": "Mozilla/5.0 (compatible; GEOBot/1.0; +https://textools.site/geo)",
            "Accept": "text/html"
        }
        has_clarity = False
        html = ""
        for proto in ("https", "http"):
            try:
                req = urllib.request.Request(f"{proto}://{domain}", headers=fetch_headers)
                with urllib.request.urlopen(req, timeout=8) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
                has_clarity = "clarity.ms" in html
                break
            except:
                continue
        # Check for GA4/analytics
        has_ga = "googletagmanager.com" in html or "gtag" in html or "G-" in html
        # Check if domain is in our saved map
        cmap = _load_clarity_map()
        saved_id = cmap.get(domain)
        return {
            "success": True,
            "has_analytics": bool(has_ga or saved_id),
            "analytics_id": saved_id or None,
            "domain": domain,
            "fetch_success": bool(html)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/v1/geo/save-analytics-id")
async def geo_save_analytics_id(request: Request):
    try:
        body = await request.json()
        domain = body.get("domain", "").strip()
        analytics_id = body.get("analytics_id", "").strip()
        if not domain or not analytics_id:
            return {"success": False, "error": "Domain and analytics_id required"}
        cmap = _load_clarity_map()
        cmap[domain] = analytics_id
        _save_clarity_map(cmap)
        return {"success": True, "domain": domain, "analytics_id": analytics_id}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ─── USDT Auto-Confirm ────────────────────────────────────────
@app.post("/v1/seo/create-usdt-order")
async def create_usdt_order(request: Request, package: str = Body(..., embed=True), buyer_email: str = Body("", embed=True)):
    """Create a pending USDT order (no key issued yet)."""
    if package not in SEO_PACKAGES:
        raise HTTPException(400, f"Invalid package: {package}")
    pkg = SEO_PACKAGES[package]
    if not buyer_email or "@" not in buyer_email:
        raise HTTPException(400, "Valid email is required")
    buyer_email = buyer_email.strip().lower()
    # 金额互斥锁：同一价格同时只能有一笔pending USDT订单
    existing_pending = db_conn.execute(
        "SELECT id FROM orders WHERE amount=? AND pay_method='usdt' AND status='pending' AND datetime(created_at) > datetime('now', '-5 minutes')",
        (pkg["price"],)
    ).fetchone()
    if existing_pending:
        return {"success": False, "error": f"当前 ${pkg['price']} 的支付订单已在处理中，请等待完成后重试"}
    oid = f"SEO{secrets.token_hex(8)}"
    db_conn.execute(
        "INSERT INTO orders (id, package, amount, pay_method, status, buyer_email) VALUES (?,?,?,?,?,?)",
        (oid, package, pkg["price"], "usdt", "pending", buyer_email)
    )
    db_conn.commit()
    return {
        "success": True, "data": {
            "order_id": oid,
            "amount": pkg["price"],
            "wallet": USDT_WALLET,
            "package": pkg["name"],
            "scans": pkg["scans"],
        }
    }

@app.post("/v1/seo/confirm-usdt")
async def confirm_usdt_payment(request: Request):
    """Verify USDT payment on-chain and auto-generate key. Called by monitoring script."""
    try:
        body = await request.json()
        tx_hash = body.get("tx_hash", "").strip()
        order_id = body.get("order_id", "").strip()
        if not tx_hash or not order_id:
            return {"success": False, "error": "tx_hash and order_id required"}

        # Look up order
        o = db_conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not o:
            return {"success": False, "error": "Order not found"}
        if o[5] != "pending":
            return {"success": False, "error": "Order already processed"}
        if o[4] != "usdt":
            return {"success": False, "error": "Not a USDT order"}

        # Check if tx_hash already used
        existing = db_conn.execute("SELECT id FROM orders WHERE tx_hash=? AND status='paid'", (tx_hash,)).fetchone()
        if existing:
            return {"success": False, "error": "Transaction already used for another order"}

        # Verify on-chain via TronGrid
        import requests as http_req
        url = f"{TRONGRID_API}/v1/accounts/{USDT_WALLET}/transactions/trc20"
        params = {
            "limit": 20,
            "contract_address": USDT_CONTRACT,
            "only_to": True,
        }
        resp = http_req.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            return {"success": False, "error": f"TronGrid error: {resp.status_code}"}

        tx_data = resp.json().get("data", [])
        matched_tx = None
        for tx in tx_data:
            if tx.get("transaction_id") == tx_hash:
                matched_tx = tx
                break

        if not matched_tx:
            return {"success": False, "error": "Transaction not found on-chain for this address"}

        # Verify amount matches
        value_str = matched_tx.get("value", "0")
        try:
            received_amount = int(value_str) / 1_000_000  # USDT has 6 decimals
        except:
            return {"success": False, "error": "Invalid value in transaction"}

        # Look up package (SEO or subscription)
        is_sub = o[2].startswith('sub_')
        if is_sub:
            sub_plan = o[2].replace('sub_', '')
            sp = SUB_PLANS.get(sub_plan)
            if not sp:
                return {"success": False, "error": "Subscription plan not found"}
            expected = sp["price"]
            plan_name = sp["name"]
        else:
            pkg = SEO_PACKAGES.get(o[2])
            if not pkg:
                return {"success": False, "error": "Package not found"}
            expected = pkg["price"]
            plan_name = pkg["name"]

        if abs(received_amount - expected) > 0.01:
            return {"success": False, "error": f"Amount mismatch: received ${received_amount:.2f}, expected ${expected}"}

        # All checks passed
        buyer_email = o[10] if len(o) > 10 else ""
        k = None

        if is_sub:
            # Subscription: activate / extend
            sub_plan = o[2].replace('sub_', '')
            sp = SUB_PLANS[sub_plan]
            days = sp["days"]
            end_date = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            existing = db_conn.execute(
                "SELECT id FROM subscriptions WHERE email=? AND plan=? AND status='active'",
                (buyer_email, sub_plan)
            ).fetchone()
            if existing:
                # Extend existing subscription
                db_conn.execute(
                    "UPDATE subscriptions SET end_date=datetime(end_date, ?), subscribed_at=datetime('now') WHERE email=? AND plan=?",
                    (f'+{days} days', buyer_email, sub_plan)
                )
            else:
                db_conn.execute(
                    "INSERT INTO subscriptions (email, plan, status, end_date, lang) VALUES (?,?,?,?,?)",
                    (buyer_email, sub_plan, 'active', end_date, 'en')
                )
            # Issue API key with balance for 排盘 access
            k = "zw_" + secrets.token_hex(16)
            db_conn.execute(
                "INSERT INTO api_keys (key, name, balance) VALUES (?,?,?)",
                (k, f"Sub-{sp['name_en']}", 50)
            )
        else:
            # One-time SEO pack: generate key with scans
            k = "seo_" + secrets.token_hex(16)
            db_conn.execute(
                "INSERT INTO api_keys (key, name, balance) VALUES (?,?,?)",
                (k, f"USDT-{plan_name}", pkg["scans"])
            )

        db_conn.execute(
            "UPDATE orders SET status='paid', api_key=?, paid_at=datetime('now'), tx_hash=? WHERE id=?",
            (k, tx_hash, order_id)
        )
        db_conn.commit()

        # Send email
        buyer_email = o[10] if len(o) > 10 else ""
        smtp_available = SMTP_HOST and SMTP_USER and SMTP_PASS
        if smtp_available and buyer_email:
            try:
                if is_sub:
                    end_display = end_date.split(" ")[0] if not existing else "(extended)"
                    html = f"""<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px">
<h2 style="color:#e8b860">🌟 紫微斗數訂閱已啟用</h2>
<p style="color:#d4c9a8">方案: <strong>{sp['name']}</strong> · 有效至: <strong>{end_display}</strong></p>
<div style="background:#1a1a1a;border:1px solid #2a2a1a;border-radius:8px;padding:12px;margin:16px 0;text-align:center">
<p style="color:#c9a84c">🔑 您的 API Key: <code style="background:#2a2a1a;padding:4px 8px;border-radius:4px;font-size:13px">{k}</code></p>
</div>
<p style="color:#8a8060;font-size:12px">您可通過此 Key 調用排盤 API。每日運勢將自動推送到您的郵箱。</p>
<hr style="border:none;border-top:1px solid #2a2a1a;margin:16px 0">
<p style="color:#4a4020;font-size:11px">TXID: {tx_hash[:20]}… · Order: {order_id}</p>
</div>"""
                else:
                    html = f"""<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px">
<h2 style="color:#89b4fa">🔍 Your SEO Audit Key</h2>
<p style="color:#cdd6f4">Package: <strong>{pkg['name']}</strong></p>
<p style="color:#cdd6f4">Scans: <strong>{pkg['scans']}</strong></p>
<p style="color:#585b70;font-size:12px">Payment: USDT ${pkg['price']} ✅</p>
<div style="background:#1e1e2e;border:1px solid #313244;border-radius:8px;padding:12px;margin:16px 0;text-align:center">
<code style="font-size:16px;color:#a6e3a1">{k}</code>
</div>
<p style="color:#585b70;font-size:13px">Use this key on <a href="https://seo.textools.site" style="color:#89b4fa">seo.textools.site</a> to run full audits and register URLs for weekly monitoring.</p>
<hr style="border:none;border-top:1px solid #313244;margin:16px 0">
<p style="color:#45475a;font-size:11px">TXID: {tx_hash[:20]}… · Order: {order_id}</p>
</div>"""
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                import smtplib
                msg = MIMEMultipart('alternative')
                msg['From'] = f"SEO Audit <{SMTP_FROM}>"
                msg['To'] = buyer_email
                subject = '📬 Weekly Subscription Active' if is_monthly else f'Your SEO Audit Key — {pkg["name"]}'
                msg['Subject'] = subject
                msg.attach(MIMEText(html, 'html', 'utf-8'))
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                    s.starttls()
                    s.login(SMTP_USER, SMTP_PASS)
                    s.send_message(msg)
            except Exception as e:
                print(f"[usdt] Email failed: {e}")

        return {"success": True, "data": {
            "key": k,
            "scans": pkg["scans"] if not is_monthly else "∞",
            "package": pkg["name"],
            "order_id": order_id,
            "is_monthly": is_monthly,
        }}

    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/v1/seo/expire-stale-usdt-orders")
async def expire_stale_usdt_orders():
    """将超过5分钟的pending USDT订单标记为expired，释放金额锁。由check_usdt.py调用"""
    try:
        expired = db_conn.execute(
            "UPDATE orders SET status='expired' WHERE pay_method='usdt' AND status='pending' AND datetime(created_at) < datetime('now', '-5 minutes')"
        ).rowcount
        db_conn.commit()
        return {"success": True, "expired": expired}
    except Exception as e:
        return {"success": False, "error": str(e), "expired": 0}

# ─── USDT Monitor Script ──────────────────────────────────────
@app.get("/v1/seo/gsc-stats")
async def get_gsc_stats(domain: str = "", days: int = 30):
    """Return GSC trend data for dashboard"""
    if domain:
        rows = db_conn.execute(
            "SELECT date, impressions, clicks, ctr, avg_position, top_queries FROM gsc_stats WHERE domain=? ORDER BY date DESC LIMIT ?",
            (domain, days)
        ).fetchall()
    else:
        rows = db_conn.execute(
            "SELECT domain, date, impressions, clicks, ctr, avg_position FROM gsc_stats ORDER BY date DESC LIMIT ?",
            (days * 3,)
        ).fetchall()
    
    data = []
    for r in rows:
        if domain:
            data.append({
                "date": r[0], "impressions": r[1], "clicks": r[2],
                "ctr": r[3], "avg_position": r[4],
                "top_queries": json.loads(r[5]) if r[5] else {}
            })
        else:
            data.append({
                "domain": r[0], "date": r[1], "impressions": r[2],
                "clicks": r[3], "ctr": r[4], "avg_position": r[5]
            })
    
    return {"success": True, "data": data}

@app.get("/v1/seo/gsc-latest")
async def get_gsc_latest():
    """Return latest snapshot for each domain"""
    rows = db_conn.execute("""
        SELECT g1.domain, g1.date, g1.impressions, g1.clicks, g1.ctr, g1.avg_position, g1.top_queries
        FROM gsc_stats g1
        INNER JOIN (
            SELECT domain, MAX(date) as max_date FROM gsc_stats GROUP BY domain
        ) g2 ON g1.domain = g2.domain AND g1.date = g2.max_date
        ORDER BY g1.domain
    """).fetchall()
    
    domains = {}
    for r in rows:
        domains[r[0]] = {
            "date": r[1], "impressions": r[2], "clicks": r[3],
            "ctr": r[4], "avg_position": r[5],
            "top_queries": json.loads(r[6]) if r[6] else {}
        }
    
    return {"success": True, "data": domains}

@app.get("/v1/seo/check-owner")
async def check_owner(key: str = ""):
    """Check if a key has owner privileges (for GSC dashboard)"""
    import hashlib
    key_hash = hashlib.sha256(key.encode()).hexdigest()[:16] if key else ""
    return {"success": True, "is_owner": key_hash == OWNER_KEY_HASH}

@app.get("/v1/seo/pending-usdt-orders")
async def get_pending_usdt_orders():
    """Return pending USDT orders (for monitoring script)."""
    rows = db_conn.execute(
        "SELECT id, amount, created_at FROM orders WHERE pay_method='usdt' AND status='pending' ORDER BY created_at ASC LIMIT 20"
    ).fetchall()
    return {"success": True, "data": [
        {"order_id": r[0], "amount": r[1], "created_at": str(r[2]) if r[2] else ""}
        for r in rows
    ]}


# ─── Admin: Key Management (owner only) ─────────────────────
@app.get("/v1/seo/admin/scan-logs")
async def admin_scan_logs(key: str = "", owner_key: str = ""):
    """Return scan history for a key. Requires owner key."""
    import hashlib
    if hashlib.sha256(owner_key.encode()).hexdigest()[:16] != OWNER_KEY_HASH:
        return {"success": False, "error": "Unauthorized"}
    key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
    rows = db_conn.execute(
        "SELECT url, score, ip, created_at FROM scan_logs WHERE key_hash=? ORDER BY created_at DESC LIMIT 100",
        (key_hash,)
    ).fetchall()
    return {"success": True, "data": [
        {"url": r[0], "score": r[1], "ip": r[2], "time": r[3]} for r in rows
    ]}

@app.post("/v1/seo/admin/freeze-key")
async def admin_freeze_key(request: Request):
    """Disable a key. Requires owner key."""
    import hashlib
    body = await request.json()
    target_key = body.get("key", "")
    owner_key = body.get("owner_key", "")
    if hashlib.sha256(owner_key.encode()).hexdigest()[:16] != OWNER_KEY_HASH:
        return {"success": False, "error": "Unauthorized"}
    cur = db_conn.execute("SELECT active FROM api_keys WHERE key=?", (target_key,))
    row = cur.fetchone()
    if not row:
        return {"success": False, "error": "Key not found"}
    db_conn.execute("UPDATE api_keys SET active=0 WHERE key=?", (target_key,))
    db_conn.commit()
    return {"success": True, "message": "Key frozen"}

@app.post("/v1/seo/admin/unfreeze-key")
async def admin_unfreeze_key(request: Request):
    """Re-enable a frozen key. Requires owner key."""
    import hashlib
    body = await request.json()
    target_key = body.get("key", "")
    owner_key = body.get("owner_key", "")
    if hashlib.sha256(owner_key.encode()).hexdigest()[:16] != OWNER_KEY_HASH:
        return {"success": False, "error": "Unauthorized"}
    db_conn.execute("UPDATE api_keys SET active=1 WHERE key=?", (target_key,))
    db_conn.commit()
    return {"success": True, "message": "Key unfrozen"}

@app.post("/v1/seo/admin/replace-key")
async def admin_replace_key(request: Request):
    """Freeze old key and issue a new one with same balance. Requires owner key."""
    import hashlib, secrets
    body = await request.json()
    old_key = body.get("key", "")
    owner_key = body.get("owner_key", "")
    if hashlib.sha256(owner_key.encode()).hexdigest()[:16] != OWNER_KEY_HASH:
        return {"success": False, "error": "Unauthorized"}
    cur = db_conn.execute("SELECT balance, name FROM api_keys WHERE key=?", (old_key,))
    row = cur.fetchone()
    if not row:
        return {"success": False, "error": "Key not found"}
    # Freeze old key
    db_conn.execute("UPDATE api_keys SET active=0 WHERE key=?", (old_key,))
    # Create new key with same balance
    new_key = "seo_" + secrets.token_hex(32)
    db_conn.execute("INSERT INTO api_keys (key, name, balance, created_at, active) VALUES (?,?,?,datetime('now'),1)",
        (new_key, row[1], row[0]))
    db_conn.commit()
    return {"success": True, "data": {"old_key": old_key, "new_key": new_key, "balance": row[0]}}


@app.post("/v1/seo/subscribe-email")
async def seo_subscribe_email(request: Request):
    """Subscribe email for SEO audit report delivery. Sends first email immediately."""
    try:
        body = await request.json()
        email = body.get("email", "").strip().lower()
        domain = body.get("domain", "").strip()
        score = body.get("score", None)

        if not email or "@" not in email:
            return {"success": False, "error": "Valid email is required"}

        # Step 1: Insert or ignore if already subscribed
        if score is not None:
            db_conn.execute(
                "INSERT OR IGNORE INTO email_subscribers (email, domain, score, step, source) VALUES (?,?,?,0,'scan')",
                (email, domain, int(score))
            )
        else:
            db_conn.execute(
                "INSERT OR IGNORE INTO email_subscribers (email, domain, step, source) VALUES (?,?,0,'scan')",
                (email, domain)
            )
        db_conn.commit()

        # Step 2: Send email 1 — SEO audit report ready
        display_score = score if score is not None else 78
        display_domain = domain if domain else "your site"
        subject = f"Your SEO Audit Report is Ready — {display_score}/100"

        # Score ring colour based on value
        if display_score >= 90:
            ring_color = "#a6e3a1"
            ring_label = "Excellent"
        elif display_score >= 70:
            ring_color = "#f9e2af"
            ring_label = "Good"
        elif display_score >= 50:
            ring_color = "#fab387"
            ring_label = "Needs Work"
        else:
            ring_color = "#f38ba8"
            ring_label = "Poor"

        circumference = 251  # 2 * pi * 40
        offset = circumference - (display_score / 100) * circumference

        html = f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:560px;margin:0 auto;padding:32px 24px;background:#1e1e2e;border-radius:16px;color:#cdd6f4">
<div style="text-align:center;margin-bottom:24px">
<h1 style="font-size:22px;color:#cdd6f4;margin:0 0 4px">🔍 SEO Audit Complete</h1>
<p style="color:#585b70;font-size:13px;margin:0">{display_domain}</p>
</div>
<div style="text-align:center;margin:24px 0">
<svg width="120" height="120" viewBox="0 0 120 120" style="display:inline-block">
<circle cx="60" cy="60" r="40" fill="none" stroke="#313244" stroke-width="8"/>
<circle cx="60" cy="60" r="40" fill="none" stroke="{ring_color}" stroke-width="8" stroke-dasharray="{circumference}" stroke-dashoffset="{offset}" stroke-linecap="round" transform="rotate(-90,60,60)"/>
<text x="60" y="56" text-anchor="middle" fill="{ring_color}" font-size="26" font-weight="bold">{display_score}</text>
<text x="60" y="72" text-anchor="middle" fill="#585b70" font-size="11">/ 100</text>
</svg>
<p style="color:{ring_color};font-size:14px;font-weight:600;margin:8px 0 0">{ring_label}</p>
</div>
<div style="background:#181825;border-radius:12px;padding:20px;margin:20px 0">
<h3 style="color:#cdd6f4;font-size:15px;margin:0 0 12px">📋 Top Issues Found</h3>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<tr><td style="padding:8px 0;border-bottom:1px solid #313244">🔴 Missing meta descriptions</td><td style="text-align:right;color:#f38ba8;padding:8px 0;border-bottom:1px solid #313244">High</td></tr>
<tr><td style="padding:8px 0;border-bottom:1px solid #313244">🟠 Slow LCP (&gt;2.5s)</td><td style="text-align:right;color:#fab387;padding:8px 0;border-bottom:1px solid #313244">Medium</td></tr>
<tr><td style="padding:8px 0">🟡 Missing alt attributes on images</td><td style="text-align:right;color:#f9e2af;padding:8px 0">Medium</td></tr>
</table>
</div>
<div style="text-align:center;margin:24px 0">
<a href="https://seo.textools.site/#pricing" style="display:inline-block;background:#89b4fa;color:#1e1e2e;text-decoration:none;font-weight:700;font-size:15px;padding:14px 32px;border-radius:8px">Unlock Full Report →</a>
</div>
<div style="margin-top:20px;padding-top:16px;border-top:1px solid #313244;text-align:center">
<p style="color:#585b70;font-size:11px;margin:0">You received this email because you requested an SEO audit on seo.textools.site</p>
<p style="color:#45475a;font-size:11px;margin:6px 0 0">{display_domain} · seo.textools.site</p>
</div>
</div>"""

        sent = send_email(email, subject, html)

        # Step 3: Update step if email was sent
        if sent:
            db_conn.execute("UPDATE email_subscribers SET step=1, last_sent=datetime('now') WHERE email=?", (email,))
            db_conn.commit()

        return {"success": True}

    except Exception as e:
        print(f"[subscribe-email] Error: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8119, reload=True)
