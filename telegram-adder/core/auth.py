"""
Authentication module — حماية كاملة للتطبيق بكلمة مرور + إشعار بوت تيليجرام.
"""
import hashlib
import streamlit as st
import requests as _requests
from core.database import get_setting, set_setting, log_access_attempt

_SALT = "TgAdderPro_2025_"


def _hash(pw: str) -> str:
    return hashlib.sha256((_SALT + pw).encode()).hexdigest()


def set_master_password(password: str):
    set_setting("master_password_hash", _hash(password))


def is_password_set() -> bool:
    return bool(get_setting("master_password_hash"))


def verify_password(password: str) -> bool:
    stored = get_setting("master_password_hash")
    if not stored:
        return True
    return _hash(password) == stored


def send_bot_notification(name: str, granted: bool):
    """إرسال إشعار للأدمن عند تسجيل الدخول."""
    bot_token = get_setting("bot_token")
    admin_id = get_setting("admin_chat_id")
    if not bot_token or not admin_id:
        return
    icon = "✅" if granted else "❌"
    text = (
        f"{icon} *Telegram Adder Pro*\n\n"
        f"الاسم: `{name}`\n"
        f"الحالة: {'دخل بنجاح' if granted else 'محاولة دخول فاشلة'}"
    )
    try:
        _requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": admin_id, "text": text, "parse_mode": "Markdown"},
            timeout=5,
        )
    except Exception:
        pass


def require_auth():
    """
    استدعِ هذه الدالة في كل صفحة مباشرةً بعد set_page_config().
    إذا لم يكن المستخدم مصادقاً → تعرض شاشة الدخول وتوقف الصفحة.
    """
    if st.session_state.get("tg_authenticated"):
        return

    if not is_password_set():
        _show_first_setup()
        st.stop()
    else:
        _show_login()
        st.stop()


def _show_first_setup():
    st.markdown(
        "<h1 style='text-align:center'>⚡ Telegram Adder Pro</h1>",
        unsafe_allow_html=True,
    )
    st.info("🔑 المرة الأولى — حدد كلمة مرور رئيسية للتطبيق")

    with st.form("setup_pw_form", clear_on_submit=True):
        new_pw = st.text_input("كلمة المرور الرئيسية", type="password", placeholder="اختر كلمة مرور قوية")
        confirm_pw = st.text_input("تأكيد كلمة المرور", type="password")
        name_input = st.text_input("اسمك (للسجلات)", placeholder="Admin")
        setup_btn = st.form_submit_button("🚀 تفعيل الحماية")

    if setup_btn:
        if not new_pw or len(new_pw) < 4:
            st.error("كلمة المرور يجب أن تكون 4 أحرف على الأقل")
            return
        if new_pw != confirm_pw:
            st.error("كلمتا المرور غير متطابقتَين")
            return
        set_master_password(new_pw)
        st.session_state["tg_authenticated"] = True
        st.session_state["tg_user_name"] = name_input or "Admin"
        log_access_attempt(name_input or "Admin", granted=True)
        st.success("✅ تم تفعيل الحماية! جاري التحميل...")
        st.rerun()


def _show_login():
    st.markdown(
        "<h1 style='text-align:center'>⚡ Telegram Adder Pro</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center;color:#888'>أدخل بياناتك للدخول</p>",
        unsafe_allow_html=True,
    )

    col_pad, col_form, col_pad2 = st.columns([1, 2, 1])
    with col_form:
        with st.form("login_form", clear_on_submit=True):
            name_input = st.text_input("اسمك", placeholder="أدخل اسمك")
            pw_input = st.text_input("كلمة المرور", type="password", placeholder="كلمة المرور")
            login_btn = st.form_submit_button("🔐 دخول", use_container_width=True)

        if login_btn:
            if verify_password(pw_input):
                st.session_state["tg_authenticated"] = True
                st.session_state["tg_user_name"] = name_input or "زائر"
                log_access_attempt(name_input or "زائر", granted=True)
                send_bot_notification(name_input or "زائر", granted=True)
                st.success("✅ تم الدخول بنجاح!")
                st.rerun()
            else:
                log_access_attempt(name_input or "مجهول", granted=False)
                send_bot_notification(name_input or "مجهول", granted=False)
                st.error("❌ كلمة المرور غير صحيحة")

    st.markdown("---")
    st.caption("🔒 هذا النظام محمي — فقط المصرح لهم يمكنهم الوصول")
