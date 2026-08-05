import logging

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from info import ADMINS
from database.filters_mdb import add_filter, delete_filter, get_filters, del_all
from utils import split_quotes, parser

log = logging.getLogger(__name__)


async def _is_allowed(client, message):
    if message.from_user and message.from_user.id in ADMINS:
        return True
    if message.chat.type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
        try:
            member = await client.get_chat_member(message.chat.id, message.from_user.id)
            return member.status in (enums.ChatMemberStatus.OWNER,
                                     enums.ChatMemberStatus.ADMINISTRATOR)
        except Exception:
            return False
    return False


@Client.on_message(filters.command(["addfilter", "add"]))
async def add_manual_filter(client, message):
    """
    /addfilter <keyword> <reply text>            (text filter)
    reply to a photo/video/document + /addfilter <keyword> <caption>
    Buttons: [Name](buttonurl:https://link.com)
    Use in PM (admins) for a GLOBAL filter, in a group for a group filter.
    """
    if not await _is_allowed(client, message):
        return await message.reply("🚫 Only group admins / bot admins can add filters.")

    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply(
            "<b>Usage</b>\n<code>/addfilter keyword reply text</code>\n"
            "or reply to a photo/file with <code>/addfilter keyword caption</code>\n\n"
            "Buttons: <code>[Watch](buttonurl:https://t.me/yourchannel)</code>")

    extracted = split_quotes(args[1])
    keyword = extracted[0].lower().strip()
    reply_text = extracted[1] if len(extracted) > 1 else ""

    file_ref = file_type = None
    reply = message.reply_to_message
    if reply and reply.media:
        media = getattr(reply, reply.media.value, None)
        if media:
            file_ref = media.file_id
            file_type = reply.media.value
            if not reply_text:
                reply_text = reply.caption.html if reply.caption else ""

    if not reply_text and not file_ref:
        return await message.reply("❌ Give some reply text or reply to a photo/file.")

    chat_id = 0 if message.chat.type == enums.ChatType.PRIVATE else message.chat.id
    await add_filter(chat_id, keyword, reply_text, file_ref=file_ref, file_type=file_type)
    scope = "GLOBAL" if chat_id == 0 else message.chat.title
    await message.reply(f"✅ Manual filter <code>{keyword}</code> saved for <b>{scope}</b>.")


@Client.on_message(filters.command(["delfilter", "del"]))
async def del_manual_filter(client, message):
    if not await _is_allowed(client, message):
        return await message.reply("🚫 Only admins can delete filters.")
    if len(message.command) < 2:
        return await message.reply("Usage: <code>/delfilter keyword</code>")
    keyword = message.text.split(None, 1)[1].lower().strip()
    chat_id = 0 if message.chat.type == enums.ChatType.PRIVATE else message.chat.id
    n = await delete_filter(chat_id, keyword)
    await message.reply("🗑 Filter deleted." if n else "❌ No such filter here.")


@Client.on_message(filters.command(["filters", "viewfilters"]))
async def list_filters(client, message):
    chat_id = 0 if message.chat.type == enums.ChatType.PRIVATE else message.chat.id
    docs = await get_filters(chat_id)
    if not docs:
        return await message.reply("No manual filters saved here yet.")
    text = "<b>🧩 Manual filters</b>\n\n" + "\n".join(
        f"• <code>{d['text']}</code>" for d in docs[:80])
    await message.reply(text)


@Client.on_message(filters.command("delallfilters"))
async def del_all_filters(client, message):
    if not await _is_allowed(client, message):
        return await message.reply("🚫 Only admins.")
    chat_id = 0 if message.chat.type == enums.ChatType.PRIVATE else message.chat.id
    await del_all(chat_id)
    await message.reply("🗑 All manual filters deleted for this chat.")
