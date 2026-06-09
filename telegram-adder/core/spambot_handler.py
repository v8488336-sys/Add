"""
SpamBot Handler — يتحقق من حالة الحساب عبر @SpamBot ويرسل طلب رفع الحظر تلقائياً.
"""
import asyncio
import logging
import random
from telethon import events
from core.database import update_account_spambot_status, add_log

logger = logging.getLogger(__name__)

SPAMBOT_USERNAME = "SpamBot"

APPEAL_TEMPLATES = [
    (
        "Hello Telegram Team,\n\n"
        "My account has been restricted, but I strongly believe this was done in error "
        "by an automated system. I have not sent any spam or unsolicited bulk messages, "
        "and I have not violated Telegram's Terms of Service in any way.\n\n"
        "I kindly request a manual review of my account and ask that the restriction "
        "be lifted as soon as possible. This account is essential for my personal and "
        "professional communication.\n\n"
        "Thank you for your understanding."
    ),
    (
        "Dear Telegram Developers,\n\n"
        "I am writing to appeal a restriction that has been placed on my account. "
        "I have not been engaging in any spamming activity, sending bulk messages, "
        "or violating any community guidelines. My account appears to have been flagged "
        "incorrectly by an automated system.\n\n"
        "I respectfully request a review of my account activity and the removal of this "
        "restriction. I am a regular user who relies on Telegram for legitimate daily communication.\n\n"
        "Thank you for your time."
    ),
    (
        "Hello,\n\n"
        "I noticed my Telegram account has been restricted. I believe this is a mistake, "
        "as I have not engaged in any spamming or policy-violating behavior. "
        "I have not sent mass messages, added strangers to groups without consent, "
        "or performed any action that would constitute abuse of the platform.\n\n"
        "I humbly request that you review my account and lift this restriction. "
        "I value Telegram as a platform and have always used it responsibly.\n\n"
        "Thank you."
    ),
]

STATUS_FREE_KEYWORDS = [
    "no limits", "free", "available", "not restricted", "no restrictions",
    "everything is fine", "not spam", "clear"
]

STATUS_RESTRICTED_KEYWORDS = [
    "spam", "restricted", "limited", "block", "banned", "reported",
    "limit", "cannot", "can't", "won't work"
]


async def _wait_for_spambot_reply(client, timeout=20):
    """انتظر رد @SpamBot بعد إرسال رسالة."""
    try:
        async with asyncio.timeout(timeout):
            async for message in client.iter_messages(SPAMBOT_USERNAME, limit=1, wait_time=timeout):
                return message
    except (asyncio.TimeoutError, Exception):
        pass
    await asyncio.sleep(timeout)
    msgs = await client.get_messages(SPAMBOT_USERNAME, limit=1)
    return msgs[0] if msgs else None


def _detect_status(text: str) -> str:
    """اكتشف حالة الحساب من نص رد SpamBot."""
    if not text:
        return "unknown"
    lower = text.lower()
    for kw in STATUS_FREE_KEYWORDS:
        if kw in lower:
            return "clean"
    for kw in STATUS_RESTRICTED_KEYWORDS:
        if kw in lower:
            return "restricted"
    return "unknown"


async def _click_button_by_keywords(message, keywords: list) -> bool:
    """اضغط أول زر يحتوي على أي من الكلمات المطلوبة."""
    if not message or not message.buttons:
        return False
    for row in message.buttons:
        for btn in row:
            btn_text = (btn.text or "").lower()
            if any(kw.lower() in btn_text for kw in keywords):
                try:
                    await btn.click()
                    return True
                except Exception as e:
                    logger.warning(f"Button click error: {e}")
    return False


async def check_and_appeal(client, account_id, job_id=None) -> dict:
    """
    التحقق من حالة الحساب عبر @SpamBot وإرسال Appeal تلقائي إذا كان مقيداً.
    يعيد dict: {"status": "clean"/"restricted"/"appeal_sent"/"unknown", "message": str}
    """
    result = {"status": "unknown", "message": ""}

    try:
        logger.info(f"[SpamBot] Checking account {account_id}")

        await client.send_message(SPAMBOT_USERNAME, "/start")
        await asyncio.sleep(random.uniform(3, 6))

        msgs = await client.get_messages(SPAMBOT_USERNAME, limit=3)
        if not msgs:
            result["message"] = "No response from SpamBot"
            update_account_spambot_status(account_id, "unknown")
            return result

        combined_text = " ".join(m.text or "" for m in msgs if m.text)
        status = _detect_status(combined_text)

        logger.info(f"[SpamBot] Account {account_id} status detected: {status}")
        logger.info(f"[SpamBot] Response text: {combined_text[:300]}")

        if status == "clean":
            result["status"] = "clean"
            result["message"] = combined_text[:300]
            update_account_spambot_status(account_id, "clean")
            add_log(job_id, account_id, None, "spambot_check", "clean", combined_text[:200])
            return result

        if status == "restricted":
            result["status"] = "restricted"
            result["message"] = combined_text[:300]

            latest_msg = msgs[0]

            clicked = await _click_button_by_keywords(latest_msg, [
                "mistake", "wrong", "error", "no", "innocent",
                "this is a mistake", "nothing like that"
            ])

            if not clicked:
                await asyncio.sleep(2)
                msgs2 = await client.get_messages(SPAMBOT_USERNAME, limit=1)
                if msgs2:
                    clicked = await _click_button_by_keywords(msgs2[0], [
                        "mistake", "wrong", "no", "innocent", "this is"
                    ])

            await asyncio.sleep(random.uniform(2, 4))

            msgs3 = await client.get_messages(SPAMBOT_USERNAME, limit=1)
            if msgs3:
                await _click_button_by_keywords(msgs3[0], [
                    "no", "nothing", "didn't", "never", "not me",
                    "yes", "appeal", "request"
                ])

            await asyncio.sleep(random.uniform(2, 5))

            appeal_text = random.choice(APPEAL_TEMPLATES)
            await client.send_message(SPAMBOT_USERNAME, appeal_text)
            await asyncio.sleep(random.uniform(2, 4))

            final_msgs = await client.get_messages(SPAMBOT_USERNAME, limit=1)
            final_text = (final_msgs[0].text or "") if final_msgs else ""

            result["status"] = "appeal_sent"
            result["message"] = f"Appeal sent. SpamBot reply: {final_text[:200]}"
            update_account_spambot_status(account_id, "appeal_pending", appeal_sent=True)
            add_log(job_id, account_id, None, "spambot_appeal", "sent",
                    f"Appeal submitted. Reply: {final_text[:150]}")
            logger.info(f"[SpamBot] Appeal sent for account {account_id}")
            return result

        result["status"] = "unknown"
        result["message"] = combined_text[:300]
        update_account_spambot_status(account_id, "unknown")
        add_log(job_id, account_id, None, "spambot_check", "unknown", combined_text[:200])

    except Exception as e:
        logger.error(f"[SpamBot] Error for account {account_id}: {e}")
        result["status"] = "error"
        result["message"] = str(e)
        add_log(job_id, account_id, None, "spambot_check", "error", str(e)[:200])

    return result


async def bulk_check_accounts(clients_accounts: list, job_id=None) -> list:
    """
    فحص مجموعة حسابات بالتسلسل (للحد من الضغط).
    clients_accounts: [(client, account_id), ...]
    """
    results = []
    for client, account_id in clients_accounts:
        res = await check_and_appeal(client, account_id, job_id)
        results.append({"account_id": account_id, **res})
        await asyncio.sleep(random.uniform(10, 20))
    return results
