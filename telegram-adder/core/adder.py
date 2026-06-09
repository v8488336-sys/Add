import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest
from telethon.tl.types import InputPeerUser, Channel
from telethon.errors import (
    FloodWaitError, UserPrivacyRestrictedError, UserBannedInChannelError,
    UserKickedError, UserNotMutualContactError, PeerFloodError,
    ChatWriteForbiddenError, UserChannelsTooMuchError, InputUserDeactivatedError,
    UserDeactivatedBanError, PhoneNumberBannedError, SessionRevokedError
)
from core.human_behavior import simulate_online_presence, simulate_offline, occasional_break
from core.database import (
    update_member_status, update_account_status, increment_daily_count,
    add_log, update_job, get_accounts,
    add_to_blacklist, is_blacklisted
)

logger = logging.getLogger(__name__)

DAILY_LIMIT = 40
MAX_ERRORS_BEFORE_FREEZE = 3


async def add_user_to_group(client, target_group, user_data):
    user_entity = InputPeerUser(
        user_id=user_data["user_id"],
        access_hash=user_data["access_hash"]
    )
    target = await client.get_entity(target_group)

    if isinstance(target, Channel) and target.megagroup:
        await client(InviteToChannelRequest(target, [user_entity]))
    else:
        await client(AddChatUserRequest(
            chat_id=target.id,
            user_id=user_entity,
            fwd_limit=50
        ))


class WorkerManager:
    def __init__(self, job_id, target_group, source_group, delay_min, delay_max):
        self.job_id = job_id
        self.target_group = target_group
        self.source_group = source_group
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.queue = asyncio.Queue()
        self.stop_event = asyncio.Event()
        self.stats = {
            "added": 0,
            "privacy": 0,
            "flood": 0,
            "error": 0,
            "skipped": 0,
            "blacklisted": 0,
        }

    def put_members(self, members):
        filtered = 0
        for m in members:
            if is_blacklisted(m["user_id"]):
                filtered += 1
                self.stats["blacklisted"] += 1
                continue
            self.queue.put_nowait(m)
        queued = len(members) - filtered
        update_job(self.job_id, total=queued)
        if filtered:
            logger.info(f"[Queue] Skipped {filtered} blacklisted users before queueing")
        return queued, filtered

    def stop(self):
        self.stop_event.set()

    async def run_worker(self, worker_id, client, account_id):
        logger.info(f"[Worker {worker_id}] Started")
        consecutive_errors = 0
        await simulate_online_presence(client)

        while not self.queue.empty() and not self.stop_event.is_set():
            try:
                user_data = self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            try:
                await simulate_online_presence(client)
                await asyncio.sleep(random.uniform(0.5, 2.0))
                await add_user_to_group(client, self.target_group, user_data)

                update_member_status(user_data["user_id"], self.source_group, "added", account_id)
                increment_daily_count(account_id)
                add_log(self.job_id, account_id, user_data["user_id"], "add", "success")
                self.stats["added"] += 1
                update_job(self.job_id, done=1)
                logger.info(f"[Worker {worker_id}] Added: {user_data.get('username') or user_data['user_id']}")

                consecutive_errors = 0

                delay = random.uniform(self.delay_min, self.delay_max)
                jitter = random.gauss(0, 5)
                await asyncio.sleep(max(10, delay + jitter))
                await occasional_break(probability=0.03)

            except FloodWaitError as e:
                wait_time = e.seconds
                logger.warning(f"[Worker {worker_id}] FloodWait {wait_time}s — freezing account")
                self.stats["flood"] += 1
                update_job(self.job_id, errors=1)

                freeze_until = datetime.now(timezone.utc) + timedelta(seconds=wait_time + 60)
                update_account_status(account_id, "flood", freeze_until)
                add_log(self.job_id, account_id, user_data["user_id"], "add", "flood",
                        f"FloodWait {wait_time}s")

                await self.queue.put(user_data)
                break

            except PeerFloodError:
                logger.warning(f"[Worker {worker_id}] PeerFlood — account restricted")
                self.stats["flood"] += 1
                update_account_status(account_id, "restricted")
                add_log(self.job_id, account_id, user_data["user_id"], "add", "peer_flood")
                await self.queue.put(user_data)
                break

            except UserPrivacyRestrictedError:
                username = user_data.get("username")
                add_to_blacklist(user_data["user_id"], username, reason="privacy_restricted")
                update_member_status(user_data["user_id"], self.source_group, "privacy")
                self.stats["privacy"] += 1
                self.stats["blacklisted"] += 1
                add_log(self.job_id, account_id, user_data["user_id"], "add", "privacy",
                        f"Added to global blacklist: @{username or user_data['user_id']}")
                logger.info(f"[Worker {worker_id}] Blacklisted: {user_data['user_id']} (privacy)")
                self.queue.task_done()

            except (UserBannedInChannelError, UserKickedError):
                update_member_status(user_data["user_id"], self.source_group, "banned",
                                     error_msg="Banned/kicked from channel")
                self.stats["error"] += 1
                update_job(self.job_id, errors=1)
                add_log(self.job_id, account_id, user_data["user_id"], "add", "banned")
                self.queue.task_done()

            except (InputUserDeactivatedError, UserDeactivatedBanError):
                add_to_blacklist(user_data["user_id"], user_data.get("username"), reason="deactivated")
                update_member_status(user_data["user_id"], self.source_group, "deactivated")
                self.stats["skipped"] += 1
                self.queue.task_done()

            except (SessionRevokedError, PhoneNumberBannedError) as e:
                logger.error(f"[Worker {worker_id}] Account banned/revoked: {e}")
                update_account_status(account_id, "banned")
                add_log(self.job_id, account_id, None, "account", "banned", str(e))
                await self.queue.put(user_data)
                break

            except UserChannelsTooMuchError:
                update_member_status(user_data["user_id"], self.source_group, "channels_limit",
                                     error_msg="User in too many channels")
                self.stats["error"] += 1
                self.queue.task_done()

            except Exception as e:
                logger.error(f"[Worker {worker_id}] Error: {type(e).__name__}: {e}")
                consecutive_errors += 1
                self.stats["error"] += 1
                update_job(self.job_id, errors=1)
                update_member_status(user_data["user_id"], self.source_group, "error", error_msg=str(e)[:200])
                add_log(self.job_id, account_id, user_data["user_id"], "add", "error", str(e)[:200])

                if consecutive_errors >= MAX_ERRORS_BEFORE_FREEZE:
                    logger.warning(f"[Worker {worker_id}] Too many errors, pausing")
                    await asyncio.sleep(random.uniform(30, 90))
                    consecutive_errors = 0
                else:
                    await asyncio.sleep(random.uniform(5, 15))

                self.queue.task_done()

        await simulate_offline(client)
        logger.info(f"[Worker {worker_id}] Done. Stats: {self.stats}")

    async def run_all(self, clients_accounts):
        update_job(self.job_id, status="running")
        tasks = []
        for i, (client, account_id) in enumerate(clients_accounts):
            task = asyncio.create_task(self.run_worker(i + 1, client, account_id))
            tasks.append(task)
            await asyncio.sleep(random.uniform(2, 5))

        await asyncio.gather(*tasks, return_exceptions=True)
        update_job(self.job_id, status="completed")
        logger.info(f"All workers done. Final stats: {self.stats}")
        return self.stats
