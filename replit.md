# Telegram Adder Pro ⚡

نظام إضافة أعضاء تليجرام احترافي (نسخة مدفوعة) — يعمل بـ String Sessions + Proxy Binding + AsyncIO Workers متوازية + Device Spoofing + Human Jitter + Account Warming + Captcha Bypass.

## تشغيل التطبيق

- `streamlit run telegram-adder/app.py --server.port 5000` — تشغيل لوحة التحكم
- الـ Workflow الافتراضي: `artifacts/telegram-adder: web`

## المكدس التقني

- **Python 3** + **Streamlit** — واجهة المستخدم
- **Telethon 1.43** — مكتبة تليجرام (MTProto)
- **PostgreSQL** + psycopg2 — تخزين الـ Sessions والبيانات
- **asyncio** — التوازي الحقيقي عبر Workers
- **PySocks** — دعم SOCKS5/HTTP proxy
- **Plotly + Pandas** — الرسوم البيانية

## هيكل الملفات

```
telegram-adder/
├── app.py                  # Dashboard الرئيسي
├── .streamlit/config.toml  # إعدادات Streamlit
├── core/
│   ├── database.py         # PostgreSQL schema + CRUD
│   ├── session_manager.py  # StringSession management
│   ├── device_spoofer.py   # توليد بيانات الجهاز العشوائية
│   ├── human_behavior.py   # Jitter + State simulation
│   ├── worker.py           # AsyncIO Queue + Workers
│   ├── scraper.py          # Smart member scraping
│   ├── adder.py            # إضافة الأعضاء + error handling
│   ├── account_warmer.py   # Account warming system
│   └── captcha_handler.py  # Inline button / captcha bypass
└── pages/
    ├── 1_Accounts.py       # إدارة الحسابات + تسجيل الدخول
    ├── 2_Proxies.py        # إدارة البروكسيات + ربط تلقائي
    ├── 3_Scraper.py        # سحب الأعضاء بفلاتر ذكية
    ├── 4_Adder.py          # الإضافة بنظام Workers
    ├── 5_Warming.py        # تدفئة الحسابات
    └── 6_Logs.py           # السجلات والإحصائيات
```

## قاعدة البيانات (جداول PostgreSQL)

- `tg_accounts` — الحسابات + Session Strings + Device params
- `tg_proxies` — البروكسيات مع الربط بالحسابات
- `tg_members` — الأعضاء المسحوبون + حالتهم
- `tg_jobs` — المهام (scrape/add/warm)
- `tg_logs` — السجل الكامل لكل عملية
- `tg_warming_sessions` — جلسات التدفئة

## الميزات الاحترافية المُطبَّقة

- ✅ String Sessions (بدلاً من ملفات SQLite)
- ✅ Proxy-to-Session Binding (SOCKS5/HTTP/SOCKS4)
- ✅ AsyncIO Queue + Workers متوازية
- ✅ Smart Scraping Filter (نشطون خلال X ساعة فقط)
- ✅ State Persistence — يكمل من نفس نقطة التوقف
- ✅ Device Spoofing — جهاز مختلف لكل حساب
- ✅ Human Jitter — تأخير عشوائي غير خطي
- ✅ UpdateStatusRequest — محاكاة الحضور
- ✅ Account Warming — تدفئة الحسابات الجديدة
- ✅ Captcha Bypass — ضغط الأزرار تلقائياً
- ✅ FloodWait Handler — تجميد الحساب + إرجاع الهدف للطابور
- ✅ Dashboard مباشر مع إحصائيات Plotly

## Environment Variables

- `DATABASE_URL` — PostgreSQL connection string (متوفر)

## User preferences

- المستخدم يريد نظام احترافي بمستوى commercial-grade
- الواجهة بالعربية
