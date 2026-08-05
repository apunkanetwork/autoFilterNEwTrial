import logging
import datetime

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from info import (ADMINS, PREMIUM_TXT, PREMIUM_PRICE, FREE_TRIAL_CLICKS,
                  VERIFY_HOURS, OWNER_USERNAME, PREMIUM_UPI)
from database.users_chats_db import db
from delivery import premium_keyboard, user_plan
from utils import time_left, send_log

log = logging.getLogger(__name__)


def premium_text(user_id):
    txt = PREMIUM_TXT.format(price=PREMIUM_PRICE, trial=FREE_TRIAL_CLICKS,
                             hours=VERIFY_HOURS, owner=OWNER_USERNAME, user_id=user_id)
    if PREMIUM_UPI:
        txt += f"\n\n<b>UPI :</b> <code>{PREMIUM_UPI}</code>"
    return txt


@Client.on_message(filters.command(["premium", "buypremium", "plan"]))
async def premium_cmd(client, message):
    await message.reply(premium_text(message.from_user.id),
                        reply_markup=premium_keyboard())


@Client.on_message(filters.command("myplan"))
async def myplan_cmd(client, message):
    uid = message.from_user.id
    await db.add_user(uid, message.from_user.first_name)
    user = await db.get_user(uid)
    plan = await user_plan(uid)
    if plan == "premium":
        text = (f"<b>💎 PREMIUM ACTIVE</b>\n\n"
                f"<b>Expires in :</b> {time_left(user['premium_until'])}\n"
                f"<b>Expiry date :</b> {user['premium_until'].strftime('%d %b %Y, %H:%M')} UTC\n"
                f"<b>Downloads :</b> {user.get('downloads', 0)}")
    elif plan == "verified":
        text = (f"<b>✅ VERIFIED (free plan)</b>\n\n"
                f"Access ends in {time_left(user['verified_until'])}.\n"
                f"Go premium to skip verification forever 💎")
    elif plan == "trial":
        text = (f"<b>🎁 FREE TRIAL</b>\n\n"
                f"Clicks left : <b>{user.get('trial_left', 0)}</b> / {FREE_TRIAL_CLICKS}")
    else:
        text = ("<b>🆓 FREE PLAN</b>\n\n"
                "Trial used up — verify through a shortlink or buy premium 💎")
    await message.reply(text, reply_markup=premium_keyboard())


@Client.on_message(filters.command("addpremium") & filters.user(ADMINS))
async def add_premium(client, message):
    parts = message.text.split()
    if len(parts) < 3:
        return await message.reply("Usage: <code>/addpremium user_id days</code>")
    try:
        uid, days = int(parts[1]), int(parts[2])
    except ValueError:
        return await message.reply("❌ user_id and days must be numbers.")

    await db.add_user(uid, "unknown")
    until = await db.add_premium(uid, days)
    await message.reply(f"✅ Premium added.\n\n<b>User:</b> <code>{uid}</code>\n"
                        f"<b>Days:</b> {days}\n"
                        f"<b>Expires:</b> {until.strftime('%d %b %Y, %H:%M')} UTC")
    try:
        await client.send_message(
            uid,
            f"<b>💎 Congratulations! Premium activated.</b>\n\n"
            f"<b>Duration :</b> {days} day(s)\n"
            f"<b>Expires :</b> {until.strftime('%d %b %Y, %H:%M')} UTC\n\n"
            f"Enjoy direct files with no shortlinks ⚡")
    except Exception:
        await message.reply("⚠️ Added, but I couldn't DM the user (they never started the bot).")
    await send_log(client, f"#PREMIUM_ADDED\nUser: <code>{uid}</code> | {days} days")


@Client.on_message(filters.command("removepremium") & filters.user(ADMINS))
async def remove_premium(client, message):
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("Usage: <code>/removepremium user_id</code>")
    try:
        uid = int(parts[1])
    except ValueError:
        return await message.reply("❌ user_id must be a number.")
    await db.remove_premium(uid)
    await message.reply(f"✅ Premium removed from <code>{uid}</code>")
    try:
        await client.send_message(uid, "<b>❌ Your premium membership was removed by admin.</b>")
    except Exception:
        pass
    await send_log(client, f"#PREMIUM_REMOVED\nUser: <code>{uid}</code>")


@Client.on_message(filters.command("premiumusers") & filters.user(ADMINS))
async def premium_users(client, message):
    cursor = await db.premium_users()
    lines, n = [], 0
    async for u in cursor:
        n += 1
        lines.append(f"{n}. <code>{u['id']}</code> — {time_left(u['premium_until'])} left")
    if not lines:
        return await message.reply("No active premium users.")
    text = "<b>💎 PREMIUM USERS</b>\n\n" + "\n".join(lines[:50])
    if n > 50:
        text += f"\n\n… and {n - 50} more"
    await message.reply(text)


@Client.on_message(filters.command("addtrial") & filters.user(ADMINS))
async def add_trial(client, message):
    parts = message.text.split()
    if len(parts) < 3:
        return await message.reply("Usage: <code>/addtrial user_id clicks</code>")
    uid, clicks = int(parts[1]), int(parts[2])
    await db.users.update_one({"id": uid}, {"$inc": {"trial_left": clicks}}, upsert=True)
    await message.reply(f"✅ Gave {clicks} trial clicks to <code>{uid}</code>")
