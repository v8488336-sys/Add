"""
الإعدادات الشاملة:
  0 - كلمة المرور والأمان
  1 - 2FA العالمية (كلمة مرور ثابتة تُستخدم عند تسجيل الدخول)
  2 - بوت الإشعارات
  3 - تصدير/استيراد DB (كامل)
  4 - تنظيف الجلسات والبروكسيات
  5 - النشر على Railway
  6 - سجل الدخول
"""
import streamlit as st
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.database import (
    init_db, get_accounts, get_proxies, get_setting, set_setting,
    update_account_status, delete_accounts_bulk, delete_inactive_proxies,
    mark_proxy_inactive, get_access_log, export_db_json, import_db_json,
)
from core.auth import (
    set_master_password, is_password_set, verify_password, require_auth
)
from core.session_manager import connect_account

st.set_page_config(page_title="الإعدادات | Telegram Adder Pro", page_icon="⚙️", layout="wide")
init_db()
require_auth()

st.sidebar.markdown(f"👤 **{st.session_state.get('tg_user_name', 'Admin')}**")
if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.title("⚙️ الإعدادات")
st.divider()

tabs = st.tabs([
    "🔐 كلمة المرور والأمان",
    "🔑 2FA العالمية",
    "🤖 بوت الإشعارات",
    "💾 تصدير/استيراد DB",
    "🧹 تنظيف الجلسات والبروكسيات",
    "🚂 النشر على Railway",
    "📜 سجل الدخول",
])

# ─── Tab 0: Password & Security ───────────────────────────────────────────────
with tabs[0]:
    st.subheader("🔐 إدارة كلمة المرور الرئيسية")
    st.markdown("""
    كلمة المرور تحمي **كامل التطبيق** — أي شخص يفتح الرابط بدون كلمة المرور لن يرى شيئاً.
    """)

    pw_set = is_password_set()
    st.info(f"الحالة: {'✅ كلمة مرور مُفعَّلة' if pw_set else '⚠️ لا توجد كلمة مرور — التطبيق مكشوف!'}")

    with st.form("change_pw_form"):
        st.markdown("**تغيير كلمة المرور:**")
        if pw_set:
            old_pw = st.text_input("كلمة المرور الحالية", type="password")
        new_pw = st.text_input("كلمة المرور الجديدة", type="password")
        confirm_pw = st.text_input("تأكيد كلمة المرور الجديدة", type="password")
        change_btn = st.form_submit_button("💾 حفظ كلمة المرور")

    if change_btn:
        if pw_set and not verify_password(old_pw):
            st.error("❌ كلمة المرور الحالية غير صحيحة")
        elif len(new_pw) < 4:
            st.error("⚠️ كلمة المرور قصيرة جداً (4 أحرف على الأقل)")
        elif new_pw != confirm_pw:
            st.error("⚠️ كلمتا المرور غير متطابقتَين")
        else:
            set_master_password(new_pw)
            st.success("✅ تم تحديث كلمة المرور!")

    st.divider()
    st.markdown("""
    > **كيف يعمل نظام الحماية؟**
    > - كل شخص يفتح الرابط يرى شاشة تسجيل الدخول فقط
    > - بدون كلمة المرور لا يمكن رؤية أي بيانات أو التحكم بأي حساب
    > - كل جلسة مستقلة — تسجيل الخروج يمسح الجلسة فوراً
    > - كلمة المرور مُخزَّنة بتشفير SHA-256 في قاعدة البيانات
    """)

# ─── Tab 1: Global 2FA Password ───────────────────────────────────────────────
with tabs[1]:
    st.subheader("🔑 كلمة مرور 2FA العالمية (Global Default)")
    st.markdown("""
    إذا كانت **معظم** حساباتك تستخدم نفس كلمة مرور 2FA (Cloud Password)،  
    ضعها هنا مرةً واحدة — سيستخدمها النظام تلقائياً عند الاتصال بأي حساب لم تُعيَّن له كلمة مرور خاصة.

    **الأولوية عند الاتصال:**
    1. 🔐 كلمة مرور **خاصة بالحساب** (من صفحة الحسابات) ← تُستخدم أولاً
    2. 🌐 كلمة مرور **عالمية** (من هنا) ← تُستخدم إذا لا توجد كلمة خاصة
    3. ❌ إذا لا توجد كلمة مرور وطُلبت 2FA ← خطأ واضح

    **متى تُستخدم؟**
    - عند الاتصال بأي حساب بدون session (تسجيل دخول تفاعلي)
    - عند فحص الجلسات في صفحة التنظيف
    - عند تشغيل Workers للإضافة
    """)

    current_global_2fa = get_setting("global_2fa_password")
    has_global = bool(current_global_2fa)

    st.info(f"الحالة الحالية: {'✅ كلمة مرور عالمية مُفعَّلة' if has_global else '⚪ لا توجد كلمة مرور عالمية'}")

    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        with st.form("global_2fa_form"):
            g2fa_pw = st.text_input(
                "كلمة مرور 2FA العالمية",
                type="password",
                placeholder="اتركه فارغاً لإلغاء الكلمة العالمية",
                help="هذه هي Cloud Password أو Two-Step Verification Password الخاصة بحساباتك"
            )
            col_save, col_clear = st.columns(2)
            with col_save:
                save_g2fa = st.form_submit_button("💾 حفظ", use_container_width=True)
            with col_clear:
                clear_g2fa = st.form_submit_button("🗑️ مسح العالمية", use_container_width=True)

        if save_g2fa:
            if g2fa_pw:
                set_setting("global_2fa_password", g2fa_pw)
                st.success("✅ تم حفظ كلمة مرور 2FA العالمية!")
            else:
                st.warning("أدخل كلمة مرور أولاً.")

        if clear_g2fa:
            set_setting("global_2fa_password", "")
            st.success("✅ تم مسح كلمة مرور 2FA العالمية.")
            st.rerun()

    with col_f2:
        st.markdown("**حسابات بكلمة مرور خاصة:**")
        accounts = get_accounts()
        with_own_pw = [a for a in accounts if a.get("two_factor_password")]
        without_pw = [a for a in accounts if not a.get("two_factor_password")]
        st.metric("لها كلمة مرور خاصة", len(with_own_pw))
        st.metric("ستستخدم العالمية", len(without_pw))
        if has_global:
            st.success(f"✅ {len(without_pw)} حساب يستفيد من الكلمة العالمية")
        else:
            st.warning(f"⚠️ {len(without_pw)} حساب بلا أي 2FA")

# ─── Tab 2: Telegram Bot Notifications ───────────────────────────────────────
with tabs[2]:
    st.subheader("🤖 بوت تيليجرام للإشعارات")
    st.markdown("""
    عند تفعيل هذا البوت، ستصلك رسالة تليجرام **فور تسجيل دخول أي شخص** للتطبيق.

    **للحصول على Bot Token:** راسل @BotFather → `/newbot` → انسخ الـ Token

    **للحصول على Chat ID:** راسل @userinfobot أو افتح `https://api.telegram.org/bot<TOKEN>/getUpdates`
    """)

    current_token = get_setting("bot_token") or ""
    current_admin = get_setting("admin_chat_id") or ""

    with st.form("bot_settings_form"):
        bot_token = st.text_input(
            "Bot Token",
            value="•" * min(len(current_token), 20) if current_token else "",
            placeholder="123456789:ABCdefGHIjklMNOpqrSTUvwxyz",
            type="password",
        )
        admin_chat_id = st.text_input(
            "Admin Chat ID (رقم ID حسابك)",
            value=current_admin,
            placeholder="123456789",
        )
        save_bot_btn = st.form_submit_button("💾 حفظ إعدادات البوت")

    if save_bot_btn:
        if bot_token and not bot_token.startswith("•"):
            set_setting("bot_token", bot_token.strip())
        if admin_chat_id:
            set_setting("admin_chat_id", admin_chat_id.strip())
        st.success("✅ تم حفظ إعدادات البوت!")

    if current_token and current_admin:
        if st.button("📡 اختبار الإشعار"):
            import requests as req
            try:
                r = req.post(
                    f"https://api.telegram.org/bot{current_token}/sendMessage",
                    json={"chat_id": current_admin,
                          "text": "✅ Telegram Adder Pro — اختبار الإشعارات ناجح!"},
                    timeout=5,
                )
                if r.status_code == 200:
                    st.success("✅ تم إرسال الرسالة بنجاح!")
                else:
                    st.error(f"❌ فشل الإرسال: {r.text}")
            except Exception as e:
                st.error(f"خطأ: {e}")
        st.info(f"البوت: {'✅ مُفعَّل' if current_token else '❌ غير مُفعَّل'} | Admin ID: {current_admin or '—'}")
    else:
        st.warning("⚠️ لم يتم إعداد البوت بعد")

# ─── Tab 3: DB Export / Import ────────────────────────────────────────────────
with tabs[3]:
    st.subheader("💾 تصدير واستيراد قاعدة البيانات")
    st.markdown("""
    استخدم هذا القسم **لنقل البيانات بين السيرفرات** (مثلاً من Railway إلى Railway آخر).
    """)

    col_ex, col_im = st.columns(2)

    with col_ex:
        st.markdown("### ⬇️ تصدير (Export)")
        st.markdown("""
        يُصدّر **كل الجداول وكل السجلات** بدون استثناء:
        - ✅ الحسابات | البروكسيات | الأعضاء
        - ✅ المهام | السجلات | القائمة السوداء
        - ✅ الإعدادات | سجل الدخول
        """)

        include_sensitive = st.checkbox(
            "✅ تضمين Sessions وكلمات المرور وAPI Hash",
            value=True,
            help="فعّل هذا للنقل الكامل بين السيرفرات — لا تشارك الملف مع أحد",
        )
        if include_sensitive:
            st.warning("⚠️ الملف يحتوي بيانات حساسة — احفظه في مكان آمن")
        else:
            st.info("ℹ️ الملف بدون Sessions — مناسب للمشاركة الآمنة")

        if st.button("📥 تصدير قاعدة البيانات", type="primary"):
            with st.spinner("جاري تصدير كل البيانات..."):
                json_data = export_db_json(include_sensitive=include_sensitive)
            st.download_button(
                label="💾 تحميل tg_adder_backup.json",
                data=json_data,
                file_name="tg_adder_backup.json",
                mime="application/json",
            )
            import json as _json
            meta = _json.loads(json_data)
            st.success(f"✅ جاهز للتحميل! ({len(json_data)//1024} KB)")
            tables = meta.get("__meta__", {}).get("tables", [])
            for t in tables:
                count = len(meta.get(t, []))
                if count:
                    st.write(f"• **{t}**: {count} سجل")

    with col_im:
        st.markdown("### ⬆️ استيراد (Import)")
        st.markdown("""
        يُدرج **كل السجلات من كل الجداول** في الملف.  
        لا يحذف أي بيانات موجودة — يتخطى التكرارات تلقائياً.
        """)
        st.warning("⚠️ تأكد من تشغيل `init_db` أولاً (يحدث تلقائياً عند فتح التطبيق)")

        uploaded = st.file_uploader("رفع ملف backup.json", type=["json"])
        if uploaded:
            if st.button("📤 استيراد البيانات", type="secondary"):
                with st.spinner("جاري الاستيراد..."):
                    try:
                        json_str = uploaded.read().decode("utf-8")
                        results = import_db_json(json_str)
                        st.success("✅ تم الاستيراد بنجاح!")
                        for table, info in results.items():
                            if isinstance(info, dict):
                                ins = info.get("inserted", 0)
                                skp = info.get("skipped", 0)
                                if ins or skp:
                                    st.write(f"• **{table}**: ✅ أُضيف {ins} | ⏭ تخطّى {skp}")
                    except Exception as e:
                        st.error(f"خطأ في الاستيراد: {e}")

# ─── Tab 4: Cleanup ────────────────────────────────────────────────────────────
with tabs[4]:
    st.subheader("🧹 تنظيف الجلسات والبروكسيات")
    st.markdown("يتحقق النظام من كل حساب وبروكسي ويحذف أو يعطّل ما لا يعمل.")

    all_accounts = get_accounts()
    all_proxies = get_proxies()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("إجمالي الحسابات", len(all_accounts))
        banned = [a for a in all_accounts if a["status"] in ("banned", "restricted")]
        no_session = [a for a in all_accounts if not a.get("session_string")]
        st.metric("حسابات محظورة/مقيدة", len(banned))
        st.metric("حسابات بدون session", len(no_session))
    with col2:
        st.metric("إجمالي البروكسيات", len(all_proxies))
        inactive_p = [p for p in all_proxies if not p.get("is_active", True)]
        st.metric("بروكسيات غير نشطة", len(inactive_p))

    st.divider()
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("### 👤 تنظيف الحسابات")

        if st.button("🔍 فحص صلاحية الجلسات"):
            dead_ids = []
            progress = st.progress(0)
            status_text = st.empty()
            accs_with_session = [a for a in all_accounts if a.get("session_string")]

            for i, acc in enumerate(accs_with_session):
                status_text.text(f"⏳ فحص {acc['phone']} ({i+1}/{len(accs_with_session)})...")
                try:
                    client = asyncio.run(connect_account(acc["id"]))
                    asyncio.run(client.disconnect())
                    st.write(f"✅ {acc['phone']} — يعمل")
                except Exception as e:
                    st.write(f"❌ {acc['phone']} — معطّل: {str(e)[:80]}")
                    dead_ids.append(acc["id"])
                    update_account_status(acc["id"], "banned")
                progress.progress((i + 1) / max(len(accs_with_session), 1))

            status_text.text("")
            if dead_ids:
                st.warning(f"⚠️ {len(dead_ids)} حساب معطّل — حالتهم الآن 'banned'")
            else:
                st.success("✅ كل الحسابات تعمل!")

        if banned:
            if st.button(f"🗑️ حذف المحظورة ({len(banned)} حساب)", type="secondary"):
                if st.session_state.get("confirm_del_banned"):
                    deleted = delete_accounts_bulk([a["id"] for a in banned])
                    st.session_state.pop("confirm_del_banned", None)
                    st.success(f"✅ تم حذف {deleted} حساب")
                    st.rerun()
                else:
                    st.session_state["confirm_del_banned"] = True
                    st.warning("اضغط مرة ثانية للتأكيد")

        if no_session:
            if st.button(f"🗑️ حذف بدون Session ({len(no_session)} حساب)", type="secondary"):
                delete_accounts_bulk([a["id"] for a in no_session])
                st.success("✅ تم الحذف")
                st.rerun()

    with col_b:
        st.markdown("### 🌐 تنظيف البروكسيات")

        if st.button("🔍 فحص صلاحية البروكسيات"):
            import socket
            progress2 = st.progress(0)
            dead_proxies = []
            for i, proxy in enumerate(all_proxies):
                try:
                    s = socket.create_connection((proxy["host"], int(proxy["port"])), timeout=5)
                    s.close()
                    st.write(f"✅ {proxy['host']}:{proxy['port']} — يعمل")
                except Exception:
                    st.write(f"❌ {proxy['host']}:{proxy['port']} — لا يعمل")
                    mark_proxy_inactive(proxy["id"])
                    dead_proxies.append(proxy["id"])
                progress2.progress((i + 1) / max(len(all_proxies), 1))

            if dead_proxies:
                st.warning(f"⚠️ {len(dead_proxies)} بروكسي لا يعمل — تم تعطيله")
            else:
                st.success("✅ كل البروكسيات تعمل!")

        if inactive_p:
            if st.button(f"🗑️ حذف غير النشطة ({len(inactive_p)})", type="secondary"):
                deleted = delete_inactive_proxies()
                st.success(f"✅ تم حذف {deleted} بروكسي")
                st.rerun()

# ─── Tab 5: Railway Deployment ────────────────────────────────────────────────
with tabs[5]:
    st.subheader("🚂 النشر على Railway")
    st.markdown("Railway تدعم Python وPostgreSQL — مثالية لهذا المشروع.")

    with st.expander("1️⃣ رفع الكود على GitHub", expanded=True):
        st.markdown("""
        المشروع موجود على: **https://github.com/herk72/Add**

        لرفع أي تحديثات جديدة، شغّل هذه الأوامر من Replit Shell:
        ```bash
        git remote add github https://TOKEN@github.com/herk72/Add.git
        git push github main --force
        ```
        *(استبدل TOKEN بـ GitHub Personal Access Token)*
        """)

    with st.expander("2️⃣ إنشاء مشروع Railway"):
        st.markdown("""
        1. اذهب لـ [railway.app](https://railway.app) وسجّل بحساب GitHub
        2. **New Project** → **Deploy from GitHub repo** → اختر `herk72/Add`
        3. Railway يكتشف Python تلقائياً ويبني المشروع
        """)

    with st.expander("3️⃣ إضافة PostgreSQL"):
        st.markdown("""
        1. في مشروع Railway: **+ New** → **Database** → **Add PostgreSQL**
        2. انسخ **DATABASE_URL** من Variables في الـ PostgreSQL service
        3. ضعه في Variables للمشروع الرئيسي باسم `DATABASE_URL`
        """)

    with st.expander("4️⃣ أمر التشغيل (Start Command)"):
        st.code(
            "streamlit run telegram-adder/app.py "
            "--server.port $PORT --server.address 0.0.0.0 --server.headless true",
            language="bash"
        )

    with st.expander("5️⃣ ملف railway.toml"):
        toml_content = (
            "[build]\n"
            'builder = "nixpacks"\n\n'
            "[deploy]\n"
            'startCommand = "streamlit run telegram-adder/app.py '
            '--server.port $PORT --server.address 0.0.0.0 --server.headless true"\n'
            'restartPolicyType = "on_failure"\n'
            "restartPolicyMaxRetries = 5\n"
        )
        st.code(toml_content, language="toml")

    with st.expander("6️⃣ نقل قاعدة البيانات"):
        st.markdown("""
        1. **هنا (Replit):** تبويب **تصدير/استيراد DB** ← فعّل "تضمين Sessions" ← اضغط تصدير ← حمّل الملف
        2. **على Railway:** افتح التطبيق الجديد ← نفس التبويب ← ارفع الملف ← استيراد
        3. ✅ كل بياناتك (حسابات + sessions + بروكسيات + قائمة سوداء) ستنتقل كاملةً
        """)

    st.info("💡 الخطة المجانية محدودة — الخطة المدفوعة ($5/شهر) للتشغيل 24/7")

    reqs = (
        "streamlit>=1.32\n"
        "telethon>=1.34\n"
        "psycopg2-binary>=2.9\n"
        "plotly>=5.17\n"
        "pandas>=2.0\n"
        "PySocks>=1.7\n"
        "Faker>=18.0\n"
        "requests>=2.31\n"
    )
    st.markdown("### requirements.txt للنشر:")
    st.code(reqs, language="text")
    st.download_button("📥 تحميل requirements.txt", reqs, "requirements.txt", "text/plain")

# ─── Tab 6: Access Log ────────────────────────────────────────────────────────
with tabs[6]:
    st.subheader("📜 سجل الدخول")
    st.markdown("كل من حاول الدخول للتطبيق (ناجح أو فاشل).")

    access_log = get_access_log(limit=100)
    if access_log:
        import pandas as pd
        df = pd.DataFrame([dict(r) for r in access_log])
        df["granted"] = df["granted"].map({True: "✅ ناجح", False: "❌ فاشل"})
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد سجلات دخول بعد.")
