import streamlit as st
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.database import init_db, get_accounts, create_job, add_log
from core.session_manager import connect_account
from core.account_warmer import warm_account, ai_chat_warming

st.set_page_config(page_title="تدفئة الحسابات | Telegram Adder Pro", page_icon="🔥", layout="wide")
init_db()
from core.auth import require_auth
require_auth()

st.sidebar.markdown(f"👤 **{st.session_state.get('tg_user_name', 'Admin')}**")
if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.title("🔥 تدفئة الحسابات (Account Warming)")
st.markdown("""
**لماذا التدفئة؟** الحسابات الجديدة لديها **Trust Score = صفر**.  
تدفئتها قبل الإضافة يرفع الثقة ويقلل نسبة الحظر.
""")
st.divider()

all_accounts = get_accounts()
tab1, tab2 = st.tabs(["🔥 تدفئة عادية", "🤖 AI Smart Warming (محادثة بين الحسابات)"])

with tab1:
    if not all_accounts:
        st.warning("لا توجد حسابات.")
        st.stop()

    selected_phones = st.multiselect("اختر الحسابات للتدفئة",
        options=[f"{acc['phone']} — {acc['status']} (ID: {acc['id']})" for acc in all_accounts])
    selected_ids = [int(s.split("ID: ")[-1].rstrip(")")) for s in selected_phones]

    col_a, col_b = st.columns(2)
    with col_a:
        warming_days = st.slider("عدد أيام التدفئة", min_value=1, max_value=7, value=3)
    with col_b:
        st.info(f"⏱️ التدفئة تستغرق {warming_days * 3}-{warming_days * 8} ساعات")

    if st.button("🔥 بدء التدفئة", type="primary", disabled=not selected_ids):
        job_id = create_job("warm", None, None)
        for acc_id in selected_ids:
            acc = next((a for a in all_accounts if a["id"] == acc_id), None)
            if not acc:
                continue
            with st.status(f"🔥 تدفئة {acc['phone']}...", expanded=True) as status:
                try:
                    client = asyncio.run(connect_account(acc_id))
                    success = asyncio.run(warm_account(client, acc_id, days=warming_days, job_id=job_id))
                    asyncio.run(client.disconnect())
                    if success:
                        status.update(label=f"✅ {acc['phone']} — تمت التدفئة!", state="complete")
                    else:
                        status.update(label=f"⚠️ {acc['phone']} — خطأ", state="error")
                except Exception as e:
                    status.update(label=f"❌ فشل", state="error")
                    st.error(str(e))
                    add_log(job_id, acc_id, None, "warm_connect", "error", str(e))

with tab2:
    st.subheader("🤖 محادثة ذكية بين حساباتك")
    st.markdown("""
    حساباتك تتحدث مع بعضها بمحادثات طبيعية متغيرة تبني **Trust Score عالٍ** وتخدع خوارزميات التليجرام.
    > ⚠️ يحتاج **حسابَين على الأقل**
    """)

    if len(all_accounts) < 2:
        st.warning("⚠️ تحتاج حسابَين على الأقل.")
    else:
        ai_selected = st.multiselect("اختر الحسابات",
            options=[f"{acc['phone']} (ID: {acc['id']})" for acc in all_accounts],
            default=[f"{acc['phone']} (ID: {acc['id']})" for acc in all_accounts[:2]])
        ai_selected_ids = [int(s.split("ID: ")[-1].rstrip(")")) for s in ai_selected]

        ai_rounds = st.slider("جولات المحادثة", min_value=1, max_value=5, value=2)
        st.code("صباح الخير ☀️ → الحمدلله تمام وانت? → شفت الأخبار اليوم? → يلا بحكيك بعدين 🙂", language=None)

        if st.button("🤖 بدء AI Smart Warming", type="primary", disabled=len(ai_selected_ids) < 2):
            job_id = create_job("ai_warm", None, None)
            with st.status("🤖 جاري AI Smart Warming...", expanded=True) as ai_status:
                try:
                    clients_accounts = []
                    for acc_id in ai_selected_ids:
                        acc = next((a for a in all_accounts if a["id"] == acc_id), None)
                        if not acc:
                            continue
                        client = asyncio.run(connect_account(acc_id))
                        clients_accounts.append((client, acc_id, acc["phone"]))

                    if len(clients_accounts) < 2:
                        st.error("فشل الاتصال بعدد كافٍ من الحسابات")
                    else:
                        asyncio.run(ai_chat_warming(clients_accounts, job_id=job_id, rounds=ai_rounds))
                        for client, _, _ in clients_accounts:
                            asyncio.run(client.disconnect())
                        ai_status.update(label="✅ AI Smart Warming اكتمل!", state="complete")
                        st.success(f"{ai_rounds} جولة محادثة بين {len(clients_accounts)} حساب.")
                except Exception as e:
                    ai_status.update(label="❌ خطأ", state="error")
                    st.error(str(e))

st.divider()
st.subheader("📊 حالة الحسابات")
if all_accounts:
    import pandas as pd
    df = pd.DataFrame([dict(a) for a in all_accounts])
    display_cols = ["id", "phone", "status", "device_model", "app_version", "daily_add_count", "spambot_status", "last_used"]
    available = [c for c in display_cols if c in df.columns]
    st.dataframe(df[available], use_container_width=True, hide_index=True)
