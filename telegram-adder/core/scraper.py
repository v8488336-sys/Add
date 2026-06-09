import asyncio
import logging
from datetime import datetime, timezone, timedelta
from telethon.tl.types import (
    UserStatusOnline, UserStatusRecently, UserStatusLastWeek,
    UserStatusLastMonth, UserStatusOffline, UserStatusEmpty,
    ChannelParticipantAdmin, ChannelParticipantCreator
)
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsAdmins
from core.human_behavior import human_sleep, simulate_online_presence
from core.database import save_members, add_log

logger = logging.getLogger(__name__)


def get_last_seen_label(status):
    if isinstance(status, UserStatusOnline):
        return "online"
    elif isinstance(status, UserStatusRecently):
        return "recently"
    elif isinstance(status, UserStatusOffline):
        if status.was_online:
            return status.was_online.strftime("%Y-%m-%d %H:%M")
        return "offline"
    elif isinstance(status, UserStatusLastWeek):
        return "last_week"
    elif isinstance(status, UserStatusLastMonth):
        return "last_month"
    elif isinstance(status, UserStatusEmpty):
        return "long_time_ago"
    return "unknown"


def is_active_user(user, filter_hours=48):
    status = user.status
    if isinstance(status, UserStatusOnline):
        return True
    if isinstance(status, UserStatusRecently):
        return True
    if isinstance(status, UserStatusOffline) and status.was_online:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=filter_hours)
        return status.was_online >= cutoff
    return False


def should_skip_user(user, admin_ids: set, filter_active=True, filter_hours=48):
    if user.deleted or user.bot or user.fake:
        return True, "deleted/bot/fake"
    if not user.access_hash:
        return True, "no_access_hash"
    if user.id in admin_ids:
        return True, "admin_or_creator"
    if filter_active and not is_active_user(user, filter_hours):
        return True, "inactive"
    return False, None


async def _get_admin_ids(client, group) -> set:
    """اسحب IDs المشرفين والمالكين لتجنبهم أثناء الإضافة."""
    admin_ids = set()
    try:
        result = await client(GetParticipantsRequest(
            channel=group,
            filter=ChannelParticipantsAdmins(),
            offset=0,
            limit=200,
            hash=0
        ))
        for participant in result.participants:
            if isinstance(participant, (ChannelParticipantAdmin, ChannelParticipantCreator)):
                admin_ids.add(participant.user_id)
        logger.info(f"[Scraper] Found {len(admin_ids)} admins/creators to exclude")
    except Exception as e:
        logger.warning(f"[Scraper] Could not fetch admins (will proceed without filter): {e}")
    return admin_ids


async def scrape_members(
    client, account_id, source_group_link,
    filter_active=True, filter_hours=48,
    filter_admins=True,
    job_id=None, progress_callback=None
):
    logger.info(f"Starting scrape from: {source_group_link}")

    try:
        await simulate_online_presence(client)
        group = await client.get_entity(source_group_link)
    except Exception as e:
        logger.error(f"Cannot get group entity: {e}")
        raise

    admin_ids = set()
    if filter_admins:
        admin_ids = await _get_admin_ids(client, group)

    members_data = []
    skipped = 0
    skipped_reasons = {}
    total_fetched = 0

    try:
        async for user in client.iter_participants(group, aggressive=True):
            total_fetched += 1
            skip, reason = should_skip_user(user, admin_ids, filter_active, filter_hours)

            if skip:
                skipped += 1
                skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1
                continue

            last_seen = get_last_seen_label(user.status) if user.status else "unknown"

            members_data.append({
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "access_hash": user.access_hash,
                "phone": user.phone,
                "last_seen": last_seen,
            })

            if len(members_data) % 50 == 0:
                if progress_callback:
                    progress_callback(len(members_data), total_fetched, skipped)
                await asyncio.sleep(0.05)

    except Exception as e:
        logger.error(f"Error during iteration: {e}")
        raise

    if members_data:
        save_members(members_data, source_group_link)
        skip_summary = ", ".join(f"{r}:{c}" for r, c in skipped_reasons.items())
        if job_id:
            add_log(job_id, account_id, None, "scrape", "success",
                    f"Scraped {len(members_data)} members "
                    f"(skipped {skipped}: {skip_summary}) "
                    f"out of {total_fetched} total")

    logger.info(
        f"Scrape complete: {len(members_data)} members saved, "
        f"{skipped} skipped (admins excluded: {len(admin_ids)}) "
        f"out of {total_fetched} total"
    )
    return len(members_data), skipped, total_fetched
