import re
import asyncio
import logging

from pyrogram import Client, filters, enums
from pyrogram.errors import PeerIdInvalid, UserIsBlocked, MessageNotModified
from pyrogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                            CallbackQuery, Message)

from info import (MAX_BTN, ADMINS, SUPPORT_LINK, PICS, START_TXT, HELP_TXT,
                  ABOUT_TXT, OWNER_USERNAME, AUTH_CHANNEL, LANGUAGES, QUALITIES)
from database.ia_filterdb import get_search_results, get_file_details, delete_files
from database.users_chats_db import db
from database.filters_mdb import find_filter
from delivery import deliver_file, premium_keyboard, user_plan
from utils import (get_size, temp, BUTTONS, is_subscribed, auto_delete,
                   parser, time_left)
from plugins.premium import premium_text

log = logging.getLogger(__name__)

IGNORE = re.compile(r"^[/!.#]|^\s*$|^\d+$")


def key_of(message):
    return f"{message.chat.id}_{message.id}"


async def build_results(query, key, offset=0, quality=None, lang=None):
    search = query
    if quality:
        search = f"{query} {quality}"
    if lang:
        search = f"{query} {lang}"
    files, next_offset, total = await get_search_results(search, offset=offset,
                                                         max_results=MAX_BTN)
    if not files:
        return None, 0, 0
    btn = [[InlineKeyboardButton(
        text=f"[{get_size(f['file_size'])}] {f['file_name'][:55]}",
        callback_data=f"files#{f['_id']}")] for f in files]

    page = (offset // MAX_BTN) + 1
    pages = max(1, -(-total // MAX_BTN))
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton("⬅️ Back",
                                        callback_data=f"nav#{max(offset - MAX_BTN, 0)}#{key}"))
    nav.append(InlineKeyboardButton(f"📄 {page}/{pages}", callback_data="pages"))
    if next_offset:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"nav#{next_offset}#{key}"))
    if len(nav) > 1:
        btn.append(nav)
    btn.append([InlineKeyboardButton("💎 Premium", callback_data="premium_info"),
                InlineKeyboardButton("🗑 Close", callback_data="close")])
    return InlineKeyboardMarkup(btn), total, pages


@Client.on_message(filters.text & (filters.group | filters.private) & filters.incoming, group=1)
async def auto_filter(client, message: Message):
    if not message.from_user:
        return
    text = (message.text or "").strip()
    if IGNORE.search(text) or len(text) < 2 or len(text) > 100:
        return
    if await db.is_banned(message.from_user.id):
        return

    if message.chat.type == enums.ChatType.PRIVATE:
        await db.add_user(message.from_user.id, message.from_user.first_name)
    else:
        await db.add_chat(message.chat.id, message.chat.title)

    # ---------- 1) manual filter has priority ----------
    mf = await find_filter(message.chat.id, text)
    if mf:
        reply, buttons = parser(mf.get("reply") or "", text)
        markup = InlineKeyboardMarkup(buttons) if buttons else None
        try:
            if mf.get("file"):
                await message.reply_cached_media(mf["file"], caption=reply or "",
                                                 reply_markup=markup)
            else:
                await message.reply(reply or text, reply_markup=markup,
                                    disable_web_page_preview=True)
            return
        except Exception as e:
            log.warning(f"manual filter: {e}")

    # ---------- 2) auto filter ----------
    key = key_of(message)
    BUTTONS[key] = text
    markup, total, pages = await build_results(text, key)
    if not markup:
        if message.chat.type == enums.ChatType.PRIVATE:
            m = await message.reply(
                f"❌ <b>No result found for</b> <code>{text}</code>\n\n"
                f"• Check the spelling\n• Try the original movie name (no year/quality)\n"
                f"• Or request it in the support group.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🆘 Request in Support", url=SUPPORT_LINK)]]))
            asyncio.create_task(auto_delete(m, 120))
        return

    plan = await user_plan(message.from_user.id)
    BUTTONS[key] = {"q": text, "user": message.from_user.mention, "plan": plan}
    m = await message.reply(head_text(text, total, 1, pages,
                                      message.from_user.mention, plan),
                            reply_markup=markup, quote=True)
    asyncio.create_task(auto_delete(m, 900))


def head_text(query, total, page, pages, mention, plan):
    return (f"<b>🔎 Results for :</b> <code>{query}</code>\n"
            f"<b>📁 Found :</b> <code>{total}</code> files  •  <b>Page {page}/{pages}</b>\n"
            f"<b>👤 Requested by :</b> {mention}\n"
            f"<b>💠 Plan :</b> "
            f"{'💎 Premium — direct files' if plan == 'premium' else '🆓 Free'}")


@Client.on_callback_query(filters.regex(r"^nav#"))
async def navigate(client, query: CallbackQuery):
    _, offset, key = query.data.split("#", 2)
    data = BUTTONS.get(key)
    if not data:
        return await query.answer("⏳ This search expired. Please send the name again.",
                                  show_alert=True)
    offset = int(offset)
    markup, total, pages = await build_results(data["q"], key, offset=offset)
    if not markup:
        return await query.answer("No more results.", show_alert=True)
    page = (offset // MAX_BTN) + 1
    try:
        await query.message.edit_text(
            head_text(data["q"], total, page, pages, data["user"], data["plan"]),
            reply_markup=markup)
    except MessageNotModified:
        pass
    except Exception as e:
        log.warning(f"nav: {e}")
    await query.answer()



@Client.on_callback_query(filters.regex(r"^files#"))
async def file_cb(client, query: CallbackQuery):
    file_id = query.data.split("#", 1)[1]
    user_id = query.from_user.id

    if await db.is_banned(user_id):
        return await query.answer("🚫 You are banned.", show_alert=True)

    if AUTH_CHANNEL and not await is_subscribed(client, user_id):
        return await query.answer("🔒 Join our channel first, then press again.",
                                  show_alert=True)

    file = await get_file_details(file_id)
    if not file:
        return await query.answer("❌ File not found / deleted.", show_alert=True)

    try:
        ok, err = await deliver_file(client, user_id, file_id)
    except (PeerIdInvalid, UserIsBlocked):
        ok, err = False, "start"
    except Exception as e:
        log.exception(e)
        ok, err = False, str(e)

    if ok:
        return await query.answer("✅ File sent to your PM. Check it!", show_alert=True)
    if err == "verify":
        return await query.answer("🔐 Free clicks over — check your PM to verify or go Premium.",
                                  show_alert=True)
    # user never started the bot
    await query.answer("⚠️ Start me in private first, then press again.", show_alert=True)
    try:
        await query.message.reply(
            f"{query.from_user.mention}, start me in PM to receive files 👇",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🤖 Start Me",
                                       url=f"https://t.me/{temp.U_NAME}?start=file_{file_id}")]]))
    except Exception:
        pass


@Client.on_callback_query(filters.regex(r"^premium_info$"))
async def premium_cb(client, query: CallbackQuery):
    await query.answer()
    try:
        await query.message.edit_text(premium_text(query.from_user.id),
                                      reply_markup=premium_keyboard())
    except Exception:
        await query.message.reply(premium_text(query.from_user.id),
                                  reply_markup=premium_keyboard())


@Client.on_callback_query(filters.regex(r"^(help|about|start|pages|close)$"))
async def misc_cb(client, query: CallbackQuery):
    data = query.data
    if data == "pages":
        return await query.answer()
    if data == "close":
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        return
    back = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="start")]])
    if data == "help":
        text, kb = HELP_TXT, back
    elif data == "about":
        text, kb = ABOUT_TXT.format(owner=OWNER_USERNAME), back
    else:
        from plugins.commands import start_keyboard, plan_line
        text = START_TXT.format(mention=query.from_user.mention,
                                plan=await plan_line(query.from_user.id))
        kb = start_keyboard()
    await query.answer()
    try:
        await query.message.edit_text(text, reply_markup=kb)
    except Exception:
        await query.message.reply(text, reply_markup=kb)


# ---------------- admin: delete files ----------------
@Client.on_message(filters.command("delete") & filters.user(ADMINS))
async def delete_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: <code>/delete file name</code>")
    query = message.text.split(None, 1)[1]
    n = await delete_files(query)
    await message.reply(f"🗑 Deleted <code>{n}</code> file(s) matching <code>{query}</code>")


@Client.on_message(filters.command("deleteall") & filters.user(ADMINS))
async def deleteall_cmd(client, message):
    from database.ia_filterdb import col
    await message.reply(
        "⚠️ This will delete <b>ALL</b> indexed files. Are you sure?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, delete everything", callback_data="delall_yes")],
            [InlineKeyboardButton("❌ Cancel", callback_data="close")]]))


@Client.on_callback_query(filters.regex(r"^delall_yes$"))
async def delall_cb(client, query):
    if query.from_user.id not in ADMINS:
        return await query.answer("Admins only.", show_alert=True)
    from database.ia_filterdb import col
    await col.delete_many({})
    await query.message.edit_text("🗑 All files deleted from the database.")
