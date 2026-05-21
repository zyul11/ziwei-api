"""
紫微斗数 API — 排盘 + AI 解读 + API Key 计费
"""
import json
import sqlite3
import subprocess
import secrets
import os
import smtplib
import email
from email.mime.text import MIMEText
import json as jmod
from datetime import datetime, timedelta, date
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Load .env for local dev
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from fastapi import FastAPI, HTTPException, Header, Depends, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from openai import OpenAI
from typing import Optional

# ─── config ────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
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

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")

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
    db_conn.execute("""CREATE TABLE IF NOT EXISTS trial_claims (ip TEXT, email TEXT, key TEXT, created_at TEXT DEFAULT (datetime('now')))""")
    db_conn.execute("""CREATE TABLE IF NOT EXISTS subscriptions (email TEXT PRIMARY KEY, plan TEXT NOT NULL DEFAULT 'monthly', status TEXT NOT NULL DEFAULT 'active', lang TEXT DEFAULT 'zh', delivery_count INTEGER DEFAULT 0, tier INTEGER DEFAULT 1, subscribed_at TEXT DEFAULT (datetime('now')), cancelled_at TEXT)""")
    db_conn.commit()
    yield
    if db_conn:
        db_conn.close()

app = FastAPI(title="紫微斗数 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

static_dir = Path(__file__).parent.parent
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    from fastapi.responses import HTMLResponse
    @app.get("/app/{page}")
    def serve_page(page: str):
        fp = static_dir / page
        if fp.exists(): return HTMLResponse(fp.read_text(encoding="utf-8"))
        return HTMLResponse("Not found", 404)
    @app.get("/")
    async def serve_root():
        return FileResponse(static_dir / "index.html")

# ─── models ─────────────────────────────────────────────────
class PaiPanRequest(BaseModel):
    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: float = Field(..., ge=0, le=23)
    gender: str = Field(..., pattern="^(male|female)$")
    style: str = Field("modern", pattern="^(modern|classical|poetic)$")
    city: str = Field("", max_length=100)
    language: str = Field("zh-Hant", pattern="^(zh-Hant|zh-Hans|en)$")

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
_NODE = shutil.which("node") or "node"

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

# ─── 城市特征库 ────────────────────────────────────────────────
CITY_PROFILES = {
    "新加坡": "国际金融中心、港口贸易枢纽、花园城市", "吉隆坡": "马来西亚首都、华人活跃、热带气候",
    "曼谷": "泰国首都、旅游大城、华人文化深厚", "雅加达": "印尼首都、华人商业网络发达",
    "马尼拉": "菲律宾首都、BPO外包产业", "胡志明": "越南经济中心、新兴制造业枢纽",
    "台北": "台湾政经文化中心、半导体/ICT产业", "香港": "国际金融中心、中西交汇",
    "澳门": "世界旅游休闲中心、博彩业", "上海": "中国经济金融中心、长三角集群",
    "北京": "政治文化教育中心、互联网/文创", "深圳": "科技之都、大湾区核心",
    "广州": "南大门、千年商都、岭南文化", "杭州": "数字经济重镇、阿里总部",
    "成都": "西南消费中心、文创之都", "高雄": "台湾南部最大城市、港口与重工业",
    "台中": "台湾中部经济文化中心", "纽约": "世界金融中心、多元文化大熔炉",
    "洛杉矶": "娱乐产业之都、好莱坞", "旧金山": "硅谷所在地、全球科创发源地",
    "西雅图": "云计算/航空产业领先", "波士顿": "教育之都、哈佛/MIT/生物科技",
    "芝加哥": "中西部经济中心、大湖区枢纽", "温哥华": "加拿大西岸最大城市、华人社区",
    "多伦多": "加拿大最大城市、金融中心", "东京": "东亚经济中心、服务业/科技",
    "首尔": "韩国首都、韩流文化中心", "悉尼": "澳洲最大城市、南太平洋金融中心",
    "墨尔本": "文化之都、全球最宜居城市", "奥克兰": "新西兰最大城市、交通枢纽",
    "伦敦": "全球金融中心、欧洲文化之都", "巴黎": "艺术时尚之都、奢侈品/旅游",
    "阿姆斯特丹": "金融/创新枢纽、金融科技", "迪拜": "中东商业旅游中心、免税财富",
    "开普敦": "南非立法首都、旅游和金融业",
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
    "温哥华": "Canada's West Coast, large Chinese community",
    "多伦多": "Canada's largest city, financial center",
    "东京": "Global megacity, services/tech/finance",
    "首尔": "South Korea's capital, Hallyu culture",
    "悉尼": "Australia's largest city, Pacific financial center",
    "墨尔本": "Cultural capital, world's most livable",
    "奥克兰": "New Zealand's largest city, transport hub",
    "伦敦": "Global finance, European cultural capital",
    "巴黎": "Fashion/art capital, luxury/tourism",
    "阿姆斯特丹": "Finance/innovation hub, fintech",
    "迪拜": "Business/tourism hub, tax-free wealth",
    "开普敦": "Legislative capital, tourism/finance",
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
    if p.exists(): return HTMLResponse(p.read_text(encoding="utf-8"))
    return HTMLResponse("Not found", 404)

@app.get("/about.html")
async def serve_about():
    p = static_dir / "about.html"
    if p.exists(): return HTMLResponse(p.read_text(encoding="utf-8"))
    return HTMLResponse("Not found", 404)

@app.get("/api-docs.html")
async def serve_api_docs():
    p = static_dir / "api-docs.html"
    if p.exists(): return HTMLResponse(p.read_text(encoding="utf-8"))
    return HTMLResponse("Not found", 404)

@app.get("/health")
def root():
    return {"name": "紫微斗数 API", "version": "1.0.0", "docs": "/docs"}

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
                resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_msg}], temperature=0.7, max_tokens=500, timeout=15)
                full = resp.choices[0].message.content or ""
                reading = full[:200] + ("..." if len(full) > 200 else "")
            except: reading = "AI解读暂时不可用"
        _FREE_IPS.add(ip)
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
                resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_msg}], temperature=0.7, max_tokens=2000, timeout=15)
                reading = resp.choices[0].message.content or ""
                it = resp.usage.prompt_tokens if resp.usage else 0
                ot = resp.usage.completion_tokens if resp.usage else 0
                cost = max(1, (it + ot) // 1000)
                log_usage(key, "paipan", cost, it, ot)
                deduct_balance(key, cost)
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
    language: str = Field("zh-Hant", pattern="^(zh-Hant|zh-Hans|en)$")

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
                resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_msg}], temperature=0.7, max_tokens=800, timeout=15)
                reading = resp.choices[0].message.content or ""
                it = resp.usage.prompt_tokens if resp.usage else 0; ot = resp.usage.completion_tokens if resp.usage else 0
                cost = max(1, (it + ot) // 1000)
                log_usage(key, "daily", cost, it, ot); deduct_balance(key, cost)
            except Exception as e:
                reading = f"[AI不可用: {str(e)}]"
                log_usage(key, "daily", 1); deduct_balance(key, 1)
        else:
            log_usage(key, "daily", 1); deduct_balance(key, 1)
        return DailyResponse(success=True, data={"context": context, "reading": reading})
    except Exception as e: return DailyResponse(success=False, error=str(e))

# ─── daxian ─────────────────────────────────────────────────
class DaXianRequest(BaseModel):
    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: float = Field(..., ge=0, le=23)
    gender: str = Field(..., pattern="^(male|female)$")
    style: str = Field("modern", pattern="^(modern|classical|poetic)$")
    city: str = Field("", max_length=100)
    language: str = Field("zh-Hant", pattern="^(zh-Hant|zh-Hans|en)$")

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
                resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role":"system","content":prompt},{"role":"user","content":user_msg}], temperature=0.7, max_tokens=800, timeout=15)
                reading = resp.choices[0].message.content or ""
                it = resp.usage.prompt_tokens if resp.usage else 0; ot = resp.usage.completion_tokens if resp.usage else 0
                cost = max(1, (it + ot) // 1000)
                log_usage(key, "daxian", cost, it, ot); deduct_balance(key, cost)
            except:
                reading = "[AI不可用]"
                log_usage(key, "daxian", 1); deduct_balance(key, 1)
        else:
            log_usage(key, "daxian", 1); deduct_balance(key, 1)
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
                resp=client.chat.completions.create(model="deepseek-chat",messages=[{"role":"system","content":prompt},{"role":"user","content":user_msg}],temperature=0.7,max_tokens=400,timeout=15)
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
                resp=client.chat.completions.create(model="deepseek-chat",messages=[{"role":"system","content":prompt},{"role":"user","content":user_msg}],temperature=0.7,max_tokens=400,timeout=15)
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

# ─── shop ────────────────────────────────────────────────────
PACKAGES = {"starter":{"name":"Starter","price":9.9,"quota":3},"standard":{"name":"Standard","price":34.9,"quota":30},"pro":{"name":"Pro","price":119,"quota":200},"enterprise":{"name":"Enterprise","price":1888,"quota":1888}}

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

@app.post("/v1/checkout/mock")
def mock_checkout(request: Request, package: str = Body(None, embed=True), buyer_email: str = Body("", embed=True)):
    """Trial: 1 key per IP/email, 3 quota, emailed"""
    if not package: raise HTTPException(400, "package is required")
    if not buyer_email or "@" not in buyer_email:
        raise HTTPException(400, "Valid email is required")
    buyer_email = buyer_email.strip().lower()
    ip = request.client.host if request.client else "unknown"

    # Check IP 24h limit
    yesterday = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    recent = db_conn.execute("SELECT COUNT(*) FROM trial_claims WHERE ip=? AND created_at>?", (ip, yesterday)).fetchone()[0]
    if recent > 0:
        raise HTTPException(429, "Only 1 trial per 24 hours per IP")
    # Check email already used
    used = db_conn.execute("SELECT COUNT(*) FROM trial_claims WHERE email=?", (buyer_email,)).fetchone()[0]
    if used > 0:
        raise HTTPException(400, "This email already claimed a trial key")

    pkg = PACKAGES[package]
    oid = f"TRIAL{secrets.token_hex(8)}"
    k = "zw_" + secrets.token_hex(16)
    db_conn.execute("INSERT INTO api_keys (key, name, balance) VALUES (?,?,?)", (k, f"Trial-{pkg['name']}", 3))
    db_conn.execute("INSERT INTO orders (id, package, amount, pay_method, status, api_key, paid_at) VALUES (?,?,?,?,?,?,datetime('now'))", (oid, package, 0, "trial", "paid", k))
    db_conn.execute("INSERT INTO trial_claims (ip, email, key) VALUES (?,?,?)", (ip, buyer_email, k))
    db_conn.commit()

    # Send email
    if SMTP_HOST and SMTP_USER and SMTP_PASS:
        try:
            subject = f"Your Ziwei API Trial Key ({pkg['name']})"
            body = f"""Hi,

Your Ziwei Doushu API trial key is ready!

  Package: {pkg['name']}
  API Key: {k}
  Remaining: 3 calls
  Order: {oid}

To use it, call:
  curl https://ziweiapi.site/v1/paipan \\
    -H 'Authorization: {k}' \\
    -H 'Content-Type: application/json' \\
    -d '{{"year":1990,"month":5,"day":15,"hour":12,"gender":"male","style":"modern","language":"en"}}'

Need more? Visit https://ziweiapi.site/shop.html to purchase a full package.

Best,
Ziwei API Team"""
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM
            msg["To"] = buyer_email
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        except Exception as e:
            print(f"⚠️ Email send failed: {e}")

    return {"success": True, "data": {"key": k, "quota": 3, "package": pkg["name"], "order_id": oid, "mock": True, "email": buyer_email}}

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
    return {"success":True,"data":{"status":o[5],"api_key":o[6],"package":o[2],"amount":o[3]}}

class SubscribeRequest(BaseModel):
    email: str
    plan: str = "monthly"
    lang: str = "zh"
    name: str = ""
    birth_year: int = 0
    birth_month: int = 0
    birth_day: int = 0
    birth_hour: float = 12.0
    gender: str = "male"
    source: str = ""
    marketing_consent: bool = False
    ref_code: str = ""  # referral code from another user

@app.post("/v1/subscribe")
def subscribe(req: SubscribeRequest, request: Request):
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Invalid email")
    plan = req.plan if req.plan in ("monthly", "yearly") else "monthly"
    lang = req.lang if req.lang in ("zh", "en") else "zh"
    try:
        # Check existing user by email
        existing_user = db_conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        user_id = existing_user[0] if existing_user else None

        if not user_id and req.birth_year:
            # Create user with birth info
            now = datetime.now().isoformat()
            db_conn.execute("""INSERT INTO users (email, name, birth_year, birth_month, birth_day, birth_hour, gender, is_active, created_at)
                VALUES (?,?,?,?,?,?,?,1,?)""",
                (email, req.name, req.birth_year, req.birth_month, req.birth_day, req.birth_hour, req.gender, now))
            db_conn.commit()
            user_id = db_conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()[0]

        # Handle referral: gifter gets +3 days
        if req.ref_code and user_id:
            gift_user = db_conn.execute("SELECT id FROM users WHERE id=? OR email=?", (req.ref_code, req.ref_code)).fetchone()
            if gift_user and gift_user[0] != user_id:
                gift_sub = db_conn.execute("SELECT end_date FROM subscriptions WHERE user_id=?", (gift_user[0],)).fetchone()
                if gift_sub and gift_sub[0]:
                    from datetime import timedelta
                    new_end = (datetime.fromisoformat(gift_sub[0]) + timedelta(days=3)).isoformat()
                    db_conn.execute("UPDATE subscriptions SET end_date=? WHERE user_id=?", (new_end, gift_user[0]))
                    db_conn.commit()

        # Create or update trial subscription
        today = datetime.now().isoformat()
        from datetime import timedelta
        trial_end = (datetime.now() + timedelta(days=3)).isoformat()

        existing_sub = db_conn.execute("SELECT * FROM subscriptions WHERE user_id=?", (user_id,)).fetchone()
        if existing_sub:
            db_conn.execute("""UPDATE subscriptions SET plan=?, lang=?, status='active',
                start_date=?, end_date=?, source=?, marketing_consent=?
                WHERE user_id=?""", (plan, lang, today, trial_end, req.source, req.marketing_consent, user_id))
        else:
            db_conn.execute("""INSERT INTO subscriptions (user_id, email, plan, status, lang, start_date, end_date, source, marketing_consent)
                VALUES (?,?,?,'active',?,?,?,?,?)""",
                (user_id, email, plan, lang, today, trial_end, req.source, req.marketing_consent))
        db_conn.commit()

        return {
            "success": True,
            "message": "Trial started" if lang == "en" else "免费试用已开通",
            "data": {
                "trial_days": 3,
                "end_date": trial_end[:10],
                "user_id": user_id
            }
        }
    except Exception as e:
        raise HTTPException(500, str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8119, reload=True)
