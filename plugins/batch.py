import re
import json
import asyncio
import logging

from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from info import ADMINS, PROTECT_CONTENT
from database.ia_filterdb import save_file, encode, decode, db
from delivery import check_access
from utils import temp, auto_delete

log = logging.getLogger(__name__)
batches = db["batches"]
MEDIA = (enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO,
         enums.MessageMediaType.DOCUMENT, enums.MessageMediaType.PHOTO)


def parse_link(link):
    m = re.match(r"(?:https?://)?(?:t\.me|telegram\.me)/(?:c/)?([\w\-]+)/(\d+)", link)
    if not m:
        return None, None
    chat, msg_id = m.group(1), int(m.group(2))
    if chat.isnumeric():
        chat = int("-100" + chat)
    return chat, msg_id


@Client.on_message(filters.command("batch") & filters.user(ADMINS))
async def batch_cmd(client, message):
    parts = message.text.split()
    if len(parts) != 3:
        return await message.reply(
            "<b>Usage</b>\n<code>/batch first_message_link last_message_link</code>\n\n"
            "Both links must be from the same channel where I am admin.")
    first_chat, first_id = parse_link(parts[1])
    last_chat, last_id = parse_link(parts[2])
    if not first_chat or not last_chat or first_chat != last_chat:
        return await message.reply("❌ Invalid links, or they are from different chats.")
    if first_id > last_id:
        first_id, last_id = last_id, first_id

    try:
        await client.get_chat(first_chat)
    except Exception as e:
        return await message.reply(f"❌ I can't access that chat: <code>{e}</code>")

    doc = {"chat_id": first_chat, "first": first_id, "last": last_id}
    res = await batches.insert_one(doc)
    bid = str(res.inserted_id)
    link = f"https://t.me/{temp.U_NAME}?start=batch_{bid}"
    await message.reply(
        f"<b>✅ Batch link created</b>\n\n"
        f"Files: <code>{last_id - first_id + 1}</code>\n\n{link}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔗 Open batch", url=link)]]))


@Client.on_message(filters.command("link") & filters.user(ADMINS) & filters.reply)
async def single_link(client, message):
    reply = message.reply_to_message
    if not reply.media or reply.media not in MEDIA:
        return await message.reply("Reply to a file to get its shareable link.")
    media = getattr(reply, reply.media.value, None)
    media.file_type = reply.media.value
    media.caption = reply.caption.html if reply.caption else ""
    await save_file(media)
    link = f"https://t.me/{temp.U_NAME}?start=file_{media.file_unique_id}"
    await message.reply(f"<b>🔗 Shareable link</b>\n\n{link}",
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("Open", url=link)]]))


async def send_batch(client, message, batch_id):
    from bson import ObjectId
    try:
        doc = await batches.find_one({"_id": ObjectId(batch_id)})
    except Exception:
        doc = None
    if not doc:
        return await message.reply("❌ This batch link is invalid or expired.")

    user_id = message.from_user.id
    allowed, kb, text = await check_access(client, user_id)
    if not allowed:
        return await message.reply(text, reply_markup=kb)

    status = await message.reply("📦 Sending files, please wait…")
    sent = 0
    ids = list(range(doc["first"], doc["last"] + 1))
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        try:
            messages = await client.get_messages(doc["chat_id"], chunk)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            continue
        except Exception as e:
            log.warning(e)
            continue
        for msg in messages:
            if not msg or msg.empty or not msg.media:
                continue
            try:
                m = await msg.copy(user_id, protect_content=PROTECT_CONTENT)
                asyncio.create_task(auto_delete(m))
                sent += 1
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception as e:
                log.warning(f"batch copy: {e}")
            await asyncio.sleep(0.4)  # stay under flood limits
    await status.edit(f"✅ Sent <code>{sent}</code> files.")
