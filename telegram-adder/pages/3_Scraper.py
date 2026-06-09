import streamlit as st
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.database import (
    init_db, get_accounts, get_pending_members, create_job,
    update_job, add_log, get_blacklist_count
)
from core.session_manager import connect_account
from core.scraper import scrape_members

st.set_page_config(page_title="السكرابر | Telegram Adder Pro", page_icon="🔍", layout="wide")
init_db()
from core.auth import require_auth
require_auth()

st.sidebar.markdown(f"👤 **{st.session_state.get('tg_user_name', 'Admin')}**")
if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.title("🔍 سحب الأعضاء (Smart Scraper)")
st.markdown("يسحب **الأعضاء النشطين** ويستبعد البوتات والخاملين والمشرفين والمالكين تلقائياً.")
st.divider()

accounts = get_accounts(status="active")
if not accounts:
    st.warning("⚠️ لا توجد حسابات نشطة. أضف حسابات أولاً.")
    st.stop()

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("⚙️ إعدادات السحب")
    source_group = st.text_input("مجموعة/قناة المصدر",
                                  placeholder="@groupname أو https://t.me/groupname")
    selected_phone = st.selectbox("الحساب المستخدم",
                                   options=[f"{acc['phone']} ({acc['id']})" for acc in accounts])
    account_id = int(selected_phone.split("(")[-1].rstrip(")"))

    st.subheader("🧠 فلاتر ذكية")
    filter_admins = st.toggle("استبعاد المشرفين والمالكين والبوتات", value=True,
                               help="يقرأ صلاحيات الأعضاء ويستبعد Admins/Creators — يقلل الحظر بشكل كبير")
    if filter_admins:
        st.success("✅ Admin Evasion: مُفعَّل")
    else:
        st.warning("⚠️ تحذير: المشرفون سيُسحبون وقد يبلّغون عنك")

    filter_active = st.toggle("فلترة المستخدمين النشطين فقط", value=True)
    filter_hours = st.slider("آخر ظهور خلال (ساعات)", min_value=1, max_value=720,
                              value=48, disabled=not filter_active)
    if filter_active:
        st.info(f"✅ سيُسحب فقط من كانوا نشطين خلال آخر **{filter_hours} ساعة**")

with col2:
    st.subheader("📊 الإحصائيات")
    total_pending = len(get_pending_members(limit=10000))
    blacklist_count = get_blacklist_count()
    st.metric("في الانتظار", total_pending)
    st.metric("في القائمة السوداء", blacklist_count)
    st.metric("المصدر", source_group or "—")

st.divider()

if st.button("🚀 بدء السحب", type="primary", disabled=not source_group):
    progress_bar = st.progress(0)
    status_text = st.empty()
    job_id = create_job("scrape", None, source_group.strip())

    def progress_callback(saved, total, skipped):
        status_text.text(f"✅ محفوظ: {saved} | إجمالي: {total} | محذوف/خامل/مشرف: {skipped}")

    try:
        status_text.text("⏳ جاري الاتصال...")
        client = asyncio.run(connect_account(account_id))
        if filter_admins:
            status_text.text("🛡️ جاري قراءة قائمة المشرفين لاستبعادهم...")
        status_text.text(f"🔍 جاري السحب من {source_group}...")

        saved, skipped, total = asyncio.run(
            scrape_members(client, account_id, source_group.strip(),
                          filter_active=filter_active, filter_hours=filter_hours,
                          filter_admins=filter_admins, job_id=job_id,
                          progress_callback=progress_callback)
        )

        asyncio.run(client.disconnect())
        update_job(job_id, status="completed", total=total, done=saved)
        progress_bar.progress(1.0)
        st.success(f"""
        ✅ **اكتمل السحب!**
        - 📥 تم حفظ: **{saved}** عضو
        - ⏭️ تم تخطي: **{skipped}** (خامل/بوت/مشرف)
        - 📊 الإجمالي: **{total}**
        """)
    except ConnectionError as e:
        st.error(f"خطأ في الاتصال: {e}")
        update_job(job_id, status="failed")
    except Exception as e:
        st.error(f"خطأ: {e}")
        update_job(job_id, status="failed")

st.divider()
st.subheader("📋 عينة من الأعضاء المسحوبين")
members_list = get_pending_members(limit=50)
if members_list:
    import pandas as pd
    df = pd.DataFrame([dict(m) for m in members_list])
    display_cols = ["user_id", "username", "first_name", "last_name", "last_seen", "source_group", "status"]
    available = [c for c in display_cols if c in df.columns]
    st.dataframe(df[available], use_container_width=True, hide_index=True)
else:
    st.info("لا توجد بيانات بعد.")
