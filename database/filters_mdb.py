from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME
from database.ia_filterdb import build_regex

_client = AsyncIOMotorClient(DATABASE_URI)
_db = _client[DATABASE_NAME]
mfilters = _db["manual_filters"]


async def add_filter(chat_id, text, reply_text, btn=None, file_ref=None, file_type=None):
    """Store / update a manual filter. chat_id 0 = global filter."""
    await mfilters.update_one(
        {"chat_id": int(chat_id), "text": text.lower().strip()},
        {"$set": {
            "reply": reply_text,
            "btn": btn or "[]",
            "file": file_ref,
            "file_type": file_type,
        }},
        upsert=True,
    )


async def find_filter(chat_id, query):
    """Exact-ish match first, then a regex match."""
    q = query.lower().strip()
    for cid in (int(chat_id), 0):
        doc = await mfilters.find_one({"chat_id": cid, "text": q})
        if doc:
            return doc
    regex = build_regex(q)
    for cid in (int(chat_id), 0):
        doc = await mfilters.find_one({"chat_id": cid, "text": regex})
        if doc:
            return doc
    return None


async def get_filters(chat_id):
    return await mfilters.find({"chat_id": int(chat_id)}).to_list(length=1000)


async def delete_filter(chat_id, text):
    res = await mfilters.delete_one({"chat_id": int(chat_id), "text": text.lower().strip()})
    return res.deleted_count


async def del_all(chat_id):
    await mfilters.delete_many({"chat_id": int(chat_id)})


async def count_filters():
    return await mfilters.count_documents({})
