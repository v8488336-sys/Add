import asyncio
import random
import logging
from telethon import events

logger = logging.getLogger(__name__)

PROTECTION_BOT_KEYWORDS = [
    "captcha", "verify", "human", "robot", "bot", "press", "click",
    "confirm", "join", "welcome", "لست روبوت", "التحقق", "اضغط",
]


async def handle_captcha_if_needed(client, group_entity, timeout=30):
    captcha_solved = asyncio.Event()
    captcha_failed = asyncio.Event()

    @client.on(events.NewMessage(chats=group_entity))
    async def on_message(event):
        try:
            msg = event.message
            is_mention = False
            me = await client.get_me()

            if msg.mentioned or (msg.entities and any(
                hasattr(e, 'user_id') and e.user_id == me.id
                for e in (msg.entities or [])
            )):
                is_mention = True

            text_lower = (msg.text or "").lower()
            is_captcha_msg = any(kw in text_lower for kw in PROTECTION_BOT_KEYWORDS)

            if (is_mention or is_captcha_msg) and msg.reply_markup:
                logger.info("Captcha detected, attempting to click button...")
                await asyncio.sleep(random.uniform(1.5, 4.0))

                buttons = msg.reply_markup.rows if hasattr(msg.reply_markup, 'rows') else []
                for row in buttons:
                    for button in (row.buttons if hasattr(row, 'buttons') else []):
                        try:
                            await msg.click(button.text if hasattr(button, 'text') else 0)
                            logger.info(f"Clicked captcha button: {getattr(button, 'text', 'unknown')}")
                            await asyncio.sleep(random.uniform(1.0, 2.0))
                            captcha_solved.set()
                            return
                        except Exception as e:
                            logger.warning(f"Button click error: {e}")

                captcha_failed.set()
        except Exception as e:
            logger.warning(f"Captcha handler error: {e}")

    try:
        await asyncio.wait_for(
            asyncio.wait([captcha_solved.wait(), captcha_failed.wait()], return_when=asyncio.FIRST_COMPLETED),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.info("No captcha detected within timeout")
    finally:
        client.remove_event_handler(on_message)

    return captcha_solved.is_set()
