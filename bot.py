import sys
import glob
import asyncio
import logging
import logging.config
from pathlib import Path

from aiohttp import web
from pyrogram import Client, idle, __version__ as pyro_version

from info import (API_ID, API_HASH, BOT_TOKEN, SESSION, WORKERS, PORT,
                  LOG_CHANNEL, DATABASE_URI, ADMINS)
from database.ia_filterdb import ensure_indexes, total_files
from database.users_chats_db import db
from utils import temp

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)
log = logging.getLogger("AutoFilterBot")

PLUGINS = dict(root="plugins")


class Bot(Client):
    def __init__(self):
        super().__init__(
            name=SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=WORKERS,
            plugins=PLUGINS,
            sleep_threshold=10,
            max_concurrent_transmissions=10,
        )

    async def start(self):
        await super().start()
        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        temp.B_LINK = f"https://t.me/{me.username}"
        self.username = me.username

        await ensure_indexes()
        files = await total_files()
        users = await db.total_users()
        log.info(f"✅ {me.first_name} started | @{me.username} | Pyrogram v{pyro_version}")
        log.info(f"📁 Files: {files} | 👤 Users: {users}")

        # background jobs
        asyncio.create_task(premium_expiry_worker(self))

        if LOG_CHANNEL:
            try:
                await self.send_message(
                    LOG_CHANNEL,
                    f"<b>✅ Bot Restarted</b>\n\n<b>Files:</b> {files}\n<b>Users:</b> {users}")
            except Exception as e:
                log.warning(f"LOG_CHANNEL not reachable: {e}")

    async def stop(self, *args):
        await super().stop()
        log.info("🛑 Bot stopped.")


async def premium_expiry_worker(client: Client):
    """Every 10 min: notify + downgrade users whose premium ended."""
    from utils import send_log
    while True:
        try:
            cursor = await db.expired_premium()
            async for user in cursor:
                uid = user["id"]
                await db.remove_premium(uid)
                try:
                    await client.send_message(
                        uid,
                        "<b>⏳ Your Premium Membership has expired!</b>\n\n"
                        "You are back on the free plan (shortlink verification required).\n"
                        "Use /premium to renew and enjoy direct files again 💎")
                except Exception:
                    pass
                await send_log(client, f"#PREMIUM_EXPIRED\nUser: <code>{uid}</code>")
        except Exception as e:
            log.warning(f"expiry worker: {e}")
        await asyncio.sleep(600)


async def web_server():
    async def health(request):
        return web.json_response({"status": "running", "bot": temp.B_NAME})
    app = web.Application()
    app.router.add_get("/", health)
    return app


def preflight():
    missing = [k for k, v in {
        "API_ID": API_ID, "API_HASH": API_HASH, "BOT_TOKEN": BOT_TOKEN,
        "DATABASE_URI": DATABASE_URI,
    }.items() if not v]
    if missing:
        log.error(f"❌ Missing required config: {', '.join(missing)}. Fill your .env file.")
        sys.exit(1)
    if not ADMINS:
        log.warning("⚠️  ADMINS is empty — admin commands will not work.")


async def main():
    preflight()
    app = Bot()
    await app.start()
    runner = web.AppRunner(await web_server())
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info(f"🌐 Health server on port {PORT}")
    await idle()
    await app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bye 👋")
