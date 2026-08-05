import datetime
import logging
from motor.motor_asyncio import AsyncIOMotorClient

from info import DATABASE_URI, DATABASE_NAME, FREE_TRIAL_CLICKS, VERIFY_HOURS

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self._client = AsyncIOMotorClient(DATABASE_URI, maxPoolSize=100, minPoolSize=5)
        self.db = self._client[DATABASE_NAME]
        self.users = self.db["users"]
        self.groups = self.db["groups"]

    # ---------------- users ----------------
    def new_user(self, user_id, name):
        return {
            "id": int(user_id),
            "name": name,
            "ban": False,
            "joined": datetime.datetime.utcnow(),
            "trial_left": FREE_TRIAL_CLICKS,
            "premium_until": None,
            "verified_until": None,
            "verify_token": None,
            "downloads": 0,
        }

    async def add_user(self, user_id, name):
        if not await self.users.find_one({"id": int(user_id)}):
            await self.users.insert_one(self.new_user(user_id, name))
            return True
        return False

    async def get_user(self, user_id):
        return await self.users.find_one({"id": int(user_id)})

    async def total_users(self):
        return await self.users.count_documents({})

    async def all_users(self):
        return self.users.find({})

    async def ban_user(self, user_id, ban=True):
        await self.users.update_one({"id": int(user_id)}, {"$set": {"ban": ban}}, upsert=True)

    async def is_banned(self, user_id):
        u = await self.get_user(user_id)
        return bool(u and u.get("ban"))

    # ---------------- groups ----------------
    async def add_chat(self, chat_id, title):
        if not await self.groups.find_one({"id": int(chat_id)}):
            await self.groups.insert_one({"id": int(chat_id), "title": title,
                                          "joined": datetime.datetime.utcnow()})

    async def total_chats(self):
        return await self.groups.count_documents({})

    async def all_chats(self):
        return self.groups.find({})

    # ---------------- premium ----------------
    async def add_premium(self, user_id, days: int):
        user = await self.get_user(user_id)
        now = datetime.datetime.utcnow()
        base = now
        if user and user.get("premium_until") and user["premium_until"] > now:
            base = user["premium_until"]
        until = base + datetime.timedelta(days=days)
        await self.users.update_one({"id": int(user_id)},
                                    {"$set": {"premium_until": until}}, upsert=True)
        return until

    async def remove_premium(self, user_id):
        await self.users.update_one({"id": int(user_id)},
                                    {"$set": {"premium_until": None}})

    async def is_premium(self, user_id) -> bool:
        u = await self.get_user(user_id)
        if not u or not u.get("premium_until"):
            return False
        return u["premium_until"] > datetime.datetime.utcnow()

    async def premium_users(self):
        return self.users.find({"premium_until": {"$gt": datetime.datetime.utcnow()}})

    async def expired_premium(self):
        """Users whose premium just ended (field still set but in the past)."""
        return self.users.find({"premium_until": {"$ne": None,
                                                  "$lte": datetime.datetime.utcnow()}})

    # ---------------- trial / verification ----------------
    async def trial_left(self, user_id) -> int:
        u = await self.get_user(user_id)
        return int(u.get("trial_left", 0)) if u else 0

    async def use_trial(self, user_id):
        await self.users.update_one({"id": int(user_id)}, {"$inc": {"trial_left": -1}})

    async def set_verify_token(self, user_id, token):
        await self.users.update_one({"id": int(user_id)},
                                    {"$set": {"verify_token": token}}, upsert=True)

    async def get_verify_token(self, user_id):
        u = await self.get_user(user_id)
        return u.get("verify_token") if u else None

    async def mark_verified(self, user_id):
        until = datetime.datetime.utcnow() + datetime.timedelta(hours=VERIFY_HOURS)
        await self.users.update_one({"id": int(user_id)},
                                    {"$set": {"verified_until": until, "verify_token": None}},
                                    upsert=True)
        return until

    async def is_verified(self, user_id) -> bool:
        u = await self.get_user(user_id)
        if not u or not u.get("verified_until"):
            return False
        return u["verified_until"] > datetime.datetime.utcnow()

    async def count_download(self, user_id):
        await self.users.update_one({"id": int(user_id)}, {"$inc": {"downloads": 1}})


db = Database()
