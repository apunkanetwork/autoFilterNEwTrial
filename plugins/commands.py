import logging
import asyncio
import datetime

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from info import (ADMINS, START_TXT, HELP_TXT, ABOUT_TXT, PREMIUM_TXT, PICS,
                  OWNER_USERNAME, SUPPORT_LINK, PREMIUM_PRICE, FREE_TRIAL_CLICKS,
                  VERIFY_HOURS, AUTH_CHANNEL, LOG_CHANNEL)
from database.users_chats_db import db
from database.ia_filterdb import total_files, db_size, decode
from database.filters_mdb import count_filters
from delivery import deliver_file, user_plan
from utils import (temp, is_subscribed, get_size, send_log, time_left,
                   humanbytes, get_readable_time)

log = logging.getLogger(__name__)
import random


def start_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add me to your Group ➕",
                              url=f"https://t.me/{temp.U_NAME}?startgroup=true")],
        [InlineKeyboardButton("💎 Premium", callback_data="premium_info"),
         InlineKeyboardButton("📖 Help", callback_data="help")],
        [InlineKeyboardButton("🆘 Support", url=SUPPORT_LINK),
         InlineKeyboardButton("ℹ️ About", callback_data="about")],
    ])


async def plan_line(user_id):
    plan = await user_plan(user_id)
    if plan == "premium":
        u = await db.get_user(user_id)
        return f"💎 Premium ({time_left(u['premium_until'])} left)"
    if plan == "verified":
        u = await db.get_user(user_id)
        return f"✅ Verified ({time_left(u['verified_until'])} left)"
    if plan == "trial":
        return f"🎁 Free Trial ({await db.trial_left(user_id)} clicks left)"
    return "🆓 Free (verification required)"


@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    user = message.from_user
    new = await db.add_user(user.id, user.first_name)
    if new:
        await send_log(client, f"#NEW_USER\n{user.mention} — <code>{user.id}</code>")

    if await db.is_banned(user.id):
        return await message.reply("🚫 You are banned from using this bot.")

    # force subscribe
    if AUTH_CHANNEL and not await is_subscribed(client, user.id):
        try:
            invite = (await client.get_chat(AUTH_CHANNEL)).invite_link or \
                     await client.export_chat_invite_link(AUTH_CHANNEL)
        except Exception:
            invite = SUPPORT_LINK
        payload = message.command[1] if len(message.command) > 1 else "start"
        return await message.reply(
            "<b>🔒 Please join our channel to use this bot.</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url=invite)],
                [InlineKeyboardButton("🔄 Try Again",
                                      url=f"https://t.me/{temp.U_NAME}?start={payload}")],
            ]))

    if len(message.command) == 1:
        return await message.reply_photo(
            photo=random.choice(PICS),
            caption=START_TXT.format(mention=user.mention, plan=await plan_line(user.id)),
            reply_markup=start_keyboard())

    payload = message.command[1]

    # ---- verification return ----
    if payload.startswith("verify-"):
        token = payload.split("-", 1)[1]
        saved = await db.get_verify_token(user.id)
        if saved and saved == token:
            until = await db.mark_verified(user.id)
            return await message.reply(
                f"<b>✅ Verification successful!</b>\n\n"
                f"You can now download files freely for <b>{VERIFY_HOURS} hours</b>.\n"
                f"Expires in <b>{time_left(until)}</b>.\n\n"
                f"Tired of verifying? Get <b>Premium</b> for {PREMIUM_PRICE} 💎",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("💎 Buy Premium", callback_data="premium_info")]]))
        return await message.reply("❌ Invalid or expired verification link. Try again.")

    # ---- single file ----
    if payload.startswith("file_"):
        fid = payload.split("_", 1)[1]
        ok, err = await deliver_file(client, user.id, fid)
        if not ok and err != "verify":
            await message.reply(err)
        return

    # ---- batch ----
    if payload.startswith("batch_"):
        from plugins.batch import send_batch
        return await send_batch(client, message, payload.split("_", 1)[1])

    await message.reply_photo(
        photo=random.choice(PICS),
        caption=START_TXT.format(mention=user.mention, plan=await plan_line(user.id)),
        reply_markup=start_keyboard())


@Client.on_message(filters.command("help"))
async def help_cmd(client, message):
    await message.reply(HELP_TXT, reply_markup=InlineKeyboardMarkup(
        [[InlineKeyboardButton("💎 Premium", callback_data="premium_info")]]))


@Client.on_message(filters.command("about"))
async def about_cmd(client, message):
    await message.reply(ABOUT_TXT.format(owner=OWNER_USERNAME))


@Client.on_message(filters.command("id"))
async def id_cmd(client, message):
    text = f"<b>Chat ID:</b> <code>{message.chat.id}</code>"
    if message.from_user:
        text += f"\n<b>Your ID:</b> <code>{message.from_user.id}</code>"
    if message.reply_to_message and message.reply_to_message.from_user:
        text += f"\n<b>Replied user:</b> <code>{message.reply_to_message.from_user.id}</code>"
    if message.reply_to_message and message.reply_to_message.forward_from_chat:
        text += f"\n<b>Channel:</b> <code>{message.reply_to_message.forward_from_chat.id}</code>"
    await message.reply(text)


@Client.on_message(filters.command("stats"))
async def stats_cmd(client, message):
    files = await total_files()
    users = await db.total_users()
    chats = await db.total_chats()
    mfl = await count_filters()
    size = await db_size()
    prem = 0
    cursor = await db.premium_users()
    async for _ in cursor:
        prem += 1
    await message.reply(
        f"<b>📊 BOT STATISTICS</b>\n\n"
        f"<b>📁 Files :</b> <code>{files}</code>\n"
        f"<b>🗄 DB size :</b> <code>{humanbytes(size)}</code>\n"
        f"<b>👤 Users :</b> <code>{users}</code>\n"
        f"<b>💎 Premium :</b> <code>{prem}</code>\n"
        f"<b>👥 Groups :</b> <code>{chats}</code>\n"
        f"<b>🧩 Manual filters :</b> <code>{mfl}</code>")


@Client.on_message(filters.command(["ban", "unban"]) & filters.user(ADMINS))
async def ban_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: <code>/ban user_id</code>")
    try:
        uid = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Give a numeric user id.")
    ban = message.command[0].lower() == "ban"
    await db.ban_user(uid, ban)
    await message.reply(f"{'🚫 Banned' if ban else '✅ Unbanned'} <code>{uid}</code>")


@Client.on_message(filters.command("users") & filters.user(ADMINS))
async def users_cmd(client, message):
    await message.reply(f"👤 Total users: <code>{await db.total_users()}</code>")


@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.reply)
async def broadcast_cmd(client, message):
    to_send = message.reply_to_message
    status = await message.reply("📢 Broadcasting…")
    total = await db.total_users()
    done = success = failed = blocked = 0
    cursor = await db.all_users()
    async for user in cursor:
        try:
            await to_send.copy(user["id"])
            success += 1
        except Exception as e:
            if "blocked" in str(e).lower() or "deactivated" in str(e).lower():
                blocked += 1
            else:
                failed += 1
        done += 1
        if done % 25 == 0:
            try:
                await status.edit(f"📢 <b>Broadcasting…</b>\n\n"
                                  f"Done: {done}/{total}\n✅ {success} | 🚫 {blocked} | ❌ {failed}")
            except Exception:
                pass
        await asyncio.sleep(0.08)  # flood-safe
    await status.edit(f"✅ <b>Broadcast finished</b>\n\nTotal: {total}\n"
                      f"Success: {success}\nBlocked: {blocked}\nFailed: {failed}")


@Client.on_message(filters.command("logs") & filters.user(ADMINS))
async def logs_cmd(client, message):
    await message.reply(f"Log channel: <code>{LOG_CHANNEL or 'not set'}</code>")


# ---------- track groups ----------
@Client.on_message(filters.group & filters.new_chat_members, group=2)
async def on_added(client, message):
    for member in message.new_chat_members:
        if member.id == temp.ME:
            await db.add_chat(message.chat.id, message.chat.title)
            await send_log(client, f"#NEW_GROUP\n{message.chat.title} "
                                   f"— <code>{message.chat.id}</code>")
            await message.reply(
                "<b>🙏 Thanks for adding me!</b>\n\n"
                "Make me <b>admin</b> and just send any movie / series name here.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("💎 Premium", callback_data="premium_info")]]))
