import os
import re
from os import environ

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


def is_enabled(value, default=False):
    if value is None:
        return default
    return str(value).lower() in ("true", "yes", "1", "enable", "y", "on")


def to_int_list(value):
    out = []
    for x in str(value or "").split():
        x = x.strip()
        if not x:
            continue
        try:
            out.append(int(x))
        except ValueError:
            out.append(x)
    return out


# ---------------- Telegram / Pyrogram ----------------
API_ID = int(environ.get("API_ID", "0"))
API_HASH = environ.get("API_HASH", "")
BOT_TOKEN = environ.get("BOT_TOKEN", "")
BOT_USERNAME = environ.get("BOT_USERNAME", "")  # without @ (optional, auto-detected)
WORKERS = int(environ.get("WORKERS", "50"))
SESSION = environ.get("SESSION", "AutoFilterBot")

# ---------------- Admins / Channels ----------------
ADMINS = to_int_list(environ.get("ADMINS", ""))
# Channels where your files live (bot must be admin there)
CHANNELS = to_int_list(environ.get("CHANNELS", ""))
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "0") or 0)
SUPPORT_CHAT = environ.get("SUPPORT_CHAT", "")          # @yoursupportgroup
SUPPORT_LINK = environ.get("SUPPORT_LINK", "https://t.me/")
OWNER_USERNAME = environ.get("OWNER_USERNAME", "admin")  # for "Buy Premium" contact

# Force subscribe (0 = disabled). Bot must be admin in that channel.
AUTH_CHANNEL = int(environ.get("AUTH_CHANNEL", "0") or 0)

# ---------------- Database ----------------
DATABASE_URI = environ.get("DATABASE_URI", "")
DATABASE_NAME = environ.get("DATABASE_NAME", "AutoFilterBot")
COLLECTION_NAME = environ.get("COLLECTION_NAME", "Telegram_files")

# ---------------- Shortener ----------------
SHORTENER_SITE = environ.get("SHORTENER_SITE", "")   # e.g. shrinkme.io
SHORTENER_API = environ.get("SHORTENER_API", "")     # your api key
VERIFY_TUTORIAL = environ.get("VERIFY_TUTORIAL", "")  # how-to-open-link video url
IS_SHORTENER = is_enabled(environ.get("IS_SHORTENER"), True)
VERIFY_HOURS = int(environ.get("VERIFY_HOURS", "24"))  # access time after 1 shortlink

# ---------------- Premium / Trial ----------------
FREE_TRIAL_CLICKS = int(environ.get("FREE_TRIAL_CLICKS", "2"))
PREMIUM_PRICE = environ.get("PREMIUM_PRICE", "₹50 / month")
PREMIUM_UPI = environ.get("PREMIUM_UPI", "")  # optional UPI id shown on the premium page

# ---------------- Behaviour ----------------
MAX_BTN = int(environ.get("MAX_BTN", "10"))
CACHE_TIME = int(environ.get("CACHE_TIME", "300"))
USE_CAPTION_FILTER = is_enabled(environ.get("USE_CAPTION_FILTER"), True)
AUTO_DELETE = is_enabled(environ.get("AUTO_DELETE"), True)
DELETE_TIME = int(environ.get("DELETE_TIME", "600"))  # seconds
PROTECT_CONTENT = is_enabled(environ.get("PROTECT_CONTENT"), False)
LANGUAGES = ["hindi", "english", "tamil", "telugu", "malayalam", "kannada",
             "marathi", "bengali", "punjabi", "gujarati", "korean", "japanese"]
QUALITIES = ["360p", "480p", "720p", "1080p", "2160p", "4k", "hdrip", "webrip",
             "web-dl", "hdcam", "predvd", "bluray"]

PICS = (environ.get("PICS") or
        "https://telegra.ph/file/6f0b4d8f0dfe1a2d3b9d7.jpg").split()

# ---------------- Web server (keep-alive for VPS/Koyeb/Render) ----------------
PORT = int(environ.get("PORT", "8080"))

# ---------------- Messages ----------------
START_TXT = """<b>Hey {mention} 👋

I am an <u>Advanced Auto-Filter Bot</u>.

➜ Add me to your group as <b>admin</b>
➜ Just send a movie / series name
➜ I will find it in my database instantly ⚡

<b>Plan:</b> {plan}</b>"""

HELP_TXT = """<b>📘 How to use me</b>

<b>• Auto Filter</b> — send any file name in group/PM, I search all connected channels.
<b>• Manual Filter</b> — <code>/addfilter name</code> (reply to a photo/text/file) to force a custom result.
<b>• Batch</b> — <code>/batch first_link last_link</code> to make one shareable link for many files.
<b>• Index</b> — forward any message from your channel or use <code>/index</code> to save old files.
<b>• Premium</b> — no shortlinks, instant files, no ads. <code>/premium</code>

<b>Admin commands</b>
<code>/addpremium id days</code> · <code>/removepremium id</code> · <code>/premiumusers</code>
<code>/index</code> · <code>/delete</code> · <code>/deleteall</code> · <code>/stats</code> · <code>/broadcast</code>
<code>/ban id</code> · <code>/unban id</code> · <code>/users</code> · <code>/logs</code>"""

ABOUT_TXT = """<b>🤖 Bot :</b> Advanced AutoFilter
<b>📡 Server :</b> VPS
<b>🗄 Database :</b> MongoDB
<b>🧩 Library :</b> Pyrogram
<b>👨‍💻 Owner :</b> @{owner}"""

PREMIUM_TXT = """<b>💎 PREMIUM MEMBERSHIP</b>

<b>Price :</b> {price}

<b>What you get</b>
✔️ Direct files — <b>no shortlink, no verification</b>
✔️ Unlimited downloads
✔️ Faster search & priority support
✔️ No ads, no waiting

<b>Free users</b> get <b>{trial} free clicks</b>, after that a shortlink
verification is needed every {hours} hours.

To buy, contact <b>@{owner}</b> and send the payment proof.
Your ID : <code>{user_id}</code>"""
