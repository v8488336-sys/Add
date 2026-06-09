import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from core.database import (
    get_account, get_account_proxy, update_account_session,
    update_account_status, get_setting
)
from core.device_spoofer import generate_device_params

logger = logging.getLogger(__name__)


def build_proxy_config(proxy_row):
    if not proxy_row:
        return None
    import socks
    proxy_type_map = {
        "socks5": socks.SOCKS5,
        "socks4": socks.SOCKS4,
        "http": socks.HTTP,
    }
    ptype = proxy_type_map.get(proxy_row["proxy_type"].lower(), socks.SOCKS5)
    if proxy_row.get("username") and proxy_row.get("password"):
        return (ptype, proxy_row["host"], int(proxy_row["port"]), True,
                proxy_row["username"], proxy_row["password"])
    return (ptype, proxy_row["host"], int(proxy_row["port"]))


def create_client(account_row, proxy_config=None):
    session_str = account_row.get("session_string") or ""
    session = StringSession(session_str)
    params = {
        "session": session,
        "api_id": account_row["api_id"],
        "api_hash": account_row["api_hash"],
        "device_model": account_row.get("device_model") or "Samsung Galaxy S23",
        "system_version": account_row.get("system_version") or "Android 13",
        "app_version": account_row.get("app_version") or "10.5.0",
        "lang_code": account_row.get("lang_code") or "en",
        "system_lang_code": account_row.get("lang_code") or "en",
    }
    if proxy_config:
        params["proxy"] = proxy_config
    return TelegramClient(**params)


async def connect_account(account_id):
    """
    يتصل بحساب تيليجرام. يجرب كلمة مرور 2FA بالترتيب:
    1. كلمة مرور 2FA الخاصة بالحساب (من DB)
    2. كلمة مرور 2FA العالمية (Global Default من الإعدادات)
    """
    account = get_account(account_id)
    if not account:
        raise ValueError(f"Account {account_id} not found")

    proxy_row = get_account_proxy(account_id)
    proxy_config = build_proxy_config(proxy_row)
    client = create_client(account, proxy_config)
    await client.connect()

    if not await client.is_user_authorized():
        # محاولة 1: كلمة مرور 2FA الخاصة بالحساب
        stored_password = account.get("two_factor_password")

        # محاولة 2: إذا لم تكن موجودة، جرّب كلمة المرور العالمية
        if not stored_password:
            stored_password = get_setting("global_2fa_password")

        if stored_password:
            try:
                logger.info(f"Trying 2FA for account {account_id}")
                await client.sign_in(password=stored_password)
                logger.info(f"2FA succeeded for account {account_id}")
            except Exception as e:
                raise ConnectionError(
                    f"Account {account['phone']} — 2FA فشل: {e}"
                )
        else:
            raise ConnectionError(
                f"Account {account['phone']} — غير مصادق. سجّل الدخول أولاً من صفحة الحسابات."
            )

    session_string = client.session.save()
    update_account_session(account_id, session_string)
    return client


async def login_account_interactive(phone, api_id, api_hash, device_params=None):
    if not device_params:
        device_params = generate_device_params()
    session = StringSession()
    client = TelegramClient(
        session, api_id, api_hash,
        device_model=device_params["device_model"],
        system_version=device_params["system_version"],
        app_version=device_params["app_version"],
        lang_code=device_params["lang_code"],
        system_lang_code=device_params["system_lang_code"],
    )
    await client.connect()
    return client, device_params


async def send_code(client, phone):
    result = await client.send_code_request(phone)
    return result


async def verify_code(client, phone, code, password=None):
    """
    يتحقق من كود تليجرام.
    إذا كان الحساب يحتاج 2FA ولم يُعطَ كلمة مرور، يجرب كلمة المرور العالمية.
    """
    try:
        user = await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        # الحساب يحتاج 2FA
        effective_pw = password
        if not effective_pw:
            # جرّب كلمة المرور العالمية
            effective_pw = get_setting("global_2fa_password")
        if not effective_pw:
            raise ValueError("2FA_REQUIRED")
        user = await client.sign_in(password=effective_pw)
    except Exception as e:
        err_name = type(e).__name__
        if "SessionPasswordNeeded" in err_name or "two-step" in str(e).lower():
            effective_pw = password
            if not effective_pw:
                effective_pw = get_setting("global_2fa_password")
            if not effective_pw:
                raise ValueError("2FA_REQUIRED")
            user = await client.sign_in(password=effective_pw)
        else:
            raise
    session_string = client.session.save()
    return user, session_string
