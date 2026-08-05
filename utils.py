import re
import math
import string
import random
import asyncio
import logging
import datetime

import aiohttp
from pyrogram import enums
from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardButton

from info import (SHORTENER_API, SHORTENER_SITE, IS_SHORTENER, AUTH_CHANNEL,
                  LOG_CHANNEL, AUTO_DELETE, DELETE_TIME)

logger = logging.getLogger(__name__)

BUTTONS = {}      # search cache  key -> query
SPELL_CHECK = {}


class temp:
    ME = None
    U_NAME = None
    B_NAME = None
    B_LINK = None
    CANCEL = False


def humanbytes(size):
    if not size:
        return "0 B"
    power = 1024
    n = 0
    units = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    while size > power and n < 4:
        size /= power
        n += 1
    return f"{round(size, 2)} {units[n]}"


get_size = humanbytes


def get_readable_time(seconds: int) -> str:
    periods = [("day", 86400), ("hour", 3600), ("min", 60), ("sec", 1)]
    result = ""
    for name, count in periods:
        if seconds >= count:
            value, seconds = divmod(seconds, count)
            result += f"{int(value)} {name} "
    return result.strip() or "0 sec"


def time_left(until: datetime.datetime) -> str:
    delta = until - datetime.datetime.utcnow()
    if delta.total_seconds() <= 0:
        return "expired"
    return get_readable_time(int(delta.total_seconds()))


def random_token(n=12):
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


async def get_shortlink(link: str) -> str:
    """Convert a link with the configured shortener. Falls back to the raw link."""
    if not (IS_SHORTENER and SHORTENER_API and SHORTENER_SITE):
        return link
    site = SHORTENER_SITE.replace("https://", "").replace("http://", "").strip("/")
    url = f"https://{site}/api"
    params = {"api": SHORTENER_API, "url": link}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, raise_for_status=True,
                                   timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json(content_type=None)
                if data.get("status") == "success" and data.get("shortenedUrl"):
                    return data["shortenedUrl"]
                if data.get("shortenedUrl"):
                    return data["shortenedUrl"]
                logger.warning(f"Shortener error: {data}")
    except Exception as e:
        logger.warning(f"Shortener failed: {e}")
    return link


async def is_subscribed(client, user_id) -> bool:
    if not AUTH_CHANNEL:
        return True
    try:
        member = await client.get_chat_member(AUTH_CHANNEL, user_id)
    except UserNotParticipant:
        return False
    except Exception as e:
        logger.warning(f"force-sub check: {e}")
        return True
    return member.status not in (enums.ChatMemberStatus.BANNED,)


async def auto_delete(message, seconds=None, notice=True):
    """Delete a message after N seconds (keeps groups clean)."""
    if not AUTO_DELETE:
        return
    await asyncio.sleep(seconds or DELETE_TIME)
    try:
        await message.delete()
    except Exception:
        pass


def split_quotes(text: str):
    if not text.startswith(("'", '"')):
        return text.split(None, 1)
    counter = 1
    while counter < len(text):
        if text[counter] == "\\":
            counter += 1
        elif text[counter] == text[0]:
            break
        counter += 1
    else:
        return text.split(None, 1)
    key = text[1:counter].replace("\\", "")
    rest = text[counter + 1:].strip()
    return list(filter(None, [key, rest]))


BTN_URL_REGEX = re.compile(r"(\[([^\[]+?)\]\((buttonurl|buttonalert):(?:/{0,2})(.+?)(:same)?\))")


def parser(text, keyword):
    """Parse [Name](buttonurl:https://...) markup into buttons."""
    if not text:
        return "", []
    buttons = []
    note_data = ""
    prev = 0
    for match in BTN_URL_REGEX.finditer(text):
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1
        if n_escapes % 2 == 0:
            if bool(match.group(5)) and buttons:
                buttons[-1].append(InlineKeyboardButton(text=match.group(2), url=match.group(4)))
            else:
                buttons.append([InlineKeyboardButton(text=match.group(2), url=match.group(4))])
            note_data += text[prev:match.start(1)]
            prev = match.end(1)
        else:
            note_data += text[prev:to_check]
            prev = match.start(1) - 1
    note_data += text[prev:]
    return note_data.strip(), buttons


def gfilters_keyboard(rows):
    return rows


async def send_log(client, text):
    if not LOG_CHANNEL:
        return
    try:
        await client.send_message(LOG_CHANNEL, text, disable_web_page_preview=True)
    except Exception as e:
        logger.warning(f"log channel: {e}")


def extract_user_id(message, args_index=1):
    """Get a user id from command args or a reply."""
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id
    parts = message.text.split()
    if len(parts) > args_index:
        try:
            return int(parts[args_index])
        except ValueError:
            return parts[args_index]
    return None
