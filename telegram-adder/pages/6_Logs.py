import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.database import init_db, get_logs, get_jobs, get_stats, get_accounts, get_pending_members, db_cursor

st.set_page_config(page_title="السجلات | Telegram Adder Pro", page_icon="📋", layout="wide")
init_db()
from core.auth import require_auth
require_auth()

st.sidebar.markdown(f"👤 **{st.session_state.get('tg_user_name', 'Admin')}**")
if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.title("📋 السجلات والإحصائيات")
st.divider()

tab1, tab2, tab3 = st.tabs(["📊 إحصائيات تفصيلية", "📋 سجل العمليات", "👥 قاعدة الأعضاء"])

with tab1:
    stats = get_stats()
    accounts = get_accounts()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("إجمالي الحسابات", sum(stats["accounts"].values()))
    with col2:
        st.metric("حسابات نشطة", stats["accounts"].get("active", 0))
    with col3:
        st.metric("إجمالي الأعضاء", sum(stats["members"].values()))
    with col4:
        st.metric("تمت إضافتهم", stats["members"].get("added", 0))

    st.divider()

    if accounts:
        st.subheader("📈 أداء كل حساب")
        import pandas as pd
        import plotly.express as px

        acc_df = pd.DataFrame([dict(a) for a in accounts])
        if "daily_add_count" in acc_df.columns and "phone" in acc_df.columns:
            fig = px.bar(acc_df, x="phone", y="daily_add_count",
                        title="إضافات اليوم لكل حساب",
                        color="status",
                        color_discrete_map={
                            "active": "#00cc44", "flood": "#ff6600",
                            "restricted": "#ff3300", "banned": "#cc0000",
                            "warming": "#ffaa00", "pending": "#888888"
                        })
            fig.update_xaxes(tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

    jobs = get_jobs(limit=20)
    if jobs:
        st.subheader("📊 تقدم المهام")
        import pandas as pd
        import plotly.express as px
        job_df = pd.DataFrame([dict(j) for j in jobs])
        if "done_count" in job_df.columns and "error_count" in job_df.columns:
            fig2 = px.bar(job_df, x="id", y=["done_count", "error_count"],
                         title="نتائج كل مهمة",
                         barmode="group",
                         labels={"value": "العدد", "variable": "النوع", "id": "رقم المهمة"})
            st.plotly_chart(fig2, use_container_width=True)

with tab2:
    col_left, col_right = st.columns([2, 1])
    with col_left:
        jobs = get_jobs(limit=20)
        job_options = ["الكل"] + [f"مهمة {j['id']} — {j['job_type']} ({j['status']})" for j in jobs]
        selected_job = st.selectbox("فلتر بالمهمة", options=job_options)
    with col_right:
        result_filter = st.selectbox("فلتر بالنتيجة", ["الكل", "success", "error", "privacy", "flood", "banned"])
        log_limit = st.number_input("عدد السجلات", min_value=10, max_value=500, value=100)

    job_id_filter = None
    if selected_job != "الكل":
        job_id_filter = int(selected_job.split("مهمة ")[1].split(" ")[0])

    logs = get_logs(job_id=job_id_filter, limit=log_limit)

    if logs:
        import pandas as pd
        df = pd.DataFrame([dict(l) for l in logs])
        if result_filter != "الكل" and "result" in df.columns:
            df = df[df["result"] == result_filter]
        display_cols = ["created_at", "phone", "user_id", "action", "result", "message"]
        available = [c for c in display_cols if c in df.columns]

        def color_result(val):
            colors = {
                "success": "background-color: #003300",
                "error": "background-color: #330000",
                "privacy": "background-color: #333300",
                "flood": "background-color: #331100",
                "banned": "background-color: #220000",
            }
            return colors.get(val, "")

        if "result" in df.columns:
            styled = df[available].style.applymap(color_result, subset=["result"])
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.dataframe(df[available], use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد سجلات.")

with tab3:
    st.subheader("👥 قاعدة بيانات الأعضاء")
    col1, col2, col3 = st.columns(3)
    with col1:
        member_status_filter = st.selectbox("الحالة", ["الكل", "pending", "added", "privacy", "banned", "error"])
    with col2:
        all_members = get_pending_members(limit=5000)
        source_groups = list({m["source_group"] for m in all_members if m.get("source_group")})
        source_filter = st.selectbox("المصدر", ["الكل"] + source_groups)
    with col3:
        member_limit = st.number_input("عدد النتائج", min_value=10, max_value=1000, value=200)

    with db_cursor() as cur:
        query = "SELECT * FROM tg_members WHERE 1=1"
        params = []
        if member_status_filter != "الكل":
            query += " AND status = %s"
            params.append(member_status_filter)
        if source_filter != "الكل":
            query += " AND source_group = %s"
            params.append(source_filter)
        query += f" ORDER BY created_at DESC LIMIT {member_limit}"
        cur.execute(query, params)
        members = cur.fetchall()

    if members:
        import pandas as pd
        df = pd.DataFrame([dict(m) for m in members])
        display_cols = ["user_id", "username", "first_name", "last_name", "last_seen",
                       "source_group", "status", "added_at", "error_msg"]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available], use_container_width=True, hide_index=True)
        csv = df[available].to_csv(index=False).encode("utf-8")
        st.download_button("📥 تحميل CSV", csv, "members.csv", "text/csv")
    else:
        st.info("لا توجد بيانات.")

    if st.button("🔄 تحديث"):
        st.rerun()
