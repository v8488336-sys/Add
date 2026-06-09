import asyncio
import random
import logging

logger = logging.getLogger(__name__)


async def human_sleep(min_sec=20, max_sec=60):
    delay = random.uniform(min_sec, max_sec)
    jitter = random.uniform(-3, 3)
    total = max(5, delay + jitter)
    logger.debug(f"Human sleep: {total:.1f}s")
    await asyncio.sleep(total)


async def simulate_online_presence(client):
    try:
        from telethon.tl.functions.account import UpdateStatusRequest
        await client(UpdateStatusRequest(offline=False))
        await asyncio.sleep(random.uniform(1.5, 4.0))
    except Exception as e:
        logger.warning(f"Status simulation error: {e}")


async def simulate_offline(client):
    try:
        from telethon.tl.functions.account import UpdateStatusRequest
        await client(UpdateStatusRequest(offline=True))
    except Exception as e:
        logger.warning(f"Offline simulation error: {e}")


async def simulate_typing(client, entity):
    try:
        from telethon.tl.functions.messages import SetTypingRequest
        from telethon.tl.types import SendMessageTypingAction
        await client(SetTypingRequest(peer=entity, action=SendMessageTypingAction()))
        await asyncio.sleep(random.uniform(1.0, 3.0))
    except Exception:
        pass


async def random_pre_action_delay():
    await asyncio.sleep(random.uniform(0.5, 2.5))


async def simulate_reading(min_sec=2, max_sec=8):
    await asyncio.sleep(random.uniform(min_sec, max_sec))


def get_human_delay(base_min=20, base_max=60):
    base = random.uniform(base_min, base_max)
    jitter = random.gauss(0, 5)
    return max(10, base + jitter)


async def occasional_break(probability=0.05, break_min=60, break_max=300):
    if random.random() < probability:
        duration = random.uniform(break_min, break_max)
        logger.info(f"Taking a break for {duration:.0f}s (human simulation)")
        await asyncio.sleep(duration)
