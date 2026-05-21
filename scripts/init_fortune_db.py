"""
紫微斗数 每日运势 — 数据库初始化
扩展 ziwei.db，新增用户/订阅/日志表
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path("/home/ubuntu/ziwei-api/data/ziwei.db")

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # 用户表
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        name TEXT DEFAULT '',
        birth_year INTEGER NOT NULL,
        birth_month INTEGER NOT NULL,
        birth_day INTEGER NOT NULL,
        birth_hour REAL NOT NULL,
        gender TEXT NOT NULL CHECK(gender IN ('male','female')),
        city TEXT DEFAULT '',
        timezone TEXT DEFAULT 'Asia/Shanghai',
        created_at TEXT DEFAULT (datetime('now')),
        last_active TEXT,
        is_active INTEGER DEFAULT 1
    )
    """)

    # 订阅表
    c.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        plan TEXT NOT NULL CHECK(plan IN ('weekly','monthly','quarterly','yearly','trial')),
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','cancelled','expired','paused')),
        price REAL DEFAULT 0,
        currency TEXT DEFAULT 'CNY',
        gumroad_order_id TEXT,
        gumroad_product_id TEXT,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        cancelled_at TEXT,
        renewed_count INTEGER DEFAULT 0
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_sub_user ON subscriptions(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sub_status ON subscriptions(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sub_end ON subscriptions(end_date)")

    # 每日运势日志
    c.execute("""
    CREATE TABLE IF NOT EXISTS daily_fortune_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        date TEXT NOT NULL,
        day_ganzhi TEXT,
        overall_score INTEGER DEFAULT 0,
        lucky_palaces TEXT DEFAULT '',       -- JSON array
        caution_palaces TEXT DEFAULT '',     -- JSON array
        detail_json TEXT DEFAULT '',         -- 完整运势JSON
        sent_via_email INTEGER DEFAULT 0,
        sent_at TEXT,
        opened INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(user_id, date)
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_dfl_user_date ON daily_fortune_logs(user_id, date)")

    # 发送统计（供营销用）
    c.execute("""
    CREATE TABLE IF NOT EXISTS fortune_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stat_date TEXT NOT NULL UNIQUE,
        total_active_users INTEGER DEFAULT 0,
        total_sent INTEGER DEFAULT 0,
        total_opened INTEGER DEFAULT 0,
        avg_score REAL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    conn.commit()
    conn.close()
    print(f"✅ DB initialized at {DB_PATH}")
    print("   Tables: users, subscriptions, daily_fortune_logs, fortune_stats")

if __name__ == "__main__":
    init_db()
