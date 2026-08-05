import re
import base64
import logging
from struct import pack
from typing import List, Tuple

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import TEXT, ASCENDING
from pymongo.errors import DuplicateKeyError

from info import DATABASE_URI, DATABASE_NAME, COLLECTION_NAME, USE_CAPTION_FILTER, MAX_BTN

logger = logging.getLogger(__name__)

client = AsyncIOMotorClient(DATABASE_URI, maxPoolSize=100, minPoolSize=5)
db = client[DATABASE_NAME]
col = db[COLLECTION_NAME]


async def ensure_indexes():
    """Create indexes once at startup (huge speed boost on big databases)."""
    try:
        await col.create_index([("file_name", TEXT), ("caption", TEXT)],
                               name="search_index", default_language="english")
    except Exception as e:
        logger.warning(f"text index: {e}")
    try:
        await col.create_index([("file_name", ASCENDING)])
    except Exception as e:
        logger.warning(f"name index: {e}")


def clean_name(name: str) -> str:
    name = re.sub(r"[_\-\.\+]", " ", str(name or ""))
    name = re.sub(r"@\w+|www\.\w+\.\w+|https?://\S+", "", name)
    return re.sub(r"\s+", " ", name).strip()


async def save_file(media) -> Tuple[bool, int]:
    """Save a media document. Returns (saved, code) code: 1 saved, 0 dup, 2 error."""
    file_name = clean_name(getattr(media, "file_name", None) or "")
    caption = clean_name(getattr(media, "caption", "") or "")
    if not file_name:
        file_name = caption[:60] or "Unknown"
    doc = {
        "_id": media.file_unique_id,
        "file_id": media.file_id,
        "file_name": file_name,
        "file_size": getattr(media, "file_size", 0) or 0,
        "file_type": getattr(media, "file_type", "document"),
        "mime_type": getattr(media, "mime_type", ""),
        "caption": caption,
    }
    try:
        await col.insert_one(doc)
        return True, 1
    except DuplicateKeyError:
        return False, 0
    except Exception as e:
        logger.exception(e)
        return False, 2


def build_regex(query: str):
    query = query.strip()
    raw = re.sub(r"[\s_\-\.\+]+", " ", query)
    raw = re.escape(raw).replace(r"\ ", r"[\s\.\+\-_\(\)\[\]]*")
    return re.compile(raw, flags=re.IGNORECASE)


async def get_search_results(query: str, file_type: str = None, max_results: int = MAX_BTN,
                             offset: int = 0) -> Tuple[List[dict], int, int]:
    """Return (files, next_offset, total)."""
    query = (query or "").strip()
    if not query:
        return [], 0, 0
    regex = build_regex(query)
    if USE_CAPTION_FILTER:
        flt = {"$or": [{"file_name": regex}, {"caption": regex}]}
    else:
        flt = {"file_name": regex}
    if file_type:
        flt["file_type"] = file_type

    total = await col.count_documents(flt)
    cursor = col.find(flt).sort("$natural", -1).skip(offset).limit(max_results)
    files = await cursor.to_list(length=max_results)

    next_offset = offset + max_results
    if next_offset >= total:
        next_offset = 0
    return files, next_offset, total


async def get_file_details(file_unique_id: str):
    return await col.find_one({"_id": file_unique_id})


async def delete_files(query: str) -> int:
    regex = build_regex(query)
    res = await col.delete_many({"$or": [{"file_name": regex}, {"caption": regex}]})
    return res.deleted_count


async def total_files() -> int:
    return await col.count_documents({})


async def db_size() -> int:
    stats = await db.command("dbstats")
    return int(stats.get("dataSize", 0))


# ---- deep-link encoding helpers ----
def encode(string: str) -> str:
    return base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")


def decode(b64: str) -> str:
    b64 += "=" * (-len(b64) % 4)
    return base64.urlsafe_b64decode(b64).decode("ascii")


def unpack_new_file_id(new_file_id):
    """Not required for normal use, kept for compatibility."""
    return new_file_id
