import re
import asyncio
import logging

from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from info import ADMINS, CHANNELS
from database.ia_filterdb import save_file
from utils import temp

log = logging.getLogger(__name__)
lock = asyncio.Lock()
MEDIA = (enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO,
         enums.MessageMediaType.DOCUMENT)


@Client.on_message(filters.chat(CHANNELS) & filters.media if CHANNELS else filters.chat([0]))
async def new_file(client, message):
    """Auto-index NEW files posted to your database channels."""
    media = getattr(message, message.media.value, None) if message.media else None
    if not media or message.media not in MEDIA:
        return
    media.file_type = message.media.value
    media.caption = message.caption.html if message.caption else ""
    await save_file(media)


@Client.on_message(filters.command("index") & filters.user(ADMINS))
async def index_hint(client, message):
    await message.reply(
        "<b>📥 INDEX OLD FILES</b>\n\n"
        "1. Make me admin in your database channel.\n"
        "2. <b>Forward the LAST message</b> of that channel to me, or\n"
        "3. Send its post link like <code>https://t.me/c/123456789/999</code>\n\n"
        "I will then index everything from that message down to the first one.")


@Client.on_message((filters.forwarded | (filters.regex(r"(https?://)?(t\.me|telegram\.me)/"))) &
                   filters.private & filters.user(ADMINS) & filters.incoming)
async def index_request(client, message):
    if message.text and "/c/" not in message.text and "t.me/" not in message.text \
            and not message.forward_from_chat:
        return
    if message.forward_from_chat and message.forward_from_chat.type == enums.ChatType.CHANNEL:
        chat_id = message.forward_from_chat.id
        last_msg_id = message.forward_from_message_id
    elif message.text:
        m = re.match(r"(?:https?://)?(?:t\.me|telegram\.me)/(?:c/)?(\-?\w+)/(\d+)", message.text)
        if not m:
            return
        chat_id, last_msg_id = m.group(1), int(m.group(2))
        if chat_id.isnumeric():
            chat_id = int("-100" + chat_id)
    else:
        return

    try:
        chat = await client.get_chat(chat_id)
    except Exception as e:
        return await message.reply(f"❌ I can't access that chat: <code>{e}</code>\n"
                                   f"Make me admin there first.")
    if chat.type != enums.ChatType.CHANNEL:
        return await message.reply("❌ That is not a channel.")

    await message.reply(
        f"<b>Index files from</b> <code>{chat.title}</code>?\n"
        f"<b>Last message id:</b> <code>{last_msg_id}</code>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Start indexing",
                                  callback_data=f"index#{chat.id}#{last_msg_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="close")]]))


@Client.on_callback_query(filters.regex(r"^index#"))
async def start_index(client, query):
    if query.from_user.id not in ADMINS:
        return await query.answer("Admins only.", show_alert=True)
    if lock.locked():
        return await query.answer("⏳ Another indexing task is already running.",
                                  show_alert=True)
    _, chat_id, last_id = query.data.split("#")
    await query.answer()
    await query.message.edit_text(
        "⏳ Indexing started…",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🛑 Cancel", callback_data="index_cancel")]]))
    temp.CANCEL = False
    async with lock:
        await do_index(client, query.message, int(chat_id), int(last_id))


@Client.on_callback_query(filters.regex(r"^index_cancel$"))
async def cancel_index(client, query):
    temp.CANCEL = True
    await query.answer("🛑 Cancelling…", show_alert=True)


async def do_index(client, status_msg, chat_id, last_msg_id):
    total = saved = dup = errors = skipped = 0
    try:
        async for message in iter_messages(client, chat_id, last_msg_id):
            if temp.CANCEL:
                break
            total += 1
            if total % 100 == 0:
                try:
                    await status_msg.edit_text(
                        f"<b>📥 Indexing…</b>\n\n"
                        f"Scanned: <code>{total}</code>\n"
                        f"✅ Saved: <code>{saved}</code>\n"
                        f"♻️ Duplicates: <code>{dup}</code>\n"
                        f"⏭ Skipped: <code>{skipped}</code>\n"
                        f"❌ Errors: <code>{errors}</code>",
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("🛑 Cancel", callback_data="index_cancel")]]))
                except Exception:
                    pass
            if not message or message.empty or not message.media:
                skipped += 1
                continue
            if message.media not in MEDIA:
                skipped += 1
                continue
            media = getattr(message, message.media.value, None)
            if not media:
                skipped += 1
                continue
            media.file_type = message.media.value
            media.caption = message.caption.html if message.caption else ""
            ok, code = await save_file(media)
            if ok:
                saved += 1
            elif code == 0:
                dup += 1
            else:
                errors += 1
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        log.exception(e)
        return await status_msg.edit_text(f"❌ Indexing stopped: <code>{e}</code>")

    await status_msg.edit_text(
        f"<b>✅ Indexing completed</b>\n\n"
        f"Scanned: <code>{total}</code>\n"
        f"Saved: <code>{saved}</code>\n"
        f"Duplicates: <code>{dup}</code>\n"
        f"Skipped: <code>{skipped}</code>\n"
        f"Errors: <code>{errors}</code>")


async def iter_messages(client, chat_id, last_msg_id, batch=200):
    """Fallback iterator (Pyrogram v2 removed iter_messages)."""
    current = last_msg_id
    while current > 0:
        ids = list(range(max(current - batch + 1, 1), current + 1))[::-1]
        try:
            messages = await client.get_messages(chat_id, ids)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            continue
        except Exception as e:
            log.warning(f"get_messages: {e}")
            messages = []
        for m in messages:
            yield m
        current -= batch
        await asyncio.sleep(0.2)
