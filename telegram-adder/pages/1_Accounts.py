import streamlit as st
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.database import (
    init_db, get_accounts, add_account, update_account_session,
    update_account_status, update_account_2fa_password, delete_account,
    get_account_proxy
)
from core.device_spoofer import generate_device_params
from core.session_manager import login_account_interactive, send_code, verify_code

st.set_page_config(page_title="الحسابات | Telegram Adder Pro", page_icon="👤", layout="wide")
init_db()
from core.auth import require_auth
require_auth()

st.sidebar.markdown(f"👤 **{st.session_state.get('tg_user_name', 'Admin')}**")
if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.title("👤 إدارة الحسابات")
st.markdown("أضف حسابات تليجرام وسجّل الدخول باستخدام **String Sessions** مع Device Spoofing تلقائي.")
st.divider()

accounts = get_accounts()

STATUS_COLORS = {
    "active": "🟢", "pending": "⚪", "warming": "🟡",
    "flood": "🟠", "restricted": "🔴", "banned": "💀",
    "appeal_pending": "⏳", "unknown": "❓"
}
SPAMBOT_COLORS = {
    "clean": "🟢 نظيف", "restricted": "🔴 مقيد",
    "appeal_pending": "⏳ طلب رفع حظر مُرسَل",
    "unknown": "❓ غير معروف", "error": "⚠️ خطأ"
}

if accounts:
    st.subheader(f"الحسابات ({len(accounts)})")
    for acc in accounts:
        proxy = get_account_proxy(acc["id"])
        proxy_info = f"{proxy['host']}:{proxy['port']}" if proxy else "❌ بدون بروكسي"
        status_icon = STATUS_COLORS.get(acc["status"], "⚪")
        spambot_info = SPAMBOT_COLORS.get(acc.get("spambot_status", "unknown"), "❓ غير معروف")
        flood_info = ""
        if acc.get("flood_wait_until"):
            flood_info = f" | FloodWait حتى: {acc['flood_wait_until']}"

        with st.expander(
            f"{status_icon} {acc['phone']} — {acc['status']}{flood_info} | "
            f"SpamBot: {spambot_info} | بروكسي: {proxy_info}"
        ):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**API ID:** {acc['api_id']}")
                st.write(f"**الجهاز:** {acc.get('device_model', 'غير محدد')}")
                st.write(f"**النظام:** {acc.get('system_version', 'غير محدد')}")
            with col2:
                st.write(f"**إصدار التطبيق:** {acc.get('app_version', 'غير محدد')}")
                st.write(f"**Session:** {'✅ موجود' if acc.get('session_string') else '❌ غير موجود'}")
                st.write(f"**إضافات اليوم:** {acc.get('daily_add_count', 0)}")
                has_2fa = bool(acc.get("two_factor_password"))
                st.write(f"**2FA محفوظ:** {'🔐 نعم' if has_2fa else '🔓 لا'}")
            with col3:
                if st.button(f"🗑️ حذف", key=f"del_{acc['id']}"):
                    delete_account(acc["id"])
                    st.success("تم الحذف")
                    st.rerun()
                if acc["status"] in ("flood", "restricted") and st.button("✅ إعادة تفعيل", key=f"act_{acc['id']}"):
                    update_account_status(acc["id"], "active")
                    st.success("تم التفعيل")
                    st.rerun()

            st.markdown("---")
            st.markdown("**🔐 تحديث كلمة مرور 2FA:**")
            with st.form(f"2fa_form_{acc['id']}"):
                new_pw = st.text_input(
                    "كلمة مرور 2FA (Cloud Password)",
                    type="password",
                    placeholder="اتركه فارغاً إذا لا يوجد 2FA",
                    key=f"pw_{acc['id']}"
                )
                save_pw = st.form_submit_button("💾 حفظ كلمة المرور")
            if save_pw:
                update_account_2fa_password(acc["id"], new_pw if new_pw else None)
                st.success("✅ تم حفظ كلمة مرور 2FA في قاعدة البيانات")
else:
    st.info("لا توجد حسابات. أضف حساباً من القسم أدناه.")

st.divider()
st.subheader("➕ إضافة حساب جديد")

tab1, tab2 = st.tabs(["تسجيل دخول تفاعلي", "إدخال Session String يدوياً"])

with tab1:
    st.markdown("سيقوم النظام تلقائياً بتوليد معاملات جهاز عشوائية لكل حساب.")

    with st.form("login_form"):
        phone = st.text_input("رقم الهاتف (مع كود الدولة)", placeholder="+966501234567")
        api_id = st.number_input("API ID", min_value=1, value=None, placeholder="من my.telegram.org")
        api_hash = st.text_input("API Hash", placeholder="من my.telegram.org", type="password")
        submitted = st.form_submit_button("📲 إرسال كود التحقق")

    if submitted and phone and api_id and api_hash:
        try:
            device_params = generate_device_params()
            st.info(f"🎲 جهاز مولّد: {device_params['device_model']} | {device_params['system_version']} | v{device_params['app_version']}")
            client, dp = asyncio.run(login_account_interactive(phone, int(api_id), api_hash, device_params))
            code_result = asyncio.run(send_code(client, phone))
            st.session_state["pending_client"] = client
            st.session_state["pending_phone"] = phone
            st.session_state["pending_api_id"] = int(api_id)
            st.session_state["pending_api_hash"] = api_hash
            st.session_state["pending_device"] = dp
            st.session_state["code_hash"] = code_result.phone_code_hash
            st.success("✅ تم إرسال الكود! أدخله أدناه.")
        except Exception as e:
            st.error(f"خطأ: {e}")

    if "pending_client" in st.session_state:
        with st.form("verify_form"):
            code = st.text_input("كود التحقق من التليجرام", placeholder="12345")
            password = st.text_input("كلمة مرور 2FA (إذا مفعّلة)", type="password",
                                     help="إذا كان الحساب محمياً بكلمة مرور السحابة، أدخلها وسيتم حفظها")
            verify_btn = st.form_submit_button("✅ تأكيد الكود")

        if verify_btn and code:
            try:
                client = st.session_state["pending_client"]
                phone = st.session_state["pending_phone"]
                dp = st.session_state["pending_device"]
                user, session_string = asyncio.run(verify_code(client, phone, code, password or None))
                acc_id = add_account(
                    phone=phone, api_id=st.session_state["pending_api_id"],
                    api_hash=st.session_state["pending_api_hash"],
                    device_model=dp["device_model"], system_version=dp["system_version"],
                    app_version=dp["app_version"],
                )
                update_account_session(acc_id, session_string, "active")
                if password:
                    update_account_2fa_password(acc_id, password)
                    st.info("🔐 تم حفظ كلمة مرور 2FA تلقائياً")
                for key in ["pending_client", "pending_phone", "pending_api_id", "pending_api_hash", "pending_device", "code_hash"]:
                    st.session_state.pop(key, None)
                st.success(f"✅ تم تسجيل الدخول بنجاح! الحساب: {phone}")
                st.rerun()
            except ValueError as e:
                if "2FA_REQUIRED" in str(e):
                    st.warning("⚠️ يجب إدخال كلمة مرور 2FA")
                else:
                    st.error(f"خطأ: {e}")
            except Exception as e:
                st.error(f"خطأ في التحقق: {e}")

with tab2:
    st.markdown("إذا كان عندك Session String جاهز (مثلاً من Pyrogram أو Telethon مسبقاً).")
    with st.form("manual_session_form"):
        m_phone = st.text_input("رقم الهاتف", placeholder="+966501234567")
        m_api_id = st.number_input("API ID", min_value=1, value=None, key="m_api_id")
        m_api_hash = st.text_input("API Hash", type="password", key="m_api_hash")
        m_session = st.text_area("Session String", placeholder="1BQANOTEuA...", height=100)
        m_2fa = st.text_input("كلمة مرور 2FA (اختياري)", type="password", key="m_2fa")
        m_submitted = st.form_submit_button("💾 حفظ الحساب")

    if m_submitted and m_phone and m_api_id and m_api_hash and m_session:
        try:
            device_params = generate_device_params()
            acc_id = add_account(phone=m_phone, api_id=int(m_api_id), api_hash=m_api_hash,
                                 device_model=device_params["device_model"],
                                 system_version=device_params["system_version"],
                                 app_version=device_params["app_version"])
            update_account_session(acc_id, m_session.strip(), "active")
            if m_2fa:
                update_account_2fa_password(acc_id, m_2fa)
            st.success(f"✅ تم حفظ الحساب {m_phone}")
            st.rerun()
        except Exception as e:
            st.error(f"خطأ: {e}")
