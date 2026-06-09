import streamlit as st
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.database import (
    init_db, get_accounts, create_job, add_log,
    get_blacklist, get_blacklist_count, clear_blacklist, add_to_blacklist,
    update_account_spambot_status
)
from core.session_manager import connect_account
from core.spambot_handler import check_and_appeal

st.set_page_config(page_title="Anti-Ban | Telegram Adder Pro", page_icon="🛡️", layout="wide")
init_db()
from core.auth import require_auth
require_auth()

st.sidebar.markdown(f"👤 **{st.session_state.get('tg_user_name', 'Admin')}**")
if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.title("🛡️ Anti-Ban & Evasion Center")
st.markdown("مركز الحماية من الحظر — فحص الحسابات عبر **@SpamBot** + رفع الحظر تلقائي + إدارة **القائمة السوداء**.")
st.divider()

tab1, tab2 = st.tabs(["🤖 SpamBot — فحص ورفع الحظر", "⛔ القائمة السوداء (Global Blacklist)"])

with tab1:
    st.subheader("🤖 فحص الحسابات عبر @SpamBot")
    st.markdown("""
    يتصل بـ **@SpamBot** تلقائياً ويفحص حالة كل حساب.  
    إذا كان الحساب مقيداً، يرسل **طلب رفع حظر (Appeal)** تلقائياً، ويضع الحساب في حالة **"انتظار"**.
    """)
    st.info("""
    **آلية العمل:** `/start` ← قراءة الرد ← إذا مقيد: ضغط "This is a mistake" ← إرسال نص Appeal ← تحديث الحالة
    """)

    accounts = get_accounts()
    if not accounts:
        st.warning("لا توجد حسابات.")
        st.stop()

    active_accounts = [a for a in accounts if a.get("session_string")]

    check_mode = st.radio("الوضع", ["فحص حساب واحد", "فحص جميع الحسابات"], horizontal=True, label_visibility="collapsed")

    if check_mode == "فحص حساب واحد":
        selected = st.selectbox(
            "اختر الحساب",
            options=[f"{a['phone']} — SpamBot: {a.get('spambot_status','unknown')} (ID: {a['id']})" for a in active_accounts]
        )
        if selected:
            acc_id = int(selected.split("ID: ")[-1].rstrip(")"))

            if st.button("🔍 فحص الآن", type="primary"):
                with st.status("⏳ جاري الفحص...", expanded=True) as s:
                    try:
                        client = asyncio.run(connect_account(acc_id))
                        job_id = create_job("spambot", None, None)
                        result = asyncio.run(check_and_appeal(client, acc_id, job_id))
                        asyncio.run(client.disconnect())
                        status_map = {
                            "clean": ("✅ الحساب نظيف!", "complete"),
                            "appeal_sent": ("📤 مقيد — تم إرسال طلب رفع الحظر!", "warning"),
                            "restricted": ("🔴 مقيد — تعذّر إرسال الطلب تلقائياً", "error"),
                            "unknown": ("❓ لم نستطع تحديد الحالة", "error"),
                            "error": ("❌ خطأ أثناء الفحص", "error"),
                        }
                        label, state = status_map.get(result["status"], ("❓", "error"))
                        s.update(label=label, state=state)
                        st.write(f"**رد SpamBot:** {result['message'][:400]}")
                    except Exception as e:
                        s.update(label=f"❌ خطأ: {e}", state="error")
                        st.error(str(e))
    else:
        if st.button("🔍 فحص جميع الحسابات", type="primary"):
            job_id = create_job("spambot_bulk", None, None)
            progress = st.progress(0)
            status_text = st.empty()
            results = []
            clients_accounts = []

            for acc in active_accounts:
                try:
                    status_text.text(f"⏳ اتصال بـ {acc['phone']}...")
                    client = asyncio.run(connect_account(acc["id"]))
                    clients_accounts.append((client, acc["id"], acc["phone"]))
                except Exception as e:
                    st.warning(f"⚠️ فشل الاتصال بـ {acc['phone']}: {e}")

            for i, (client, acc_id, phone) in enumerate(clients_accounts):
                status_text.text(f"📡 فحص {phone} ({i+1}/{len(clients_accounts)})...")
                result = asyncio.run(check_and_appeal(client, acc_id, job_id))
                asyncio.run(client.disconnect())
                results.append({"phone": phone, **result})
                progress.progress((i + 1) / len(clients_accounts))

            st.success("✅ اكتمل الفحص!")
            for r in results:
                icon = {"clean": "✅", "appeal_sent": "📤", "restricted": "🔴", "unknown": "❓", "error": "❌"}.get(r["status"], "❓")
                st.write(f"{icon} **{r['phone']}** — {r['status']}: {r['message'][:150]}")

    st.divider()
    st.subheader("📊 حالة SpamBot لكل الحسابات")
    if accounts:
        import pandas as pd
        df = pd.DataFrame([{
            "phone": a["phone"],
            "status": a["status"],
            "spambot_status": a.get("spambot_status", "unknown"),
            "spambot_checked_at": str(a.get("spambot_checked_at") or "لم يُفحص"),
            "appeal_sent_at": str(a.get("appeal_sent_at") or "—"),
        } for a in accounts])
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("""
    > **كيف أعرف إذا انفك الحظر؟**  
    > الحسابات ذات حالة `appeal_pending` يجب إعادة فحصها كل **24-72 ساعة**.  
    > اضغط "فحص الآن" على الحساب مرة أخرى — إذا رد SpamBot بـ "no limits" ستتحول حالته لـ `clean` تلقائياً.
    """)

with tab2:
    st.subheader("⛔ القائمة السوداء العالمية (Global Blacklist)")
    st.markdown("""
    كل مستخدم يرفض الإضافة بسبب **الخصوصية** أو حساب محذوف يُضاف هنا تلقائياً.  
    لن تضيع الحسابات الأخرى وقتها في محاولة إضافتهم مستقبلاً.
    """)

    bl_count = get_blacklist_count()
    col_m, col_n = st.columns([1, 3])
    with col_m:
        st.metric("إجمالي القائمة السوداء", bl_count)
    with col_n:
        if bl_count > 0:
            if st.button("🗑️ مسح القائمة السوداء كاملاً", type="secondary"):
                if st.session_state.get("confirm_clear_bl"):
                    clear_blacklist()
                    st.session_state.pop("confirm_clear_bl", None)
                    st.success("✅ تم المسح")
                    st.rerun()
                else:
                    st.session_state["confirm_clear_bl"] = True
                    st.warning("⚠️ اضغط مرة ثانية للتأكيد")

    with st.expander("➕ إضافة يدوية للقائمة السوداء"):
        with st.form("add_bl_form"):
            bl_uid = st.number_input("User ID", min_value=1, value=None)
            bl_uname = st.text_input("Username (اختياري)", placeholder="@username")
            bl_reason = st.selectbox("السبب", ["privacy_restricted", "deactivated", "always_banned", "manual"])
            bl_submit = st.form_submit_button("إضافة للقائمة")
        if bl_submit and bl_uid:
            add_to_blacklist(int(bl_uid), bl_uname.lstrip("@") if bl_uname else None, bl_reason)
            st.success(f"✅ تم إضافة {bl_uid}")
            st.rerun()

    blacklist = get_blacklist(limit=500)
    if blacklist:
        import pandas as pd
        df_bl = pd.DataFrame([dict(b) for b in blacklist])
        st.dataframe(df_bl, use_container_width=True, hide_index=True)
    else:
        st.info("القائمة السوداء فارغة — ستُملأ تلقائياً أثناء الإضافة.")
