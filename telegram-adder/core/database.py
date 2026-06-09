import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime, date
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_conn():
    return psycopg2.connect(DATABASE_URL)


@contextmanager
def db_cursor():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tg_accounts (
                id SERIAL PRIMARY KEY,
                phone VARCHAR(20) UNIQUE NOT NULL,
                api_id INTEGER NOT NULL,
                api_hash VARCHAR(100) NOT NULL,
                session_string TEXT,
                proxy_id INTEGER,
                device_model VARCHAR(100),
                system_version VARCHAR(50),
                app_version VARCHAR(20),
                lang_code VARCHAR(10) DEFAULT 'en',
                status VARCHAR(30) DEFAULT 'pending',
                flood_wait_until TIMESTAMP,
                daily_add_count INTEGER DEFAULT 0,
                daily_add_date DATE,
                last_used TIMESTAMP,
                two_factor_password TEXT,
                spambot_status VARCHAR(30) DEFAULT 'unknown',
                spambot_checked_at TIMESTAMP,
                appeal_sent_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        for col_sql in [
            "ALTER TABLE tg_accounts ADD COLUMN IF NOT EXISTS two_factor_password TEXT",
            "ALTER TABLE tg_accounts ADD COLUMN IF NOT EXISTS spambot_status VARCHAR(30) DEFAULT 'unknown'",
            "ALTER TABLE tg_accounts ADD COLUMN IF NOT EXISTS spambot_checked_at TIMESTAMP",
            "ALTER TABLE tg_accounts ADD COLUMN IF NOT EXISTS appeal_sent_at TIMESTAMP",
        ]:
            cur.execute(col_sql)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tg_proxies (
                id SERIAL PRIMARY KEY,
                proxy_type VARCHAR(10) NOT NULL,
                host VARCHAR(200) NOT NULL,
                port INTEGER NOT NULL,
                username VARCHAR(100),
                password VARCHAR(100),
                account_id INTEGER,
                is_active BOOLEAN DEFAULT true,
                last_checked TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        for col_sql in [
            "ALTER TABLE tg_proxies ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true",
            "ALTER TABLE tg_proxies ADD COLUMN IF NOT EXISTS last_checked TIMESTAMP",
        ]:
            cur.execute(col_sql)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tg_members (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username VARCHAR(200),
                first_name VARCHAR(200),
                last_name VARCHAR(200),
                access_hash BIGINT,
                phone VARCHAR(20),
                source_group VARCHAR(200),
                last_seen VARCHAR(50),
                status VARCHAR(30) DEFAULT 'pending',
                added_by_account_id INTEGER,
                added_at TIMESTAMP,
                error_msg TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_id, source_group)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tg_jobs (
                id SERIAL PRIMARY KEY,
                job_type VARCHAR(20) NOT NULL,
                target_group VARCHAR(200),
                source_group VARCHAR(200),
                status VARCHAR(20) DEFAULT 'pending',
                total_count INTEGER DEFAULT 0,
                done_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                workers_count INTEGER DEFAULT 5,
                delay_min INTEGER DEFAULT 20,
                delay_max INTEGER DEFAULT 60,
                filter_active BOOLEAN DEFAULT true,
                filter_hours INTEGER DEFAULT 48,
                created_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tg_logs (
                id SERIAL PRIMARY KEY,
                job_id INTEGER,
                account_id INTEGER,
                user_id BIGINT,
                action VARCHAR(50),
                result VARCHAR(30),
                message TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tg_warming_sessions (
                id SERIAL PRIMARY KEY,
                account_id INTEGER NOT NULL,
                status VARCHAR(20) DEFAULT 'running',
                days_required INTEGER DEFAULT 3,
                days_done INTEGER DEFAULT 0,
                started_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tg_blacklist (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(200),
                reason VARCHAR(100) DEFAULT 'privacy_restricted',
                added_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tg_settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tg_access_log (
                id SERIAL PRIMARY KEY,
                user_name VARCHAR(200),
                granted BOOLEAN,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)


# ─── Settings ─────────────────────────────────────────────────────────────────

def get_setting(key: str, default=None):
    with db_cursor() as cur:
        cur.execute("SELECT value FROM tg_settings WHERE key = %s", (key,))
        row = cur.fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO tg_settings (key, value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """, (key, value))


def log_access_attempt(user_name: str, granted: bool):
    with db_cursor() as cur:
        cur.execute("INSERT INTO tg_access_log (user_name, granted) VALUES (%s, %s)", (user_name, granted))


def get_access_log(limit=50):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM tg_access_log ORDER BY created_at DESC LIMIT %s", (limit,))
        return cur.fetchall()


# ─── Accounts ─────────────────────────────────────────────────────────────────

def get_accounts(status=None):
    with db_cursor() as cur:
        if status:
            cur.execute("SELECT * FROM tg_accounts WHERE status = %s ORDER BY id", (status,))
        else:
            cur.execute("SELECT * FROM tg_accounts ORDER BY id")
        return cur.fetchall()


def get_account(account_id):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM tg_accounts WHERE id = %s", (account_id,))
        return cur.fetchone()


def add_account(phone, api_id, api_hash, device_model, system_version, app_version):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO tg_accounts (phone, api_id, api_hash, device_model, system_version, app_version)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (phone) DO UPDATE SET
                api_id = EXCLUDED.api_id, api_hash = EXCLUDED.api_hash,
                device_model = EXCLUDED.device_model, system_version = EXCLUDED.system_version,
                app_version = EXCLUDED.app_version
            RETURNING id
        """, (phone, api_id, api_hash, device_model, system_version, app_version))
        return cur.fetchone()["id"]


def update_account_session(account_id, session_string, status="active"):
    with db_cursor() as cur:
        cur.execute("""
            UPDATE tg_accounts SET session_string = %s, status = %s, last_used = NOW()
            WHERE id = %s
        """, (session_string, status, account_id))


def update_account_status(account_id, status, flood_wait_until=None):
    with db_cursor() as cur:
        cur.execute("""
            UPDATE tg_accounts SET status = %s, flood_wait_until = %s WHERE id = %s
        """, (status, flood_wait_until, account_id))


def update_account_2fa_password(account_id, password):
    with db_cursor() as cur:
        cur.execute("UPDATE tg_accounts SET two_factor_password = %s WHERE id = %s", (password, account_id))


def update_account_spambot_status(account_id, spambot_status, appeal_sent=False):
    with db_cursor() as cur:
        if appeal_sent:
            cur.execute("""
                UPDATE tg_accounts SET spambot_status = %s, spambot_checked_at = NOW(), appeal_sent_at = NOW()
                WHERE id = %s
            """, (spambot_status, account_id))
        else:
            cur.execute("""
                UPDATE tg_accounts SET spambot_status = %s, spambot_checked_at = NOW() WHERE id = %s
            """, (spambot_status, account_id))


def increment_daily_count(account_id):
    with db_cursor() as cur:
        cur.execute("""
            UPDATE tg_accounts SET
                daily_add_count = CASE WHEN daily_add_date = CURRENT_DATE THEN daily_add_count + 1 ELSE 1 END,
                daily_add_date = CURRENT_DATE, last_used = NOW()
            WHERE id = %s
        """, (account_id,))


def delete_account(account_id):
    with db_cursor() as cur:
        cur.execute("DELETE FROM tg_accounts WHERE id = %s", (account_id,))


def delete_accounts_bulk(account_ids: list):
    if not account_ids:
        return 0
    with db_cursor() as cur:
        cur.execute("DELETE FROM tg_accounts WHERE id = ANY(%s)", (account_ids,))
        return cur.rowcount


# ─── Proxies ──────────────────────────────────────────────────────────────────

def get_proxies():
    with db_cursor() as cur:
        cur.execute("SELECT * FROM tg_proxies ORDER BY id")
        return cur.fetchall()


def add_proxy(proxy_type, host, port, username=None, password=None):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO tg_proxies (proxy_type, host, port, username, password)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (proxy_type, host, port, username, password))
        return cur.fetchone()["id"]


def assign_proxy_to_account(proxy_id, account_id):
    with db_cursor() as cur:
        cur.execute("UPDATE tg_proxies SET account_id = %s WHERE id = %s", (account_id, proxy_id))
        cur.execute("UPDATE tg_accounts SET proxy_id = %s WHERE id = %s", (proxy_id, account_id))


def get_account_proxy(account_id):
    with db_cursor() as cur:
        cur.execute("""
            SELECT p.* FROM tg_proxies p
            JOIN tg_accounts a ON a.proxy_id = p.id
            WHERE a.id = %s
        """, (account_id,))
        return cur.fetchone()


def mark_proxy_inactive(proxy_id):
    with db_cursor() as cur:
        cur.execute("UPDATE tg_proxies SET is_active = false, last_checked = NOW() WHERE id = %s", (proxy_id,))


def mark_proxy_active(proxy_id):
    with db_cursor() as cur:
        cur.execute("UPDATE tg_proxies SET is_active = true, last_checked = NOW() WHERE id = %s", (proxy_id,))


def delete_proxy(proxy_id):
    with db_cursor() as cur:
        cur.execute("DELETE FROM tg_proxies WHERE id = %s", (proxy_id,))


def delete_inactive_proxies() -> int:
    with db_cursor() as cur:
        cur.execute("DELETE FROM tg_proxies WHERE is_active = false")
        return cur.rowcount


# ─── Members ──────────────────────────────────────────────────────────────────

def save_members(members_list, source_group):
    with db_cursor() as cur:
        for m in members_list:
            cur.execute("""
                INSERT INTO tg_members (user_id, username, first_name, last_name, access_hash, phone, source_group, last_seen)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, source_group) DO UPDATE SET
                    username = EXCLUDED.username, last_seen = EXCLUDED.last_seen, status = 'pending'
            """, (
                m.get("user_id"), m.get("username"), m.get("first_name"),
                m.get("last_name"), m.get("access_hash"), m.get("phone"),
                source_group, m.get("last_seen")
            ))


def get_pending_members(source_group=None, limit=1000):
    with db_cursor() as cur:
        if source_group:
            cur.execute("""
                SELECT m.* FROM tg_members m
                WHERE m.status = 'pending' AND m.source_group = %s
                AND NOT EXISTS (SELECT 1 FROM tg_blacklist b WHERE b.user_id = m.user_id)
                ORDER BY m.id LIMIT %s
            """, (source_group, limit))
        else:
            cur.execute("""
                SELECT m.* FROM tg_members m
                WHERE m.status = 'pending'
                AND NOT EXISTS (SELECT 1 FROM tg_blacklist b WHERE b.user_id = m.user_id)
                ORDER BY m.id LIMIT %s
            """, (limit,))
        return cur.fetchall()


def update_member_status(user_id, source_group, status, account_id=None, error_msg=None):
    with db_cursor() as cur:
        cur.execute("""
            UPDATE tg_members SET status = %s, added_by_account_id = %s,
                added_at = CASE WHEN %s = 'added' THEN NOW() ELSE added_at END,
                error_msg = %s
            WHERE user_id = %s AND source_group = %s
        """, (status, account_id, status, error_msg, user_id, source_group))


# ─── Blacklist ────────────────────────────────────────────────────────────────

def add_to_blacklist(user_id, username=None, reason="privacy_restricted"):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO tg_blacklist (user_id, username, reason)
            VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING
        """, (user_id, username, reason))


def is_blacklisted(user_id):
    with db_cursor() as cur:
        cur.execute("SELECT 1 FROM tg_blacklist WHERE user_id = %s", (user_id,))
        return cur.fetchone() is not None


def get_blacklist(limit=500):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM tg_blacklist ORDER BY added_at DESC LIMIT %s", (limit,))
        return cur.fetchall()


def get_blacklist_count():
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM tg_blacklist")
        return cur.fetchone()["total"]


def clear_blacklist():
    with db_cursor() as cur:
        cur.execute("DELETE FROM tg_blacklist")


# ─── Jobs & Logs ──────────────────────────────────────────────────────────────

def add_log(job_id, account_id, user_id, action, result, message=""):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO tg_logs (job_id, account_id, user_id, action, result, message)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (job_id, account_id, user_id, action, result, message))


def create_job(job_type, target_group, source_group, workers=5, delay_min=20, delay_max=60, filter_active=True, filter_hours=48):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO tg_jobs (job_type, target_group, source_group, workers_count, delay_min, delay_max, filter_active, filter_hours)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (job_type, target_group, source_group, workers, delay_min, delay_max, filter_active, filter_hours))
        return cur.fetchone()["id"]


def update_job(job_id, status=None, total=None, done=None, errors=None):
    with db_cursor() as cur:
        parts, vals = [], []
        if status:
            parts.append("status = %s")
            vals.append(status)
            if status in ("completed", "stopped"):
                parts.append("completed_at = NOW()")
        if total is not None:
            parts.append("total_count = %s")
            vals.append(total)
        if done is not None:
            parts.append("done_count = done_count + %s")
            vals.append(done)
        if errors is not None:
            parts.append("error_count = error_count + %s")
            vals.append(errors)
        if parts:
            vals.append(job_id)
            cur.execute(f"UPDATE tg_jobs SET {', '.join(parts)} WHERE id = %s", vals)


def get_jobs(limit=20):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM tg_jobs ORDER BY created_at DESC LIMIT %s", (limit,))
        return cur.fetchall()


def get_logs(job_id=None, limit=100):
    with db_cursor() as cur:
        if job_id:
            cur.execute("""
                SELECT l.*, a.phone FROM tg_logs l
                LEFT JOIN tg_accounts a ON l.account_id = a.id
                WHERE l.job_id = %s ORDER BY l.created_at DESC LIMIT %s
            """, (job_id, limit))
        else:
            cur.execute("""
                SELECT l.*, a.phone FROM tg_logs l
                LEFT JOIN tg_accounts a ON l.account_id = a.id
                ORDER BY l.created_at DESC LIMIT %s
            """, (limit,))
        return cur.fetchall()


def get_stats():
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) as total, status FROM tg_accounts GROUP BY status")
        account_stats = {r["status"]: r["total"] for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) as total, status FROM tg_members GROUP BY status")
        member_stats = {r["status"]: r["total"] for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) as total FROM tg_proxies WHERE is_active = true")
        proxy_count = cur.fetchone()["total"]
        cur.execute("SELECT COALESCE(SUM(done_count), 0) as total_added FROM tg_jobs WHERE DATE(created_at) = CURRENT_DATE")
        today_added = cur.fetchone()["total_added"]
        cur.execute("SELECT COUNT(*) as total FROM tg_blacklist")
        blacklist_count = cur.fetchone()["total"]
        return {
            "accounts": account_stats,
            "members": member_stats,
            "proxies": proxy_count,
            "today_added": today_added,
            "blacklist": blacklist_count,
        }


# ─── DB Export / Import (COMPLETE — كل البيانات بدون استثناء) ────────────────

# ترتيب الجداول: من المستقلة للتابعة (لتجنب مشاكل Foreign Keys عند الاستيراد)
_EXPORT_ORDER = [
    "tg_settings",
    "tg_accounts",
    "tg_proxies",
    "tg_blacklist",
    "tg_members",
    "tg_jobs",
    "tg_logs",
    "tg_warming_sessions",
    "tg_access_log",
]

# أعمدة UNIQUE / PRIMARY KEY لكل جدول (لـ ON CONFLICT)
_TABLE_CONFLICT_COLS = {
    "tg_settings": "(key)",
    "tg_accounts": "(phone)",
    "tg_blacklist": "(user_id)",
    "tg_members": "(user_id, source_group)",
}

# أعمدة حساسة يمكن حذفها بخيار include_sensitive=False
_SENSITIVE_COLS = {"session_string", "two_factor_password", "api_hash", "password", "value"}

# الجداول التي عمود value فيها حساس (tg_settings يحتوي كلمة المرور)
_SENSITIVE_TABLES = {"tg_settings"}


def _serialize_value(v):
    """تحويل قيم Python لتوافق JSON."""
    if isinstance(v, (datetime,)):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return v


def export_db_json(include_sensitive: bool = False) -> str:
    """
    تصدير كامل لقاعدة البيانات — كل الجداول وكل الأعمدة.
    include_sensitive=True: يشمل sessions وكلمات المرور وAPI Hash (للنقل الكامل بين السيرفرات).
    include_sensitive=False: يحذف البيانات الحساسة (للمشاركة أو النسخ الاحتياطي الآمن).
    """
    export_data = {
        "__meta__": {
            "exported_at": datetime.now().isoformat(),
            "include_sensitive": include_sensitive,
            "tables": _EXPORT_ORDER,
        }
    }

    with db_cursor() as cur:
        for table in _EXPORT_ORDER:
            try:
                cur.execute(f"SELECT * FROM {table} ORDER BY id LIMIT 200000")
                rows = []
                for row in cur.fetchall():
                    row_dict = {}
                    for k, v in dict(row).items():
                        if not include_sensitive:
                            # للـ tg_settings: نحذف كلمة المرور وبعض الإعدادات الحساسة
                            if table in _SENSITIVE_TABLES and k == "value":
                                key_name = row_dict.get("key", "")
                                if key_name in ("master_password_hash", "bot_token", "global_2fa_password"):
                                    continue
                            elif k in _SENSITIVE_COLS - {"value"}:
                                continue
                        row_dict[k] = _serialize_value(v)
                    rows.append(row_dict)
                export_data[table] = rows
            except Exception as e:
                export_data[table] = {"__error__": str(e)}

    return json.dumps(export_data, ensure_ascii=False, indent=2, default=str)


def import_db_json(json_str: str) -> dict:
    """
    استيراد كامل من JSON — يُدرج كل السجلات من كل الجداول.
    لا يحذف أي بيانات موجودة — يتخطى التكرارات بـ ON CONFLICT DO NOTHING.
    """
    data = json.loads(json_str)
    results = {}

    # إزالة مفتاح الـ meta
    for key in list(data.keys()):
        if key.startswith("__"):
            data.pop(key)

    # ترتيب الاستيراد من مستقل لتابع
    import_order = _EXPORT_ORDER

    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        for table in import_order:
            rows = data.get(table)
            if not rows or isinstance(rows, dict):
                results[table] = 0
                continue

            inserted = 0
            skipped = 0

            for row in rows:
                if not isinstance(row, dict) or not row:
                    continue

                cols = list(row.keys())
                vals = [row[c] for c in cols]

                if not cols:
                    continue

                col_str = ", ".join(f'"{c}"' for c in cols)
                placeholders = ", ".join(["%s"] * len(cols))

                conflict_clause = ""
                if table in _TABLE_CONFLICT_COLS:
                    conflict_clause = f"ON CONFLICT {_TABLE_CONFLICT_COLS[table]} DO NOTHING"
                else:
                    conflict_clause = "ON CONFLICT DO NOTHING"

                sql = f'INSERT INTO {table} ({col_str}) VALUES ({placeholders}) {conflict_clause}'

                try:
                    cur.execute(sql, vals)
                    if cur.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1
                except Exception:
                    skipped += 1

            results[table] = {"inserted": inserted, "skipped": skipped}

        # إعادة ضبط SERIAL sequences بعد الاستيراد
        for table in import_order:
            try:
                cur.execute(f"""
                    SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                        COALESCE((SELECT MAX(id) FROM {table}), 1))
                """)
            except Exception:
                pass

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()

    return results
