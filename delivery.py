"""Central file-delivery + access control (premium / trial / shortlink verify)."""
import asyncio
import logging

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from info import (PROTECT_CONTENT, AUTO_DELETE, DELETE_TIME, FREE_TRIAL_CLICKS,
                  VERIFY_HOURS, OWNER_USERNAME, VERIFY_TUTORIAL, IS_SHORTENER,
                  SHORTENER_API, SHORTENER_SITE)
from database.ia_filterdb import get_file_details
from database.users_chats_db import db
from utils import get_size, get_shortlink, random_token, temp, auto_delete, send_log

log = logging.getLogger(__name__)

CAPTION = ("<b>📁 {file_name}</b>\n\n"
           "<b>🗂 Size :</b> {file_size}\n"
           "<b>💎 Plan :</b> {plan}\n\n"
           "<b>⚠️ This file will be deleted in {dt} — forward it to saved messages.</b>")


async def user_plan(user_id):
    if await db.is_premium(user_id):
        return "premium"
    if await db.is_verified(user_id):
        return "verified"
    if await db.trial_left(user_id) > 0:
        return "trial"
    return "free"


async def check_access(client, user_id):
    """Returns (allowed, keyboard_if_blocked, text_if_blocked)."""
    plan = await user_plan(user_id)
    if plan in ("premium", "verified"):
        return True, None, None
    if plan == "trial":
        return True, None, None

    # needs verification through a shortlink
    token = random_token()
    await db.set_verify_token(user_id, token)
    deep = f"https://t.me/{temp.U_NAME}?start=verify-{token}"
    short = await get_shortlink(deep)
    buttons = [[InlineKeyboardButton("🔓 Verify & Unlock", url=short)],
               [InlineKeyboardButton("💎 Buy Premium (No Ads)", callback_data="premium_info")]]
    if VERIFY_TUTORIAL:
        buttons.insert(1, [InlineKeyboardButton("❓ How to open link", url=VERIFY_TUTORIAL)])
    text = (f"<b>🔐 Free trial finished!</b>\n\n"
            f"You used all your <b>{FREE_TRIAL_CLICKS} free clicks</b>.\n"
            f"Complete a quick verification to unlock files for <b>{VERIFY_HOURS} hours</b>, "
            f"or go Premium for direct files with <b>no verification at all</b>.")
    return False, InlineKeyboardMarkup(buttons), text


async def deliver_file(client, user_id, file_unique_id, from_message=None):
    """Send the actual file to the user in PM after access checks."""
    file = await get_file_details(file_unique_id)
    if not file:
        return False, "❌ File not found in database (it may have been deleted)."

    allowed, kb, text = await check_access(client, user_id)
    if not allowed:
        await client.send_message(user_id, text, reply_markup=kb)
        return False, "verify"

    plan = await user_plan(user_id)
    if plan == "trial":
        await db.use_trial(user_id)
        left = await db.trial_left(user_id)
        plan_label = f"Free Trial ({max(left,0)} clicks left)"
    elif plan == "premium":
        plan_label = "💎 Premium"
    else:
        plan_label = "Verified (free)"

    from utils import get_readable_time
    caption = CAPTION.format(
        file_name=file["file_name"],
        file_size=get_size(file["file_size"]),
        plan=plan_label,
        dt=get_readable_time(DELETE_TIME),
    )
    try:
        msg = await client.send_cached_media(
            chat_id=user_id,
            file_id=file["file_id"],
            caption=caption,
            protect_content=PROTECT_CONTENT and plan != "premium",
        )
    except Exception as e:
        log.exception(e)
        return False, f"❌ Could not send the file: {e}"

    await db.count_download(user_id)
    if AUTO_DELETE:
        asyncio.create_task(auto_delete(msg))
    return True, "ok"


def premium_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Contact for Premium", url=f"https://t.me/{OWNER_USERNAME}")],
        [InlineKeyboardButton("🔙 Back", callback_data="start")],
    ])
