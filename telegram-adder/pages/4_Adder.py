import streamlit as st
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.database import (
    init_db, get_accounts, get_pending_members, create_job,
    update_job, get_jobs, get_account
)
from core.session_manager import connect_account
from core.adder import WorkerManager

st.set_page_config(page_title="الإضافة | Telegram Adder Pro", page_icon="➕", layout="wide")
init_db()
from core.auth import require_auth
require_auth()

st.sidebar.markdown(f"👤 **{st.session_state.get('tg_user_name', 'Admin')}**")
if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.title("➕ إضافة الأعضاء — نظام Workers المتوازي")
st.markdown("كل حساب يعمل كـ **Worker مستقل**. عند FloodWait يتجمد الحساب ويكمل باقي الحسابات.")
st.divider()

active_accounts = get_accounts(status="active")
if not active_accounts:
    st.warning("⚠️ لا توجد حسابات نشطة. أضف حسابات أولاً.")
    st.stop()

pending_members = get_pending_members(limit=10000)
if not pending_members:
    st.warning("⚠️ لا توجد أعضاء في الانتظار. اسحب أعضاء أولاً من صفحة **السكرابر**.")
    st.stop()

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("⚙️ إعدادات الإضافة")
    target_group = st.text_input(
        "المجموعة الهدف (للإضافة إليها)",
        placeholder="@targetgroup أو رابط الدعوة"
    )
    source_group_filter = st.selectbox(
        "مصدر الأعضاء",
        options=["الكل"] + list({m["source_group"] for m in pending_members if m.get("source_group")}),
    )
    st.subheader("👥 اختيار الحسابات")
    selected_accounts = st.multiselect(
        "الحسابات التي ستُستخدم كـ Workers",
        options=[f"{acc['phone']} (ID: {acc['id']})" for acc in active_accounts],
        default=[f"{acc['phone']} (ID: {acc['id']})" for acc in active_accounts[:5]],
        help="كل حساب = Worker مستقل يعمل بالتوازي"
    )
    selected_account_ids = [int(s.split("ID: ")[-1].rstrip(")")) for s in selected_accounts]

with col2:
    st.subheader("🎛️ إعدادات متقدمة")
    delay_min = st.number_input("أقل تأخير (ثانية)", min_value=5, max_value=300, value=20)
    delay_max = st.number_input("أكبر تأخير (ثانية)", min_value=10, max_value=600, value=60)
    daily_limit = st.number_input("الحد اليومي لكل حساب", min_value=5, max_value=50, value=30)
    st.divider()
    members_to_use = get_pending_members(
        source_group_filter if source_group_filter != "الكل" else None,
        limit=5000
    )
    st.metric("أعضاء في الانتظار", len(members_to_use))
    st.metric("Workers محددة", len(selected_account_ids))
    estimated = len(selected_account_ids) * daily_limit
    st.metric("الإضافات المتوقعة (اليوم)", min(estimated, len(members_to_use)))

st.divider()

if "adder_running" not in st.session_state:
    st.session_state["adder_running"] = False

start_col, stop_col = st.columns(2)

with start_col:
    start_btn = st.button(
        "🚀 بدء الإضافة",
        type="primary",
        disabled=st.session_state.get("adder_running", False) or not target_group or not selected_account_ids
    )

with stop_col:
    if st.session_state.get("adder_running"):
        if st.button("⛔ إيقاف", type="secondary"):
            st.session_state["adder_running"] = False
            st.warning("تم إيقاف الإضافة.")

if start_btn and target_group and selected_account_ids:
    st.session_state["adder_running"] = True

    with st.status("🔄 جاري الإضافة...", expanded=True) as status_widget:
        job_id = create_job(
            "add", target_group.strip(),
            source_group_filter if source_group_filter != "الكل" else "all",
            workers=len(selected_account_ids),
            delay_min=delay_min, delay_max=delay_max
        )
        st.write(f"✅ تم إنشاء المهمة ID: {job_id}")

        async def run_add_job():
            manager = WorkerManager(
                job_id=job_id, target_group=target_group.strip(),
                source_group=source_group_filter if source_group_filter != "الكل" else "all",
                delay_min=delay_min, delay_max=delay_max
            )
            members_filtered = get_pending_members(
                source_group_filter if source_group_filter != "الكل" else None,
                limit=len(selected_account_ids) * daily_limit
            )
            queued, blacklisted = manager.put_members(list(members_filtered))
            if blacklisted:
                st.write(f"⛔ تم تخطي {blacklisted} من القائمة السوداء")

            clients_accounts = []
            for acc_id in selected_account_ids:
                try:
                    client = await connect_account(acc_id)
                    clients_accounts.append((client, acc_id))
                except Exception as e:
                    st.write(f"⚠️ تعذر الاتصال بحساب {acc_id}: {e}")

            if not clients_accounts:
                raise Exception("لا توجد حسابات متصلة")

            st.write(f"🔗 تم الاتصال بـ {len(clients_accounts)} حساب — {queued} عضو في الطابور")
            final_stats = await manager.run_all(clients_accounts)

            for client, _ in clients_accounts:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            return final_stats

        try:
            final_stats = asyncio.run(run_add_job())
            st.session_state["adder_running"] = False
            status_widget.update(label="✅ اكتملت الإضافة!", state="complete")
            st.success(f"""
            **نتائج الإضافة:**
            - ✅ تمت الإضافة: **{final_stats.get('added', 0)}**
            - 🔒 خصوصية مقيدة + أُضيفوا للقائمة السوداء: **{final_stats.get('privacy', 0)}**
            - 🌊 FloodWait: **{final_stats.get('flood', 0)}** حساب تجمّد
            - ⛔ تم تخطيهم (قائمة سوداء): **{final_stats.get('blacklisted', 0)}**
            - ❌ أخطاء أخرى: **{final_stats.get('error', 0)}**
            """)
        except Exception as e:
            st.session_state["adder_running"] = False
            st.error(f"خطأ: {e}")
            update_job(job_id, status="failed")

st.divider()
st.subheader("📋 سجل العمليات الأخيرة")
jobs = get_jobs(limit=5)
if jobs:
    import pandas as pd
    df = pd.DataFrame([dict(j) for j in jobs if j["job_type"] == "add"])
    if not df.empty:
        st.dataframe(df[["id", "target_group", "status", "total_count", "done_count", "error_count", "created_at"]],
                     use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد عمليات إضافة سابقة.")
