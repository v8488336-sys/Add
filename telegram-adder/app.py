import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.database import init_db, get_stats, get_jobs, get_accounts

st.set_page_config(
    page_title="Telegram Adder Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    init_db()
except Exception as e:
    st.error(f"Database connection error: {e}")
    st.stop()

from core.auth import require_auth
require_auth()

st.sidebar.markdown(f"👤 **{st.session_state.get('tg_user_name', 'Admin')}**")
if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.title("⚡ Telegram Adder Pro — Dashboard")
st.markdown("**نظام إضافة أعضاء تليجرام احترافي — النسخة المدفوعة**")
st.divider()

stats = get_stats()
accounts = stats.get("accounts", {})
members = stats.get("members", {})

col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric("✅ حسابات نشطة", accounts.get("active", 0))
with col2:
    st.metric("⚠️ محظورة مؤقتاً", accounts.get("flood", 0) + accounts.get("restricted", 0))
with col3:
    st.metric("🌐 البروكسيات", stats.get("proxies", 0))
with col4:
    st.metric("👥 أعضاء قيد الانتظار", members.get("pending", 0))
with col5:
    st.metric("✔️ تمت إضافتهم", members.get("added", 0))
with col6:
    st.metric("📅 مضافون اليوم", stats.get("today_added", 0))

st.divider()

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📊 حالة الحسابات")
    all_statuses = {
        "active": accounts.get("active", 0),
        "pending": accounts.get("pending", 0),
        "warming": accounts.get("warming", 0),
        "flood": accounts.get("flood", 0),
        "restricted": accounts.get("restricted", 0),
        "banned": accounts.get("banned", 0),
    }
    total_accounts = sum(all_statuses.values())
    if total_accounts > 0:
        import plotly.express as px
        import pandas as pd
        df = pd.DataFrame({
            "الحالة": list(all_statuses.keys()),
            "العدد": list(all_statuses.values())
        })
        df = df[df["العدد"] > 0]
        color_map = {
            "active": "#00cc44", "pending": "#888888",
            "warming": "#ffaa00", "flood": "#ff6600",
            "restricted": "#ff3300", "banned": "#cc0000"
        }
        fig = px.pie(df, values="العدد", names="الحالة", color="الحالة",
                     color_discrete_map=color_map, hole=0.4)
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=280)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد حسابات بعد. اذهب لصفحة **الحسابات** لإضافة حسابات.")

with col_right:
    st.subheader("📊 حالة الأعضاء")
    all_member_statuses = {
        "pending": members.get("pending", 0),
        "added": members.get("added", 0),
        "privacy": members.get("privacy", 0),
        "banned": members.get("banned", 0),
        "error": members.get("error", 0),
    }
    total_members = sum(all_member_statuses.values())
    if total_members > 0:
        import plotly.express as px
        import pandas as pd
        df2 = pd.DataFrame({
            "الحالة": list(all_member_statuses.keys()),
            "العدد": list(all_member_statuses.values())
        })
        df2 = df2[df2["العدد"] > 0]
        fig2 = px.pie(df2, values="العدد", names="الحالة", hole=0.4)
        fig2.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=280)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("لا توجد أعضاء بعد. اذهب لصفحة **السكرابر** لسحب الأعضاء.")

st.subheader("🔄 آخر العمليات")
jobs = get_jobs(limit=10)
if jobs:
    import pandas as pd
    jobs_df = pd.DataFrame([dict(j) for j in jobs])
    display_cols = ["id", "job_type", "target_group", "source_group", "status",
                    "total_count", "done_count", "error_count", "created_at"]
    available = [c for c in display_cols if c in jobs_df.columns]
    st.dataframe(jobs_df[available], use_container_width=True, hide_index=True)
else:
    st.info("لا توجد عمليات بعد.")

st.divider()
st.caption("⚡ Telegram Adder Pro | String Sessions + Proxy Binding + AsyncIO Workers + Device Spoofing + Human Behavior + Captcha Bypass")

if st.button("🔄 تحديث البيانات"):
    st.rerun()
