"""
SQLite ma'lumotlar bazasi - hech qanday tashqi xizmat (Google Sheets, CRM) kerak emas.
Barcha lidlar, sotuvchilar va to'lovlar shu bitta fayl (vizabot.db) ichida saqlanadi.
"""

import sqlite3
from datetime import datetime, timedelta
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sellers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_telegram_id INTEGER,
            client_username TEXT,
            name TEXT,
            phone TEXT,
            country TEXT,
            purpose TEXT,
            status TEXT DEFAULT 'yangi',
            assigned_seller_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            contacted_at TEXT,
            payment_amount INTEGER,
            payment_link TEXT,
            paid_at TEXT,
            reminder_sent INTEGER DEFAULT 0,
            FOREIGN KEY (assigned_seller_id) REFERENCES sellers(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            client_telegram_id INTEGER PRIMARY KEY,
            messages_json TEXT DEFAULT '[]',
            lead_id INTEGER,
            handoff INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


# ---------- AI SUHBAT TARIXI ----------

def get_conversation(client_telegram_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM conversations WHERE client_telegram_id = ?", (client_telegram_id,))
    row = cur.fetchone()
    conn.close()
    return row


def save_conversation(client_telegram_id: int, messages_json: str, lead_id=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO conversations (client_telegram_id, messages_json, lead_id, updated_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(client_telegram_id) DO UPDATE SET
             messages_json = excluded.messages_json,
             lead_id = COALESCE(excluded.lead_id, conversations.lead_id),
             updated_at = datetime('now')""",
        (client_telegram_id, messages_json, lead_id),
    )
    conn.commit()
    conn.close()


def mark_handoff(client_telegram_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE conversations SET handoff = 1 WHERE client_telegram_id = ?",
        (client_telegram_id,),
    )
    conn.commit()
    conn.close()

def add_seller(telegram_id: int, name: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO sellers (telegram_id, name) VALUES (?, ?)",
        (telegram_id, name),
    )
    conn.commit()
    conn.close()


def get_active_sellers():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sellers WHERE active = 1 ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_seller_by_telegram_id(telegram_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sellers WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    conn.close()
    return row


# ---------- LIDLAR ----------

def create_lead(client_telegram_id, client_username, name, phone, country, purpose):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO leads (client_telegram_id, client_username, name, phone, country, purpose)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (client_telegram_id, client_username, name, phone, country, purpose),
    )
    lead_id = cur.lastrowid
    conn.commit()
    conn.close()
    return lead_id


def assign_lead_round_robin(lead_id: int):
    """
    Lidni eng kam faol (hozircha yopilmagan) lidga ega bo'lgan sotuvchiga biriktiradi.
    Bu oddiy "round-robin" o'rniga yanada adolatli - ish yukini tenglashtiradi.
    """
    sellers = get_active_sellers()
    if not sellers:
        return None

    conn = get_conn()
    cur = conn.cursor()

    best_seller = None
    best_count = None
    for s in sellers:
        cur.execute(
            """SELECT COUNT(*) as c FROM leads
               WHERE assigned_seller_id = ? AND status NOT IN ('tolandi', 'yoqotildi')""",
            (s["id"],),
        )
        count = cur.fetchone()["c"]
        if best_count is None or count < best_count:
            best_count = count
            best_seller = s

    cur.execute(
        "UPDATE leads SET assigned_seller_id = ?, status = 'biriktirildi' WHERE id = ?",
        (best_seller["id"], lead_id),
    )
    conn.commit()
    conn.close()
    return best_seller


def get_lead(lead_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
    row = cur.fetchone()
    conn.close()
    return row


def mark_contacted(lead_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE leads SET status = 'muloqotda', contacted_at = datetime('now') WHERE id = ?",
        (lead_id,),
    )
    conn.commit()
    conn.close()


def set_payment_link(lead_id: int, amount: int, link: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """UPDATE leads SET status = 'tolov_kutilmoqda', payment_amount = ?, payment_link = ?
           WHERE id = ?""",
        (amount, link, lead_id),
    )
    conn.commit()
    conn.close()


def mark_paid(lead_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE leads SET status = 'tolandi', paid_at = datetime('now') WHERE id = ?",
        (lead_id,),
    )
    conn.commit()
    conn.close()


def mark_lost(lead_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE leads SET status = 'yoqotildi' WHERE id = ?", (lead_id,))
    conn.commit()
    conn.close()


def get_leads_needing_reminder(hours: int):
    """
    Biriktirilgan, lekin hali bog'lanilmagan (status='biriktirildi')
    va belgilangan soatdan ko'proq vaqt o'tgan lidlarni topadi.
    """
    conn = get_conn()
    cur = conn.cursor()
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        """SELECT * FROM leads
           WHERE status = 'biriktirildi' AND reminder_sent = 0 AND created_at <= ?""",
        (cutoff,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def mark_reminder_sent(lead_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE leads SET reminder_sent = 1 WHERE id = ?", (lead_id,))
    conn.commit()
    conn.close()


def get_seller_leads(seller_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT * FROM leads WHERE assigned_seller_id = ?
           AND status NOT IN ('tolandi', 'yoqotildi') ORDER BY created_at DESC""",
        (seller_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows
