"""
Account Warmer — تدفئة الحسابات مع Smart AI Conversation بين الحسابات.
"""
import asyncio
import random
import logging
from datetime import datetime
from telethon.tl.functions.account import UpdateProfileRequest, UpdateStatusRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import GetHistoryRequest, SendMessageRequest
from telethon.tl.types import PeerChannel, PeerUser
from core.device_spoofer import get_random_name, get_random_bio
from core.human_behavior import human_sleep, simulate_online_presence, simulate_offline
from core.database import add_log, update_account_status

logger = logging.getLogger(__name__)

PUBLIC_CHANNELS = [
    "@telegram", "@durov", "@techcrunch", "@bbcarabic",
    "@aljazeera", "@cnn", "@theeconomist", "@nasa",
    "@bbcnews", "@reuters", "@guardian", "@wired",
]

_MORNING_OPENERS = [
    "صباح الخير ☀️",
    "صبحتوا على خير",
    "Good morning! How's your day going?",
    "Morning! Hope you slept well 😊",
    "أهلاً! كيف حالك اليوم؟",
]
_EVENING_OPENERS = [
    "مساء الخير 🌙",
    "كيف كان يومك؟",
    "Good evening! What are you up to?",
    "مساء النور، شو أخبارك؟",
    "Hey! How was your day?",
]
_GENERAL_OPENERS = [
    "هلا 👋",
    "شو أخبارك؟",
    "Hey! What's up?",
    "كيفك؟ زمان ما تواصلنا",
    "Hi there, hope everything's good with you!",
    "ما في جديد؟",
    "Long time no talk! How are things?",
]
_REPLIES = [
    "الحمدلله، تمام تمام",
    "بخير والحمدلله، وانت كيفك؟",
    "great, thanks for asking! 😊",
    "ماشي الحال، شكراً",
    "تمام، بس مشغول هالأيام",
    "Doing well! Just been busy lately",
    "الحمد لله كل شي تمام",
    "Fine, thanks! Miss chatting with you",
]
_FOLLOW_UPS = [
    "إن شاء الله دايم بخير",
    "يا ربي يديم الصحة والسلامة",
    "Keep me posted! Talk later 👋",
    "حلو، خبرني اذا في جديد",
    "Stay safe! 😊",
    "نتكلم بعدين إن شاء الله",
    "Take care! Catch you later",
    "يلا، بحكيك بعدين 🙂",
]
_TOPICS = [
    "شفت الأخبار اليوم؟",
    "Did you watch the game last night?",
    "أي برامج حلوة تنصحني فيها؟",
    "Any good recommendations for movies? 🎬",
    "كيف الشغل معك؟",
    "الجو عندك كيف؟ عندنا حر 🥵",
    "Weather here is crazy today!",
    "Have you tried any good restaurants lately?",
    "شو تسوي هالأيام في وقت الفراغ؟",
]


def _generate_message(turn: int, hour: int) -> str:
    """توليد رسالة طبيعية بناءً على دور المحادثة والوقت."""
    if turn == 0:
        if 5 <= hour < 12:
            return random.choice(_MORNING_OPENERS)
        elif 17 <= hour < 23:
            return random.choice(_EVENING_OPENERS)
        else:
            return random.choice(_GENERAL_OPENERS)
    elif turn == 1:
        return random.choice(_REPLIES)
    elif turn == 2:
        return random.choice(_TOPICS)
    else:
        return random.choice(_FOLLOW_UPS)


async def _type_and_send(client, peer, text: str):
    """محاكاة الكتابة قبل الإرسال."""
    try:
        await client(UpdateStatusRequest(offline=False))
        typing_time = len(text) * random.uniform(0.05, 0.12)
        await asyncio.sleep(min(typing_time, 8))
        await client.send_message(peer, text)
        await asyncio.sleep(random.uniform(1, 3))
    except Exception as e:
        logger.warning(f"Send message error: {e}")


async def ai_chat_warming(clients_accounts: list, job_id=None, rounds: int = 2):
    """
    محادثة ذكية بين حساباتك لمحاكاة السلوك البشري.
    clients_accounts: [(client, account_id, phone), ...]
    rounds: عدد جولات المحادثة
    """
    if len(clients_accounts) < 2:
        logger.info("[SmartWarm] Need at least 2 accounts for AI chat warming")
        return

    hour = datetime.now().hour
    logger.info(f"[SmartWarm] Starting AI chat warming with {len(clients_accounts)} accounts")

    for round_num in range(rounds):
        random.shuffle(clients_accounts)
        pairs = [
            (clients_accounts[i], clients_accounts[i + 1])
            for i in range(0, len(clients_accounts) - 1, 2)
        ]

        for (client_a, acc_id_a, phone_a), (client_b, acc_id_b, phone_b) in pairs:
            try:
                logger.info(f"[SmartWarm] Round {round_num+1}: {phone_a} ↔ {phone_b}")

                user_b = await client_a.get_entity(phone_b)
                user_a = await client_b.get_entity(phone_a)

                convo_turns = random.randint(2, 4)
                for turn in range(convo_turns):
                    if turn % 2 == 0:
                        msg = _generate_message(turn, hour)
                        await _type_and_send(client_a, user_b, msg)
                        add_log(job_id, acc_id_a, None, "ai_chat", "sent",
                                f"→ {phone_b}: {msg[:80]}")
                    else:
                        msg = _generate_message(turn, hour)
                        await _type_and_send(client_b, user_a, msg)
                        add_log(job_id, acc_id_b, None, "ai_chat", "sent",
                                f"→ {phone_a}: {msg[:80]}")

                    wait = random.uniform(30, 120) if turn < convo_turns - 1 else 0
                    if wait > 0:
                        await asyncio.sleep(wait)

            except Exception as e:
                logger.warning(f"[SmartWarm] Chat error between accounts: {e}")

        if round_num < rounds - 1:
            await asyncio.sleep(random.uniform(300, 900))

    logger.info("[SmartWarm] AI chat warming complete")


async def update_profile(client, account_id, job_id=None):
    try:
        first_name, last_name = get_random_name()
        bio = get_random_bio()
        await client(UpdateProfileRequest(
            first_name=first_name,
            last_name=last_name,
            about=bio
        ))
        logger.info(f"Profile updated: {first_name} {last_name}")
        add_log(job_id, account_id, None, "warm_profile", "success", f"Set name: {first_name} {last_name}")
        await asyncio.sleep(random.uniform(2, 5))
    except Exception as e:
        logger.warning(f"Profile update error: {e}")


async def join_random_channels(client, account_id, count=3, job_id=None):
    channels = random.sample(PUBLIC_CHANNELS, min(count, len(PUBLIC_CHANNELS)))
    joined = 0
    for ch in channels:
        try:
            await simulate_online_presence(client)
            await client(JoinChannelRequest(ch))
            joined += 1
            logger.info(f"Joined channel: {ch}")
            add_log(job_id, account_id, None, "warm_join", "success", f"Joined {ch}")
            await asyncio.sleep(random.uniform(5, 20))
        except Exception as e:
            logger.warning(f"Cannot join {ch}: {e}")

    return joined


async def browse_channel(client, channel, messages=10):
    try:
        entity = await client.get_entity(channel)
        await client(GetHistoryRequest(
            peer=entity,
            limit=messages,
            offset_date=None,
            offset_id=0,
            max_id=0,
            min_id=0,
            add_offset=0,
            hash=0
        ))
        await asyncio.sleep(random.uniform(3, 12))
    except Exception as e:
        logger.warning(f"Browse error: {e}")


async def warm_account(client, account_id, days=3, job_id=None):
    logger.info(f"Starting warm-up for account {account_id}")
    update_account_status(account_id, "warming")

    try:
        await update_profile(client, account_id, job_id)
        await human_sleep(10, 30)

        await join_random_channels(client, account_id, count=2, job_id=job_id)

        for day in range(1, days + 1):
            logger.info(f"Warming day {day}/{days}")
            await simulate_online_presence(client)

            for _ in range(random.randint(3, 7)):
                ch = random.choice(PUBLIC_CHANNELS)
                await browse_channel(client, ch, messages=random.randint(5, 20))
                await human_sleep(30, 120)

            if day < days:
                logger.info(f"Day {day} done. Waiting before next day session...")
                await simulate_offline(client)
                rest_hours = random.uniform(3, 8)
                logger.info(f"Account resting for {rest_hours:.1f}h (simulated)")
                add_log(job_id, account_id, None, "warm_day", "success", f"Day {day} completed")

        update_account_status(account_id, "active")
        add_log(job_id, account_id, None, "warm_complete", "success", f"Warm-up done after {days} days")
        logger.info(f"Account {account_id} warm-up complete!")
        return True

    except Exception as e:
        logger.error(f"Warming error: {e}")
        add_log(job_id, account_id, None, "warm_error", "error", str(e))
        return False
