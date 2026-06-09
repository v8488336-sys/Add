import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.database import init_db, get_proxies, get_accounts, add_proxy, assign_proxy_to_account, delete_proxy

st.set_page_config(page_title="البروكسيات | Telegram Adder Pro", page_icon="🌐", layout="wide")
init_db()
from core.auth import require_auth
require_auth()

st.sidebar.markdown(f"👤 **{st.session_state.get('tg_user_name', 'Admin')}**")
if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.title("🌐 إدارة البروكسيات")
st.markdown("اربط كل حساب ببروكسي خاص به — يجعل التليجرام يرى كل حساب من مكان مختلف تماماً.")
st.divider()

proxies = get_proxies()
accounts = get_accounts()
accounts_map = {acc["id"]: acc["phone"] for acc in accounts}

if proxies:
    st.subheader(f"البروكسيات ({len(proxies)})")
    for proxy in proxies:
        assigned_phone = accounts_map.get(proxy.get("account_id"), "غير مربوط")
        has_auth = "✅" if proxy.get("username") else "❌"
        active_icon = "🟢" if proxy.get("is_active", True) else "🔴"

        with st.expander(f"{active_icon} {proxy['proxy_type'].upper()} | {proxy['host']}:{proxy['port']} — {assigned_phone}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**النوع:** {proxy['proxy_type'].upper()}")
                st.write(f"**الهوست:** {proxy['host']}")
                st.write(f"**البورت:** {proxy['port']}")
            with col2:
                st.write(f"**المصادقة:** {has_auth}")
                if proxy.get("username"):
                    st.write(f"**المستخدم:** {proxy['username']}")
                st.write(f"**مربوط بـ:** {assigned_phone}")
                st.write(f"**الحالة:** {'نشط' if proxy.get('is_active', True) else '❌ غير نشط'}")
            with col3:
                unassigned_accounts = [acc for acc in accounts if acc.get("proxy_id") != proxy["id"]]
                if unassigned_accounts:
                    selected = st.selectbox("ربط بحساب",
                        options=["اختر حساب"] + [acc["phone"] for acc in unassigned_accounts],
                        key=f"proxy_assign_{proxy['id']}")
                    if selected != "اختر حساب":
                        selected_acc = next((a for a in unassigned_accounts if a["phone"] == selected), None)
                        if selected_acc and st.button("🔗 ربط", key=f"bind_{proxy['id']}"):
                            assign_proxy_to_account(proxy["id"], selected_acc["id"])
                            st.success(f"تم ربط {proxy['host']} بـ {selected}")
                            st.rerun()
                if st.button("🗑️ حذف", key=f"del_proxy_{proxy['id']}"):
                    delete_proxy(proxy["id"])
                    st.success("تم الحذف")
                    st.rerun()
else:
    st.info("لا توجد بروكسيات. أضف بروكسي من القسم أدناه.")

st.divider()
st.subheader("➕ إضافة بروكسي")

tab1, tab2 = st.tabs(["إضافة فردية", "إضافة جماعية (نص)"])

with tab1:
    with st.form("add_proxy_form"):
        proxy_type = st.selectbox("نوع البروكسي", ["socks5", "socks4", "http"])
        proxy_host = st.text_input("الهوست / IP", placeholder="192.168.1.1 أو proxy.example.com")
        proxy_port = st.number_input("البورت", min_value=1, max_value=65535, value=1080)
        proxy_user = st.text_input("اسم المستخدم (اختياري)")
        proxy_pass = st.text_input("كلمة المرور (اختياري)", type="password")
        add_proxy_btn = st.form_submit_button("✅ إضافة البروكسي")

    if add_proxy_btn and proxy_host and proxy_port:
        try:
            pid = add_proxy(proxy_type, proxy_host, proxy_port, proxy_user or None, proxy_pass or None)
            st.success(f"✅ تم إضافة البروكسي ID: {pid}")
            st.rerun()
        except Exception as e:
            st.error(f"خطأ: {e}")

with tab2:
    st.markdown("""
    أدخل البروكسيات بصيغة واحدة في كل سطر:
    ```
    socks5:host:port:user:pass
    socks5:host:port
    http:host:port:user:pass
    ```
    """)
    bulk_text = st.text_area("البروكسيات", height=200, placeholder="socks5:1.2.3.4:1080:user:pass")
    if st.button("📥 استيراد"):
        added = 0
        errors = []
        for line in bulk_text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            try:
                if len(parts) >= 3:
                    ptype = parts[0].lower()
                    host = parts[1]
                    port = int(parts[2])
                    user = parts[3] if len(parts) > 3 else None
                    pwd = parts[4] if len(parts) > 4 else None
                    add_proxy(ptype, host, port, user, pwd)
                    added += 1
            except Exception as e:
                errors.append(f"{line}: {e}")
        st.success(f"✅ تم إضافة {added} بروكسي")
        if errors:
            st.warning(f"أخطاء: {len(errors)} سطر — {errors[:3]}")
        st.rerun()

st.divider()
st.subheader("🔗 ربط تلقائي بالحسابات")
st.info("سيقوم النظام بتوزيع البروكسيات المتاحة على الحسابات بدون بروكسي تلقائياً.")

if st.button("⚡ ربط تلقائي"):
    unassigned_accounts = [a for a in accounts if not a.get("proxy_id")]
    unassigned_proxies = [p for p in proxies if not p.get("account_id")]
    paired = 0
    for acc, prx in zip(unassigned_accounts, unassigned_proxies):
        assign_proxy_to_account(prx["id"], acc["id"])
        paired += 1
    if paired:
        st.success(f"✅ تم ربط {paired} حساب ببروكسي")
        st.rerun()
    else:
        st.warning("لا توجد حسابات أو بروكسيات بدون ربط.")
