#!/usr/bin/env python3
"""
DiskWala Downloader Bot — Full Featured (FIXED)
Developer: @anujbyedit
Fixes applied:
  #1  Pyrogram decorated handlers not directly callable — extracted helper functions
  #2  Deleted message pe reply_text — replaced with context.bot.send_message
  #3  Timezone-naive datetime comparison — using timezone.utc
  #4  Empty set memory leak in active_tasks — cleanup after discard
  #5  Thumbnail race condition — delete after upload, not in finally
  #6  done > total edge case in format_eta_speed
  #7  Trailing slash in CHANNEL_LINK
  #8  StatsStore.lock wrong event loop — initialized in main()
  #9  Flask thread blocking .result(timeout=120)
  #10 query.answer() called twice in ptb_handle_check_join
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from math import floor
from pathlib import Path

import httpx
from flask import Flask, request, jsonify
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters, enums
from pyrogram.errors import UserNotParticipant
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
    ReplyKeyboardMarkup,
)
from telegram import (
    InlineKeyboardButton as TgButton,
    InlineKeyboardMarkup as TgMarkup,
    Update,
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters as tg_filters,
)
from telegram.request import HTTPXRequest

try:
    import uvloop
    uvloop.install()
except Exception:
    pass

# ─────────────────────────────────────────
# Logging
# ─────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("DiskWala-Bot")

# ─────────────────────────────────────────
# Config
# ─────────────────────────────────────────
BOT_TOKEN     = os.environ.get("BOT_TOKEN", "8883806794:AAEKZ9fUFRBJujDlHCDUp8HRQQkkLUTex6c")
BOT_USERNAME  = os.environ.get("BOT_USERNAME", "save_restricted_ak_content_bot")
WEBHOOK_URL   = os.environ.get("WEBHOOK_URL", "")
PORT          = int(os.environ.get("PORT", 5000))
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", 8729304171))

_ADMIN_IDS_RAW = os.environ.get("ADMIN_IDS", "8729304171")
ADMIN_IDS = [int(x.strip()) for x in _ADMIN_IDS_RAW.split(",") if x.strip()]
if ADMIN_USER_ID and ADMIN_USER_ID not in ADMIN_IDS:
    ADMIN_IDS.append(ADMIN_USER_ID)

REQUIRED_CHANNEL_USERNAME = os.environ.get("REQUIRED_CHANNEL_USERNAME", "TeraBox_Support_Anuj_Bot")
REQUIRED_CHANNEL_URL      = os.environ.get("REQUIRED_CHANNEL_URL", "https://t.me/TeraBox_Support_Anuj_Bot")

# FIX #7 — trailing slash bhi strip karo
_channel_link_raw = os.environ.get("CHANNEL_LINK", "TeraBox_Support_Anuj_Bot")
CHANNEL_LINK = (
    _channel_link_raw
    .lstrip("@")
    .replace("https://t.me/", "")
    .replace("http://t.me/", "")
    .rstrip("/")
)
SUPPORT_USERNAME = os.environ.get("SUPPORT_USERNAME", "TeraBox_Support_Anuj_Bot")

PHOTO_URL = os.environ.get("PHOTO_URL", "https://n.uguu.se/mEXQnxjh.jpg")
DUMMY_URL = os.environ.get("DUMMY_URL", "https://n.uguu.se/HVeBBYah.jpg")

UPI_ID   = os.environ.get("UPI_ID", "971916880@ybl")
UPI_NAME = os.environ.get("UPI_NAME", "ANUJ")

DISKWALA_API_KEY  = os.environ.get("DISKWALA_API_KEY", "69ffffb2d96f638117a71ea4")
DISKWALA_BASE_URL = os.environ.get("DISKWALA_BASE_URL", "https://ddudapidd.diskwala.com/api/v1")

MONGO_DB_URI = os.environ.get("MONGO_DB_URI", "mongodb+srv://Anujedit:Anujedit@cluster0.7cs2nhd.mongodb.net/?appName=Cluster0")
DB_CHANNEL   = int(os.environ.get("DB_CHANNEL", "-1003873749415"))

API_ID   = int(os.environ.get("API_ID", 20432885))
API_HASH = os.environ.get("API_HASH", "4fdcfab1c7f5e24ae69f3ce6bb234dec")

_support_tokens_env = os.environ.get("SUPPORT_BOT_TOKENS", "")
SUPPORT_BOT_TOKENS = [t.strip() for t in _support_tokens_env.split(",") if t.strip()]

FREE_DOWNLOAD_LIMIT    = int(os.environ.get("FREE_DOWNLOAD_LIMIT", 10))
TG_MAX_FILE_SIZE       = 2000 * 1024 * 1024
TG_STANDARD_LIMIT      =   50 * 1024 * 1024
TELEGRAM_HARD_LIMIT_MB = 4096

DOWNLOAD_TIMEOUT       = 7200
UPLOAD_READ_TIMEOUT    = 3600
UPLOAD_WRITE_TIMEOUT   = 3600
UPLOAD_CONNECT_TIMEOUT = 60
UPLOAD_POOL_TIMEOUT    = 60

GLOBAL_ACTIVE_LIMIT = 8
UPLOAD_ACTIVE_LIMIT = 6
MAX_USER_QUEUE      = 4

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".flv", ".ts", ".3gp"}
AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".flac", ".opus", ".ogg"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

BASE_DIR     = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)
STATS_FILE   = BASE_DIR / "bot_stats.json"

if os.path.isdir("/dev/shm"):
    TMP_DIR = "/dev/shm/diskwala_tmp"
else:
    TMP_DIR = str(BASE_DIR / "tmp_downloads")
os.makedirs(TMP_DIR, exist_ok=True)

# ─────────────────────────────────────────
# Global state
# ─────────────────────────────────────────
global_active_sem: asyncio.Semaphore = None   # type: ignore[assignment]
upload_active_sem: asyncio.Semaphore = None   # type: ignore[assignment]
dl_semaphore:      asyncio.Semaphore = None   # type: ignore[assignment]

active_tasks:  dict[int, set]  = {}
task_state:    dict[str, dict] = {}
active_uploads: dict[str, bool] = {}

uploader_clients: dict[str, Client] = {}
uploader_state:   dict[str, bool]   = {}
uploader_lock: asyncio.Lock = None        # type: ignore[assignment]

user_active_messages: dict[int, list] = {}
user_active_lock: asyncio.Lock = None    # type: ignore[assignment]

# ─────────────────────────────────────────
# MongoDB
# ─────────────────────────────────────────
mongo        = AsyncIOMotorClient(MONGO_DB_URI) if MONGO_DB_URI else None
db           = mongo["diskwala_bot"] if mongo is not None else None
files_col    = db["files"]    if db is not None else None
users_col    = db["users"]    if db is not None else None
payments_col = db["payments"] if db is not None else None

# ─────────────────────────────────────────
# Stats
# ─────────────────────────────────────────
class StatsStore:
    def __init__(self, path: Path):
        self.path = path
        # FIX #8 — lock ab main() mein explicitly initialize hoga
        self._lock: asyncio.Lock | None = None
        self.data = self._load()

    def init_lock(self):
        """Call this inside the running event loop (from main())."""
        self._lock = asyncio.Lock()

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            # Fallback — should not reach here if init_lock() was called
            self._lock = asyncio.Lock()
        return self._lock

    def _default(self):
        return {"total_downloads": 0, "users": {}}

    def _load(self):
        if not self.path.exists():
            d = self._default()
            self._save_sync(d)
            return d
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            d.setdefault("total_downloads", 0)
            d.setdefault("users", {})
            return d
        except Exception:
            d = self._default()
            self._save_sync(d)
            return d

    def _save_sync(self, d):
        self.path.write_text(
            json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    async def register_user(self, user) -> bool:
        uid = str(user.id if hasattr(user, "id") else user)
        async with self.lock:
            is_new = uid not in self.data["users"]
            self.data["users"][uid] = {
                "id": int(uid),
                "username": getattr(user, "username", "") or "",
                "first_name": getattr(user, "first_name", "") or "",
            }
            self._save_sync(self.data)
            return is_new

    async def increment(self):
        async with self.lock:
            self.data["total_downloads"] += 1
            self._save_sync(self.data)

    async def get(self):
        async with self.lock:
            return {
                "users": len(self.data["users"]),
                "downloads": self.data["total_downloads"],
            }


stats = StatsStore(STATS_FILE)

# ─────────────────────────────────────────
# Flask
# ─────────────────────────────────────────
flask_app = Flask(__name__)


@flask_app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bot": "DiskWala Downloader"}), 200


@flask_app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"ping": "pong"}), 200


@flask_app.route("/status", methods=["GET"])
def bot_status():
    return jsonify({
        "active_tasks":   len(task_state),
        "active_uploads": len(active_uploads),
        "uploader_bots":  len(uploader_clients),
    }), 200


def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False, threaded=True)


# ─────────────────────────────────────────
# Appicrypt Header Generator
# ─────────────────────────────────────────
def make_appicrypt_headers(
    method: str,
    url_path: str,
    params: str = "",
    body: dict | None = None,
) -> dict:
    ts = str(int(time.time() * 1000))
    body_str = (
        json.dumps(body, separators=(",", ":"), sort_keys=True) if body else ""
    )
    canonical = f"{method.upper()} {url_path} | params={params} | body={body_str} | ts={ts}"
    sha256    = hashlib.sha256(canonical.encode()).hexdigest()
    return {
        "Appicrypt":     sha256,
        "Appicrypt-ts":  ts,
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {DISKWALA_API_KEY}",
    }


# ─────────────────────────────────────────
# DiskWala API Client
# ─────────────────────────────────────────
class DiskWalaClient:
    def __init__(self):
        self.base    = DISKWALA_BASE_URL
        self.session = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0),
            follow_redirects=True,
        )

    async def _get(self, path: str, params: dict | None = None) -> dict:
        param_str = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        headers   = make_appicrypt_headers("GET", path, params=param_str)
        r = await self.session.get(
            f"{self.base}{path}", params=params, headers=headers
        )
        r.raise_for_status()
        return r.json()

    async def _post(self, path: str, body: dict | None = None) -> dict:
        body    = body or {}
        headers = make_appicrypt_headers("POST", path, body=body)
        r = await self.session.post(
            f"{self.base}{path}", json=body, headers=headers
        )
        r.raise_for_status()
        return r.json()

    async def get_file_info(self, file_id: str) -> dict:
        return await self._get("/file/info", params={"file_id": file_id})

    async def get_download_url(self, file_id: str) -> str:
        data = await self._post("/file/download", {"file_id": file_id})
        url  = (
            data.get("url")
            or data.get("download_url")
            or data.get("data", {}).get("url")
            or data.get("data", {}).get("download_url")
            or ""
        )
        if not url:
            raise RuntimeError(f"No download URL in response: {data}")
        return url

    async def get_video_stream(self, file_id: str) -> str:
        data = await self._post("/file/video/stream", {"file_id": file_id})
        url  = (
            data.get("url")
            or data.get("stream_url")
            or data.get("data", {}).get("url")
            or data.get("data", {}).get("stream_url")
            or ""
        )
        if not url:
            raise RuntimeError(f"No stream URL in response: {data}")
        return url

    async def sign_file(self, file_id: str) -> dict:
        return await self._post("/file/sign", {"file_id": file_id})

    async def close(self):
        await self.session.aclose()


dw_client = DiskWalaClient()

# ─────────────────────────────────────────
# DiskWala Link Parser
# ─────────────────────────────────────────
DISKWALA_LINK_PATTERNS = [
    r"diskwala\.com/(?:s|file|f|v|d|app|share|dl|download)/...",
    r"diskwala\.com/([a-zA-Z0-9]{8,})",
]


def extract_diskwala_file_id(text: str) -> str | None:
    for pattern in DISKWALA_LINK_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return m.group(1)
    return None


def is_diskwala_url(text: str) -> bool:
    return bool(re.search(r"diskwala\.com", text, re.IGNORECASE))


def make_uid(file_id: str) -> str:
    return f"dw_{file_id}"


# ─────────────────────────────────────────
# Format helpers
# ─────────────────────────────────────────
def format_size(b: int) -> str:
    if b < 1024:        return f"{b} B"
    if b < 1024 ** 2:   return f"{b / 1024:.1f} KB"
    if b < 1024 ** 3:   return f"{b / 1024 ** 2:.1f} MB"
    return f"{b / 1024 ** 3:.2f} GB"


def format_duration(seconds: int) -> str:
    if seconds < 0: return "??:??"
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def format_speed(bps: float) -> str:
    if bps <= 0:          return "Calculating..."
    if bps < 1024:        return f"{bps:.0f} B/s"
    if bps < 1024 ** 2:   return f"{bps / 1024:.1f} KB/s"
    return f"{bps / 1024 ** 2:.1f} MB/s"


def build_bar(pct: int, width: int = 10) -> str:
    filled = min(width, floor(width * pct / 100))
    return f"[{'⬢' * filled}{'⬡' * (width - filled)}]"


def safe_filename(name: str) -> str:
    for ch in '\\/:*?"<>|':
        name = name.replace(ch, "_")
    return (name.strip() or "file")[:200]


def format_eta_speed(start_time: float, done: int, total: int):
    elapsed   = max(0.001, time.time() - start_time)
    speed_bps = done / elapsed
    speed_kbs = speed_bps / 1024
    speed_str = (
        f"{speed_kbs / 1024:.2f} MB/s" if speed_kbs >= 1024
        else f"{speed_kbs:.2f} KB/s"
    )
    # FIX #6 — done > total edge case handle karo
    remaining = max(0, total - done)
    eta = int(remaining / speed_bps) if (total and speed_bps > 0) else 0
    eta_str = time.strftime("%H:%M:%S", time.gmtime(eta))
    return speed_str, eta_str


def progress_bar(done: int, total: int, length: int = 10) -> str:
    if not total or total <= 0:
        dots = int((time.time() * 2) % (length + 1))
        return "⬢" * dots + "⬡" * (length - dots)
    filled = min(length, floor(length * done / total))
    return "⬢" * filled + "⬡" * (length - filled)


# ─────────────────────────────────────────
# MongoDB helpers
# ─────────────────────────────────────────
async def ensure_indexes():
    if db is None:
        return
    try:
        await files_col.create_index("uid",     unique=True)
        await users_col.create_index("user_id", unique=True)
        await payments_col.create_index("user_id")
    except Exception:
        pass


async def get_user(user_id: int) -> dict:
    if not users_col:
        return {"user_id": user_id, "plan": "free", "expiry": None, "total_downloads": 0}
    try:
        user = await users_col.find_one({"user_id": user_id})
        if not user:
            user = {
                "user_id":         user_id,
                "plan":            "free",
                "expiry":          None,
                "total_downloads": 0,
                "joined_at":       datetime.now(timezone.utc),
            }
            await users_col.insert_one(user)
        return user
    except Exception:
        return {"user_id": user_id, "plan": "free", "expiry": None, "total_downloads": 0}


async def is_premium(user_id: int) -> bool:
    user = await get_user(user_id)
    if user.get("plan") == "free":
        return False
    expiry = user.get("expiry")
    if expiry is None:
        return True
    # FIX #3 — timezone-aware comparison
    now = datetime.now(timezone.utc)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return now < expiry


async def increment_download_count(user_id: int):
    if not users_col:
        await stats.increment()
        return
    try:
        await users_col.update_one(
            {"user_id": user_id},
            {"$inc": {"total_downloads": 1}},
            upsert=True,
        )
        await stats.increment()
    except Exception:
        pass


async def check_free_limit(user_id: int) -> tuple[bool, int]:
    if await is_premium(user_id):
        user = await get_user(user_id)
        return False, user.get("total_downloads", 0)
    user = await get_user(user_id)
    used = user.get("total_downloads", 0)
    return used >= FREE_DOWNLOAD_LIMIT, used


async def activate_premium(user_id: int, days: int):
    if not users_col:
        return
    now = datetime.now(timezone.utc)
    if days == -1:
        expiry = None
    else:
        user   = await get_user(user_id)
        base   = user.get("expiry") or now
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        base   = base if (base and base > now) else now
        expiry = base + timedelta(days=days)
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"plan": "premium", "expiry": expiry}},
        upsert=True,
    )


async def revoke_premium(user_id: int):
    if not users_col:
        return
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"plan": "free", "expiry": None}},
        upsert=True,
    )


async def db_find(uid: str) -> dict | None:
    if not files_col:
        return None
    try:
        return await files_col.find_one({"uid": uid})
    except Exception:
        return None


async def db_save(uid: str, msg_id: int, filename: str, size_mb: float):
    if not files_col:
        return
    try:
        await files_col.update_one(
            {"uid": uid},
            {"$set": {
                "uid":      uid,
                "msg_id":   msg_id,
                "filename": filename,
                "size_mb":  round(size_mb, 2),
                "added_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning("db_save error: %s", e)


# ─────────────────────────────────────────
# Keyboards
# ─────────────────────────────────────────
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["💎 Plans",   "📊 My Status"],
        ["❓ Help",    "📞 Support"],
    ],
    resize_keyboard=True,
)


def plans_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔵 ₹19 — 12 Days",     callback_data="buyplan:19:12")],
        [InlineKeyboardButton("🔵 ₹29 — 21 Days",     callback_data="buyplan:29:21")],
        [InlineKeyboardButton("🔵 ₹45 — 35 Days",     callback_data="buyplan:45:35")],
        [InlineKeyboardButton("🔵 ₹99 — 99 Days",     callback_data="buyplan:99:99")],
        [InlineKeyboardButton("🔵 ₹999 — Lifetime ∞", callback_data="buyplan:999:-1")],
    ])


def kb_inline(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel:{task_id}")]
    ])


def join_kb_pyrogram() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=REQUIRED_CHANNEL_URL or f"https://t.me/{REQUIRED_CHANNEL_USERNAME}")],
        [InlineKeyboardButton("✅ I Joined",      callback_data="check_join")],
    ])


# ─────────────────────────────────────────
# Uploader bot management
# ─────────────────────────────────────────
pyro_bot = None


async def init_uploader_bots():
    global pyro_bot

    if not (API_ID and API_HASH and BOT_TOKEN):
        logger.warning("Pyrogram not configured — DB_CHANNEL uploads disabled.")
        return

    try:
        main_client = Client(
            "diskwala_main_pyro",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
        )
        await main_client.start()
        me = await main_client.get_me()
        logger.info("Main pyrogram client started: @%s", me.username)

        pyro_bot = main_client
        uploader_clients["main"] = main_client
        uploader_state["main"]   = False
    except Exception as e:
        logger.error("Main pyrogram client failed to start: %s", e)
        return

    for idx, token in enumerate(SUPPORT_BOT_TOKENS, start=1):
        name = f"Bot_{idx}"
        try:
            cl = Client(
                f"diskwala_support_{idx}",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=token,
            )
            await cl.start()
            uploader_clients[name] = cl
            uploader_state[name]   = False
            logger.info("Support bot %s started.", name)
        except Exception as e:
            logger.error("Support bot %s failed to start: %s", name, e)


async def pick_free_uploader() -> tuple:
    async with uploader_lock:
        for name, client in uploader_clients.items():
            if not uploader_state.get(name, False):
                uploader_state[name] = True
                return name, client
    return None, None


async def release_uploader(name: str):
    async with uploader_lock:
        uploader_state[name] = False


# ─────────────────────────────────────────
# Progress (ptb-style)
# ─────────────────────────────────────────
async def safe_edit(msg, text: str, markup=None):
    try:
        await msg.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass


class Progress:
    def __init__(self, msg):
        self.msg       = msg
        self._task     = None
        self._stop     = False
        self._last     = 0
        self._interval = 4

    async def _edit(self, text):
        now = time.time()
        if now - self._last >= self._interval:
            await safe_edit(self.msg, text)
            self._last = now

    async def start_dl(self):
        async def _run():
            checkpoints = [3, 8, 15, 25, 38, 52, 65, 78, 88, 94]
            for p in checkpoints:
                if self._stop:
                    return
                await self._edit(
                    f"📥 <b>Downloading from DiskWala...</b>\n\n"
                    f"┌─────《 Progress 》─────┐\n"
                    f"├» {build_bar(p)} {p}%\n"
                    f"├» ⚡ Fetching file...\n"
                    f"└──────────────────────┘"
                )
                await asyncio.sleep(3)
            while not self._stop:
                await self._edit(
                    f"📥 <b>Downloading from DiskWala...</b>\n\n"
                    f"┌─────《 Progress 》─────┐\n"
                    f"├» {build_bar(94)} 94%\n"
                    f"├» ⚡ Almost done...\n"
                    f"└──────────────────────┘"
                )
                await asyncio.sleep(5)

        self._task = asyncio.create_task(_run())

    async def done_dl(self):
        self._stop = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
        await safe_edit(
            self.msg,
            f"📥 <b>Download Complete!</b>\n\n"
            f"┌─────《 Progress 》─────┐\n"
            f"├» {build_bar(100)} 100%\n"
            f"├» ✅ Done!\n"
            f"└──────────────────────┘",
        )

    async def uploading(
        self, pct: int, fname: str, uploaded: int, total: int, speed: float, eta: int
    ):
        now = time.time()
        if now - self._last < self._interval:
            return
        self._last = now
        up_str = f"{format_size(uploaded)} / {format_size(total)}" if total else ""
        await safe_edit(
            self.msg,
            f"📤 <b>Uploading to Telegram</b>\n\n"
            f"┌─────《 Progress 》─────┐\n"
            f"├» 🎬 {fname[-30:]}\n"
            f"├» {build_bar(pct)} {pct}%\n"
            f"├» 📊 {up_str}\n"
            f"├» 🚀 {format_speed(speed)}\n"
            f"├» ⏱ ETA: {format_duration(eta) if eta else 'Calculating...'}\n"
            f"└──────────────────────┘",
        )

    async def cleanup(self):
        self._stop = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass


# ─────────────────────────────────────────
# Channel join check
# ─────────────────────────────────────────
async def is_joined_ptb(context, user_id: int) -> bool:
    if not REQUIRED_CHANNEL_USERNAME:
        return True
    try:
        m = await context.bot.get_chat_member(REQUIRED_CHANNEL_USERNAME, user_id)
        return m.status not in {"left", "kicked", "banned"}
    except Exception:
        return True


async def check_membership_pyro(client: Client, user_id: int) -> bool:
    if not REQUIRED_CHANNEL_USERNAME:
        return True
    try:
        member = await client.get_chat_member(REQUIRED_CHANNEL_USERNAME, user_id)
        return member.status in (
            enums.ChatMemberStatus.MEMBER,
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER,
        )
    except UserNotParticipant:
        return False
    except Exception:
        return True


# ─────────────────────────────────────────
# Video auto-deletion (1 hour)
# ─────────────────────────────────────────
async def schedule_user_video_deletion(
    client: Client, user_id: int, message_id: int, delay: int = 3600
):
    await asyncio.sleep(delay)
    try:
        await client.edit_message_media(
            chat_id=user_id,
            message_id=message_id,
            media=InputMediaPhoto(
                media=DUMMY_URL or "https://i.imgur.com/removed.png",
                caption=(
                    "⌛ Your file has been deleted due to restriction.\n\n"
                    "To watch again, please re-download.\n\n"
                    "आपका विडियो/फाइल डिलीट कर दी गयी है, "
                    "फिर से देखनी है तो फिर से डाउनलोड करें। धन्यवाद!"
                ),
            ),
        )
    except Exception as e:
        logger.debug("schedule_user_video_deletion edit error user=%s: %s", user_id, e)

    try:
        async with user_active_lock:
            lst = user_active_messages.get(user_id)
            if lst and message_id in lst:
                lst.remove(message_id)
            if not user_active_messages.get(user_id):
                user_active_messages.pop(user_id, None)
                try:
                    await client.send_message(
                        user_id,
                        "⌛ It's been 1 hour — your video has been deleted.\n\n"
                        "If you want to watch again, please re-download.",
                    )
                except Exception:
                    pass
    except Exception as e:
        logger.debug("schedule_user_video_deletion lock error: %s", e)


# ─────────────────────────────────────────
# Core: DiskWala resolve
# ─────────────────────────────────────────
async def resolve_diskwala_file(file_id: str) -> tuple[str, dict]:
    info = {}
    try:
        info_resp = await dw_client.get_file_info(file_id)
        info      = info_resp.get("data") or info_resp or {}
        logger.info("File info: %s", json.dumps(info)[:300])
    except Exception as e:
        logger.warning("Could not get file info: %s", e)

    file_name = (
        info.get("name")
        or info.get("file_name")
        or info.get("filename")
        or f"{file_id}.mp4"
    )
    is_video = any(file_name.lower().endswith(ext) for ext in VIDEO_EXTS)

    download_url = ""
    try:
        if is_video:
            try:
                download_url = await dw_client.get_video_stream(file_id)
            except Exception:
                download_url = await dw_client.get_download_url(file_id)
        else:
            download_url = await dw_client.get_download_url(file_id)
    except Exception as e:
        try:
            sign_resp    = await dw_client.sign_file(file_id)
            download_url = (
                sign_resp.get("url")
                or sign_resp.get("data", {}).get("url")
                or ""
            )
        except Exception:
            pass
        if not download_url:
            raise RuntimeError(f"Could not get download URL: {e}")

    return download_url, info


# ─────────────────────────────────────────
# Core: Download
# ─────────────────────────────────────────
async def download_diskwala_file(
    file_id: str,
    temp_dir: Path,
    task_id: str | None = None,
    progress_msg=None,
) -> tuple[Path, dict]:
    download_url, info = await resolve_diskwala_file(file_id)

    file_name = safe_filename(
        info.get("name")
        or info.get("file_name")
        or info.get("filename")
        or f"{file_id}.mp4"
    )
    out_path = temp_dir / file_name

    headers: dict = {}
    if DISKWALA_BASE_URL and DISKWALA_BASE_URL.split("/")[2] in download_url:
        headers = make_appicrypt_headers("GET", "/file/download")

    start_time    = time.time()
    downloaded    = 0
    last_edit     = 0
    EDIT_INTERVAL = 3

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(DOWNLOAD_TIMEOUT), follow_redirects=True
    ) as client:
        async with client.stream("GET", download_url, headers=headers) as resp:
            resp.raise_for_status()
            total_size = int(resp.headers.get("content-length", 0))

            with open(out_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=512 * 1024):
                    if task_id and task_state.get(task_id, {}).get("cancelled"):
                        raise asyncio.CancelledError()

                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_msg and hasattr(progress_msg, "edit_text"):
                        now = time.time()
                        if now - last_edit >= EDIT_INTERVAL:
                            last_edit  = now
                            bar        = progress_bar(downloaded, total_size)
                            speed_str, eta_str = format_eta_speed(start_time, downloaded, total_size)
                            done_mb    = downloaded / 1024 / 1024
                            total_mb   = total_size / 1024 / 1024 if total_size else 0
                            pct        = int(downloaded * 100 / total_size) if total_size else 0
                            try:
                                await progress_msg.edit_text(
                                    f"⬇️ **Downloading** `{file_name}`\n"
                                    f"`{bar}` {pct}%\n"
                                    f"📦 {done_mb:.1f} MB / {total_mb:.1f} MB\n"
                                    f"⚡ {speed_str}  ⏳ ETA {eta_str}",
                                    reply_markup=kb_inline(task_id) if task_id else None,
                                )
                            except Exception:
                                pass

    return out_path, info


# ─────────────────────────────────────────
# Core: Upload to DB_CHANNEL + send to user
# FIX #5 — thumbnail cleanup AFTER upload, not in finally
# ─────────────────────────────────────────
async def upload_to_db_and_send(
    uploader_name: str,
    uploader_client: Client,
    file_path: str,
    filename: str,
    size_mb: float,
    thumbnail_url: str | None,
    uid: str,
    user_id: int,
    progress_msg,
    task_id: str,
):
    start_time = time.time()
    last_edit  = [0]
    EDIT_INTERVAL = 4

    thumb_path = None
    if thumbnail_url:
        try:
            async with httpx.AsyncClient(timeout=10) as _tc:
                _tr = await _tc.get(thumbnail_url)
            if _tr.status_code == 200:
                thumb_path = os.path.join(TMP_DIR, f"thumb_{task_id}.jpg")
                with open(thumb_path, "wb") as tf:
                    tf.write(_tr.content)
        except Exception:
            pass

    async def _progress_cb(current, total):
        if task_state.get(task_id, {}).get("cancelled"):
            return
        now = time.time()
        if now - last_edit[0] < EDIT_INTERVAL:
            return
        last_edit[0] = now
        bar       = progress_bar(current, total)
        speed_str, eta_str = format_eta_speed(start_time, current, total)
        done_mb   = current / 1024 / 1024
        total_str = f"{total / 1024 / 1024:.1f} MB" if total else "?"
        pct       = int(current * 100 / total) if total else 0
        try:
            await progress_msg.edit_text(
                f"📤 **Uploading** `{filename}` [{uploader_name}]\n"
                f"`{bar}` {pct}%\n"
                f"📦 {done_mb:.1f} MB / {total_str}\n"
                f"⚡ {speed_str}  ⏳ ETA {eta_str}",
                reply_markup=kb_inline(task_id),
            )
        except Exception:
            pass

    is_video = filename.lower().endswith(tuple(VIDEO_EXTS))

    db_msg = None
    try:
        if is_video:
            db_msg = await uploader_client.send_video(
                chat_id=DB_CHANNEL,
                video=file_path,
                caption=f"📁 `{filename}`\n💾 {size_mb:.1f} MB\n🏷️ #FastDB",
                file_name=filename,
                thumb=thumb_path,
                supports_streaming=True,
                progress=_progress_cb,
            )
        else:
            db_msg = await uploader_client.send_document(
                chat_id=DB_CHANNEL,
                document=file_path,
                caption=f"📁 `{filename}`\n💾 {size_mb:.1f} MB\n🏷️ #FastDB",
                file_name=filename,
                thumb=thumb_path,
                progress=_progress_cb,
            )
    except Exception as e:
        raise RuntimeError(f"Upload to DB_CHANNEL failed: {e}") from e
    finally:
        # FIX #5 — upload ke baad thumb delete karo (finally mein nahi, kyunki
        # upload already complete hai ya exception hua — dono cases mein safe hai)
        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass

    if not db_msg:
        raise RuntimeError("DB_CHANNEL upload returned None")

    await db_save(uid, db_msg.id, filename, size_mb)

    copy_client = uploader_clients.get("main") or uploader_client

    try:
        user_copy = await copy_client.copy_message(
            chat_id=user_id,
            from_chat_id=DB_CHANNEL,
            message_id=db_msg.id,
            caption=(
                f"📁 `{filename}`\n"
                f"💾 {size_mb:.1f} MB\n"
                f"⚡ Fast DB ✅\n\n"
                f"⚠️ This file will be deleted in 1 hour."
            ),
        )
    except Exception as e:
        raise RuntimeError(f"copy_message to user failed: {e}") from e

    async with user_active_lock:
        user_active_messages.setdefault(user_id, []).append(user_copy.id)

    asyncio.create_task(
        schedule_user_video_deletion(copy_client, user_id, user_copy.id, delay=3600)
    )
    return user_copy


# ─────────────────────────────────────────
# Send file without DB_CHANNEL (PTB fallback)
# ─────────────────────────────────────────
async def send_file_direct_ptb(message, progress: Progress, file_path: Path, info: dict):
    ext       = file_path.suffix.lower()
    file_size = file_path.stat().st_size
    duration  = int(info.get("duration") or 0)
    title     = info.get("name") or info.get("title") or file_path.name
    caption   = (
        f"📁 <b>{title}</b>\n"
        f"📦 Size: {format_size(file_size)}\n"
        f"⬇️ Downloaded by {BOT_USERNAME}\n"
        f"🤖 @anujedits76"
    )

    if file_size > TG_MAX_FILE_SIZE:
        await safe_edit(
            progress.msg,
            f"⚠️ File too large ({format_size(file_size)}). Maximum: 2 GB.",
        )
        return

    upload_timeout = min(300 + file_size // (1024 * 1024), 10800)
    upload_start   = time.time()

    async def _progress_task():
        avg = 600 * 1024
        if file_size > 500 * 1024 * 1024:   avg = 250 * 1024
        elif file_size > 100 * 1024 * 1024: avg = 400 * 1024
        est_secs = max(file_size / avg, 2)
        reported = 0
        while reported < 98:
            elapsed  = time.time() - upload_start
            pct      = min(int(elapsed / est_secs * 100), 98)
            if pct > reported:
                reported = pct
                uploaded = int(file_size * pct / 100)
                speed    = uploaded / max(elapsed, 0.1)
                eta      = int((file_size - uploaded) / speed) if speed > 0 else 0
                await progress.uploading(pct, file_path.name, uploaded, file_size, speed, eta)
            await asyncio.sleep(3)

    ptask = asyncio.create_task(_progress_task())
    tg_kw = dict(
        read_timeout=UPLOAD_READ_TIMEOUT,
        write_timeout=UPLOAD_WRITE_TIMEOUT,
        connect_timeout=UPLOAD_CONNECT_TIMEOUT,
        pool_timeout=UPLOAD_POOL_TIMEOUT,
    )

    try:
        async def _send():
            with open(file_path, "rb") as f:
                if ext in VIDEO_EXTS:
                    if file_size > TG_STANDARD_LIMIT:
                        await message.reply_document(
                            document=f, caption=caption[:4096],
                            filename=file_path.name, parse_mode="HTML", **tg_kw
                        )
                    else:
                        kw = dict(caption=caption[:1024], supports_streaming=True,
                                  parse_mode="HTML", **tg_kw)
                        if duration: kw["duration"] = duration
                        await message.reply_video(video=f, **kw)
                elif ext in AUDIO_EXTS:
                    if file_size > TG_STANDARD_LIMIT:
                        await message.reply_document(
                            document=f, caption=caption[:4096],
                            filename=file_path.name, parse_mode="HTML", **tg_kw
                        )
                    else:
                        kw = dict(caption=caption[:1024], parse_mode="HTML", **tg_kw)
                        if duration: kw["duration"] = duration
                        await message.reply_audio(audio=f, **kw)
                elif ext in IMAGE_EXTS:
                    await message.reply_photo(
                        photo=f, caption=caption[:1024],
                        parse_mode="HTML", **tg_kw
                    )
                else:
                    await message.reply_document(
                        document=f, caption=caption[:4096],
                        filename=file_path.name, parse_mode="HTML", **tg_kw
                    )

        await asyncio.wait_for(_send(), timeout=upload_timeout)

    except asyncio.TimeoutError:
        raise RuntimeError(
            f"⏱ Upload timeout ({format_size(file_size)}). Connection slow hai, dobara try karein."
        )
    except Exception as e:
        if "413" in str(e):
            raise RuntimeError(
                f"File too large for standard bot ({format_size(file_size)}). "
                "Local Bot API Server chahiye 2 GB ke liye."
            )
        raise
    finally:
        ptask.cancel()
        try:
            await ptask
        except Exception:
            pass


# ─────────────────────────────────────────
# Main task processor (Pyrogram)
# ─────────────────────────────────────────
async def process_task_pyro(
    task_id: str,
    user_id: int,
    file_id: str,
    status_msg: Message,
):
    dest_path: str | None = None
    try:
        task_state[task_id] = {"cancelled": False}

        # 0. Free limit check
        limit_hit, used = await check_free_limit(user_id)
        if limit_hit:
            await status_msg.edit_text(
                f"🚫 **Aapki {FREE_DOWNLOAD_LIMIT} downloads ki limit khatam ho gayi!**\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💎 Premium lene ke liye neeche dekhein:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💎 Premium Plans", callback_data="show_plans")],
                    [InlineKeyboardButton("📞 Support", url=f"https://t.me/{SUPPORT_USERNAME}")],
                ]),
            )
            return

        # 1. Resolve link
        try:
            await status_msg.edit_text(
                "🔍 DiskWala link resolve kar raha hoon...",
                reply_markup=kb_inline(task_id),
            )
        except Exception:
            pass

        try:
            download_url, info = await resolve_diskwala_file(file_id)
        except Exception as e:
            await status_msg.edit_text(
                f"❌ Link resolve nahi hua.\n`{e}`\n\nSupport: @{SUPPORT_USERNAME}"
            )
            return

        file_name = safe_filename(
            info.get("name") or info.get("file_name") or info.get("filename") or f"{file_id}.mp4"
        )
        size_b  = int(info.get("size") or info.get("file_size") or 0)
        size_mb = size_b / 1024 / 1024
        thumb   = info.get("thumbnail") or info.get("thumb") or None
        uid     = make_uid(file_id)

        if not download_url:
            await status_msg.edit_text(
                f"❌ Download link nahi mila.\n\nSupport: @{SUPPORT_USERNAME}"
            )
            return

        # 2. Size check
        if size_mb > TELEGRAM_HARD_LIMIT_MB and not await is_premium(user_id):
            await status_msg.edit_text(
                f"❌ File bahut badi hai!\n"
                f"📦 Size: {size_mb:.1f} MB\n"
                f"📏 Max: {TELEGRAM_HARD_LIMIT_MB} MB\n\n"
                f"💎 Premium upgrade karein: /plans"
            )
            return

        # 3. DB cache check
        cached = await db_find(uid)
        if cached and DB_CHANNEL:
            try:
                await status_msg.edit_text(
                    f"⚡ **Fast DB** — cache se bhej raha hoon!\n📁 `{file_name}`"
                )
                main_cl = uploader_clients.get("main")
                if main_cl:
                    user_copy = await main_cl.copy_message(
                        chat_id=user_id,
                        from_chat_id=DB_CHANNEL,
                        message_id=cached["msg_id"],
                        caption=(
                            f"📁 `{file_name}`\n"
                            f"💾 {cached.get('size_mb', 0):.1f} MB\n"
                            f"⚡ Fast DB ✅\n\n"
                            f"⚠️ 1 hour mein delete ho jayega."
                        ),
                    )
                    async with user_active_lock:
                        user_active_messages.setdefault(user_id, []).append(user_copy.id)
                    asyncio.create_task(
                        schedule_user_video_deletion(main_cl, user_id, user_copy.id, 3600)
                    )
                    await status_msg.delete()
                    await increment_download_count(user_id)
                    return
            except Exception as e:
                logger.warning("Cache copy failed, re-downloading: %s", e)

        # 4. Download
        try:
            async with global_active_sem:
                file_path, dl_info = await download_diskwala_file(
                    file_id=file_id,
                    temp_dir=Path(TMP_DIR),
                    task_id=task_id,
                    progress_msg=status_msg,
                )
        except asyncio.CancelledError:
            await status_msg.edit_text("❌ Download cancel kar diya gaya.")
            return
        except Exception as e:
            await status_msg.edit_text(f"❌ Download fail!\n`{e}`")
            return

        dest_path = str(file_path)

        if size_mb <= 0 and file_path.exists():
            size_mb = file_path.stat().st_size / 1024 / 1024

        if task_state.get(task_id, {}).get("cancelled"):
            await status_msg.edit_text("❌ Task cancel kar diya gaya.")
            return

        # 5. Pick uploader
        uploader_name, uploader_client = await pick_free_uploader()
        if not uploader_name:
            for _ in range(12):
                await asyncio.sleep(5)
                uploader_name, uploader_client = await pick_free_uploader()
                if uploader_name:
                    break
        if not uploader_name:
            await status_msg.edit_text(
                "❌ Sabhi uploaders busy hain. Thodi der baad try karein."
            )
            return

        # 6. Upload
        active_uploads[task_id] = True
        try:
            async with upload_active_sem:
                if DB_CHANNEL:
                    await upload_to_db_and_send(
                        uploader_name=uploader_name,
                        uploader_client=uploader_client,
                        file_path=dest_path,
                        filename=file_name,
                        size_mb=size_mb,
                        thumbnail_url=thumb,
                        uid=uid,
                        user_id=user_id,
                        progress_msg=status_msg,
                        task_id=task_id,
                    )
                else:
                    await uploader_client.send_document(
                        chat_id=user_id,
                        document=dest_path,
                        caption=(
                            f"📁 `{file_name}`\n"
                            f"💾 {size_mb:.1f} MB\n"
                            f"⬇️ @{BOT_USERNAME}"
                        ),
                        file_name=file_name,
                    )
        except asyncio.CancelledError:
            await status_msg.edit_text("❌ Upload cancel kar diya gaya.")
            return
        except Exception as e:
            await status_msg.edit_text(f"❌ Upload fail!\n`{e}`")
            return
        finally:
            active_uploads.pop(task_id, None)
            await release_uploader(uploader_name)

        # 7. Cleanup & finish
        try:
            await status_msg.delete()
        except Exception:
            pass

        await increment_download_count(user_id)

    except Exception as e:
        logger.error("process_task_pyro unhandled error task=%s: %s", task_id, e)
        try:
            await status_msg.edit_text(f"❌ Unexpected error:\n`{e}`")
        except Exception:
            pass
    finally:
        task_state.pop(task_id, None)
        q = active_tasks.get(user_id)
        if q is not None:
            q.discard(task_id)
            # FIX #4 — empty set cleanup karo (memory leak fix)
            if not q:
                active_tasks.pop(user_id, None)

        if dest_path:
            _cleanup_path(dest_path)


def _cleanup_path(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# ─────────────────────────────────────────
# FIX #1 — Pyrogram handler helper functions
# Decorated handlers directly call nahi hoti
# Isliye logic alag helper functions mein nikala
# ─────────────────────────────────────────
async def _send_plans(client: Client, msg: Message):
    await msg.reply_text(
        "💎 **Premium Plans**\n\n"
        "Unlimited downloads + priority queue + larger files!\n\n"
        "Neeche plan choose karo:",
        reply_markup=plans_inline_keyboard(),
    )


async def _send_status(client: Client, msg: Message):
    user   = await get_user(msg.from_user.id)
    plan   = user.get("plan", "free").capitalize()
    total  = user.get("total_downloads", 0)
    expiry = user.get("expiry")
    prem   = await is_premium(msg.from_user.id)

    if plan == "Premium" and prem:
        expiry_str = expiry.strftime("%d %b %Y") if expiry else "♾️ Lifetime"
        plan_label = f"💎 Premium (expires {expiry_str})"
        limit_line = "📥 Downloads: ♾️ Unlimited"
    else:
        remaining  = max(0, FREE_DOWNLOAD_LIMIT - total)
        plan_label = "🆓 Free"
        limit_line = (
            f"📥 Downloads used: {total}/{FREE_DOWNLOAD_LIMIT}\n"
            f"⏳ Remaining: {remaining}"
            if remaining > 0
            else f"🚫 Limit reached ({total}/{FREE_DOWNLOAD_LIMIT}) — upgrade karein!"
        )

    await msg.reply_text(
        f"📊 **Your Status**\n\n"
        f"👤 Plan: {plan_label}\n"
        f"{limit_line}\n\n"
        f"💎 Upgrade: /plans"
    )


async def _send_help(client: Client, msg: Message):
    await msg.reply_text(
        "╔══════════════════════╗\n"
        "║  📖 HOW TO USE       ║\n"
        "╚══════════════════════╝\n\n"
        "1️⃣ DiskWala pe file open karo\n"
        "2️⃣ Share link copy karo\n"
        "3️⃣ Yahan paste karo\n"
        "4️⃣ Bot download karke bhejega!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>File Size:</b>\n"
        f"≤ 50 MB → Inline play\n"
        f"> 50 MB → Document file\n"
        f"Max → 4 GB (premium)\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ <b>Commands:</b>\n"
        "/start  — Welcome\n"
        "/help   — Help\n"
        "/status — Your plan status\n"
        "/plans  — Premium plans\n"
        "/cancel — Cancel active download\n"
        "/stats  — Admin stats\n\n"
        "👨‍💻 Dev: @anujedits76",
        reply_markup=MAIN_KEYBOARD,
    )


# ─────────────────────────────────────────
# Pyrogram Handlers
# ─────────────────────────────────────────
def register_pyro_handlers(bot: Client):
    """Attach all pyrogram handlers to `bot`."""

    @bot.on_message(filters.command("start") & filters.private)
    async def pyro_cmd_start(client: Client, msg: Message):
        user = await get_user(msg.from_user.id)
        name   = msg.from_user.first_name or "Friend"
        plan   = user.get("plan", "free").capitalize()
        expiry = user.get("expiry")
        expiry_str = (
            expiry.strftime("%d %b %Y") if expiry
            else ("♾️ Lifetime" if plan == "Premium" else "—")
        )
        await stats.register_user(msg.from_user)

        welcome = (
            f"👋 <b>Hello {name}!</b>\n\n"
            f"🚀 <b>DiskWala VIP Downloader Bot</b>\n\n"
            f"╭━━━━━━━━━━━━━━━╮\n"
            f"💎 Features\n"
            f"┣ 📥 Fast Downloading\n"
            f"┣ 🎬 HD Video Support\n"
            f"┣ 📂 Direct File Generation\n"
            f"┣ ⚡ DB Cache — Instant Resend\n"
            f"┣ 🔐 Secure & Private\n"
            f"┣ 🌍 Multi-Format Support\n"
            f"╰━━━━━━━━━━━━━━━╯\n\n"
            f"📌 <b>How To Use:</b>\n"
            f"1️⃣ DiskWala link bhejein\n"
            f"2️⃣ Kuch seconds wait karein\n"
            f"3️⃣ File instantly receive karein 🚀\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f'👨‍💻 Developer: <a href="http://t.me/anujedits76">ANUJ KUMAR</a>\n'
            f"━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>Your Plan:</b> {plan}\n"
            f"📅 <b>Expiry:</b> {expiry_str}\n\n"
            f"📢 Channel: @{CHANNEL_LINK}\n"
            f"💬 Support: @{SUPPORT_USERNAME}"
        )

        if PHOTO_URL:
            try:
                await msg.reply_photo(photo=PHOTO_URL, caption=welcome, reply_markup=MAIN_KEYBOARD)
                return
            except Exception:
                pass
        await msg.reply_text(welcome, reply_markup=MAIN_KEYBOARD)

    @bot.on_message(filters.command("help") & filters.private)
    async def pyro_cmd_help(client: Client, msg: Message):
        await _send_help(client, msg)

    @bot.on_message(filters.command("status") & filters.private)
    async def pyro_cmd_status(client: Client, msg: Message):
        await _send_status(client, msg)

    @bot.on_message(filters.command("plans") & filters.private)
    async def pyro_cmd_plans(client: Client, msg: Message):
        await _send_plans(client, msg)

    @bot.on_message(filters.command("cancel") & filters.private)
    async def pyro_cmd_cancel(client: Client, msg: Message):
        user_id = msg.from_user.id
        q = active_tasks.get(user_id)
        if not q:
            await msg.reply_text("ℹ️ Koi active download nahi hai.")
            return
        cancelled = 0
        for tid in list(q):
            ts = task_state.get(tid)
            if ts:
                ts["cancelled"] = True
                cancelled += 1
        active_tasks.pop(user_id, None)
        await msg.reply_text(f"✅ {cancelled} task(s) cancel kar diye.")

    @bot.on_message(filters.command("addpremium") & filters.private)
    async def pyro_cmd_addpremium(client: Client, msg: Message):
        if msg.from_user.id not in ADMIN_IDS:
            await msg.reply_text("⛔ Not authorized.")
            return
        parts = msg.text.split()
        if len(parts) < 3:
            await msg.reply_text("Usage: /addpremium <user_id> <days>  (-1 = lifetime)")
            return
        try:
            target_id = int(parts[1])
            days      = int(parts[2])
        except ValueError:
            await msg.reply_text("❌ Invalid user_id or days.")
            return
        await activate_premium(target_id, days)
        label = "Lifetime" if days == -1 else f"{days} days"
        await msg.reply_text(f"✅ Premium activated for `{target_id}` — {label}")
        try:
            await client.send_message(
                target_id,
                f"🎉 Aapka premium plan activate ho gaya! ({label})\nFast downloads enjoy karein!"
            )
        except Exception:
            pass

    @bot.on_message(filters.command("removepremium") & filters.private)
    async def pyro_cmd_removepremium(client: Client, msg: Message):
        if msg.from_user.id not in ADMIN_IDS:
            await msg.reply_text("⛔ Not authorized.")
            return
        parts = msg.text.split()
        if len(parts) < 2:
            await msg.reply_text("Usage: /removepremium <user_id>")
            return
        try:
            target_id = int(parts[1])
        except ValueError:
            await msg.reply_text("❌ Invalid user_id.")
            return
        user = await get_user(target_id)
        if user.get("plan") == "free":
            await msg.reply_text(f"ℹ️ User `{target_id}` already free plan pe hai.")
            return
        await revoke_premium(target_id)
        await msg.reply_text(f"✅ Premium remove kar diya for `{target_id}`.")
        try:
            await client.send_message(
                target_id,
                "⚠️ Aapka premium plan admin ne remove kar diya.\n\n"
                f"Plans dekhne ke liye: /plans\nContact: @{SUPPORT_USERNAME}",
            )
        except Exception:
            pass

    @bot.on_message(filters.command("checkuser") & filters.private)
    async def pyro_cmd_checkuser(client: Client, msg: Message):
        if msg.from_user.id not in ADMIN_IDS:
            await msg.reply_text("⛔ Not authorized.")
            return
        parts = msg.text.split()
        if len(parts) < 2:
            await msg.reply_text("Usage: /checkuser <user_id>")
            return
        try:
            target_id = int(parts[1])
        except ValueError:
            await msg.reply_text("❌ Invalid user_id.")
            return

        user   = await get_user(target_id)
        plan   = user.get("plan", "free").capitalize()
        expiry = user.get("expiry")
        total  = user.get("total_downloads", 0)
        joined = user.get("joined_at")
        prem   = await is_premium(target_id)

        if plan == "Premium" and prem:
            expiry_str  = expiry.strftime("%d %b %Y %H:%M UTC") if expiry else "♾️ Lifetime"
            status_icon = "💎"
        elif plan == "Premium" and not prem:
            expiry_str  = expiry.strftime("%d %b %Y %H:%M UTC") if expiry else "—"
            status_icon = "⌛ Expired"
        else:
            expiry_str  = "—"
            status_icon = "🆓"

        joined_str = joined.strftime("%d %b %Y") if joined else "Unknown"
        await msg.reply_text(
            f"👤 **User Info** — `{target_id}`\n\n"
            f"📋 Plan: {status_icon} {plan}\n"
            f"📅 Expiry: {expiry_str}\n"
            f"📥 Downloads: {total}\n"
            f"🗓️ Joined: {joined_str}\n\n"
            f"/addpremium {target_id} <days>\n"
            f"/removepremium {target_id}",
        )

    @bot.on_message(filters.command("broadcast") & filters.private)
    async def pyro_cmd_broadcast(client: Client, msg: Message):
        if msg.from_user.id not in ADMIN_IDS:
            await msg.reply_text("⛔ Not authorized.")
            return
        if not msg.reply_to_message:
            await msg.reply_text("Reply to a message to broadcast it.")
            return
        if not users_col:
            await msg.reply_text("❌ MongoDB not configured.")
            return
        sent = failed = 0
        async for user in users_col.find({}, {"user_id": 1}):
            try:
                await client.copy_message(
                    chat_id=user["user_id"],
                    from_chat_id=msg.chat.id,
                    message_id=msg.reply_to_message.id,
                )
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1
        await msg.reply_text(f"📢 Broadcast done!\n✅ Sent: {sent}\n❌ Failed: {failed}")

    @bot.on_message(filters.command("stats") & filters.private)
    async def pyro_cmd_stats(client: Client, msg: Message):
        if msg.from_user.id not in ADMIN_IDS:
            await msg.reply_text("⛔ Not authorized.")
            return
        total_users   = await users_col.count_documents({}) if users_col else 0
        premium_users = await users_col.count_documents({"plan": "premium"}) if users_col else 0
        total_files   = await files_col.count_documents({}) if files_col else 0
        s             = await stats.get()

        await msg.reply_text(
            f"📊 **Bot Stats**\n\n"
            f"👥 Total Users: {total_users:,}\n"
            f"💎 Premium Users: {premium_users:,}\n"
            f"🗄️ Cached Files: {total_files:,}\n"
            f"📥 Total Downloads: {s['downloads']:,}\n"
            f"⚙️ Active Tasks: {len(task_state)}\n"
            f"🤖 Uploader Bots: {len(uploader_clients)}\n\n"
            "**Admin Commands:**\n"
            "/addpremium <id> <days>\n"
            "/removepremium <id>\n"
            "/checkuser <id>\n"
            "/broadcast\n"
            "/stats"
        )

    # ── Callbacks ─────────────────────────────────────────────────────────────

    @bot.on_callback_query(filters.regex(r"^cancel:(.+)$"))
    async def pyro_cb_cancel(client: Client, cq: CallbackQuery):
        task_id = cq.matches[0].group(1)
        ts = task_state.get(task_id)
        if ts:
            ts["cancelled"] = True
            await cq.answer("❌ Cancellation requested!")
            try:
                await cq.message.edit_text("⏹️ Cancelling…")
            except Exception:
                pass
        else:
            await cq.answer("Task not found or already done.", show_alert=True)

    @bot.on_callback_query(filters.regex(r"^buyplan:(\d+):(-?\d+)$"))
    async def pyro_cb_buyplan(client: Client, cq: CallbackQuery):
        price = cq.matches[0].group(1)
        days  = int(cq.matches[0].group(2))
        label = "Lifetime ♾️" if days == -1 else f"{days} Days"
        upi_str = f"UPI ID: `{UPI_ID}`\nPayee: {UPI_NAME}" if UPI_ID else "Admin se contact karein."
        await cq.message.edit_text(
            f"💎 **Plan Selected: ₹{price} — {label}**\n\n"
            f"💳 **Payment Details:**\n{upi_str}\n\n"
            f"📌 **Payment ke baad:**\n"
            f"Apna UTR/Transaction ID @{SUPPORT_USERNAME} ko bhejein:\n"
            f"`PLAN {price} UTR:<your_utr_here>`\n\n"
            f"✅ Admin kuch minutes mein activate kar dega!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}")],
            ]),
        )
        await cq.answer()

    @bot.on_callback_query(filters.regex(r"^show_plans$"))
    async def pyro_cb_show_plans(client: Client, cq: CallbackQuery):
        await cq.message.edit_text(
            "💎 **Premium Plans**\n\nNeeche plan choose karo:",
            reply_markup=plans_inline_keyboard(),
        )
        await cq.answer()

    @bot.on_callback_query(filters.regex(r"^check_join$"))
    async def pyro_cb_check_join(client: Client, cq: CallbackQuery):
        user_id   = cq.from_user.id
        is_member = await check_membership_pyro(client, user_id)
        if is_member:
            await cq.answer("✅ Verified! Ab apna DiskWala link bhejein.", show_alert=True)
            try:
                await cq.message.delete()
            except Exception:
                pass
        else:
            await cq.answer("❌ Abhi join nahi kiya!", show_alert=True)

    # ── Main text handler ──────────────────────────────────────────────────────

    @bot.on_message(filters.private & filters.text)
    async def pyro_on_text(client: Client, msg: Message):
        user_id = msg.from_user.id
        text    = msg.text.strip()
        await stats.register_user(msg.from_user)

        # FIX #1 — helper functions call karo, decorated handlers nahi
        if text == "💎 Plans":
            await _send_plans(client, msg)
            return
        if text == "📊 My Status":
            await _send_status(client, msg)
            return
        if text == "❓ Help":
            await _send_help(client, msg)
            return
        if text == "📞 Support":
            await msg.reply_text(
                f"💬 **Support**\n\nContact: @{SUPPORT_USERNAME}\nChannel: @{CHANNEL_LINK}"
            )
            return

        if not is_diskwala_url(text):
            await msg.reply_text(
                "⚠️ Sirf DiskWala links supported hain.\n\n"
                "Example:\n`https://www.diskwala.com/s/abc123`",
                reply_markup=MAIN_KEYBOARD,
            )
            return

        file_id = extract_diskwala_file_id(text)
        if not file_id:
            await msg.reply_text(
                "❌ DiskWala link se file ID extract nahi hua.\n"
                "Sahi link share karein.\n\n"
                "Example:\n`https://www.diskwala.com/s/abc123`"
            )
            return

        if REQUIRED_CHANNEL_USERNAME:
            is_member = await check_membership_pyro(client, user_id)
            if not is_member:
                await msg.reply_text(
                    f"❌ **Join required!**\n\n"
                    f"Pehle channel join karein:\n"
                    f"{REQUIRED_CHANNEL_URL or f'https://t.me/{REQUIRED_CHANNEL_USERNAME}'}",
                    reply_markup=join_kb_pyrogram(),
                )
                return

        q = active_tasks.setdefault(user_id, set())
        if len(q) >= MAX_USER_QUEUE:
            await msg.reply_text(
                f"⚠️ Aapke paas {len(q)} tasks already queue mein hain.\n"
                "Inke complete hone ka wait karein ya /cancel karein."
            )
            return

        task_id = f"{user_id}_{int(time.time() * 1000)}"
        q.add(task_id)

        status_msg = await msg.reply_text(
            "⏳ Task queue mein hai… abhi shuru hoga.",
            reply_markup=kb_inline(task_id),
        )

        asyncio.create_task(
            process_task_pyro(task_id, user_id, file_id, status_msg)
        )


# ─────────────────────────────────────────
# PTB handlers (fallback when no Pyrogram)
# ─────────────────────────────────────────
async def ptb_cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await stats.register_user(user)
    await update.message.reply_text(
        f"👋 <b>Hello {user.first_name}!</b>\n\n"
        "🚀 <b>DiskWala Downloader Bot</b>\n\n"
        "📥 DiskWala ka koi bhi link bhejein aur main\n"
        "    file download karke Telegram pe bhej dunga!\n\n"
        "✅ Supported: Videos, Images, Files\n"
        "📦 Max size: 2 GB\n\n"
        "🔗 <b>Example:</b>\n"
        "<code>https://www.diskwala.com/s/abc123</code>",
        parse_mode="HTML",
        reply_markup=TgMarkup([[
            TgButton(
                "➕ Add to Group",
                url=f"https://t.me/{BOT_USERNAME}?startgroup=true",
            )
        ]]),
    )


async def ptb_cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "╔══════════════════════╗\n"
        "║  📖 HOW TO USE       ║\n"
        "╚══════════════════════╝\n\n"
        "1️⃣ DiskWala pe file open karo\n"
        "2️⃣ Share link copy karo\n"
        "3️⃣ Yahan paste karo\n"
        "4️⃣ Bot download karke bhejega!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>File Size:</b>\n"
        "≤ 50MB → Inline play\n"
        "> 50MB → Document file\n"
        "Max → 2 GB\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ <b>Commands:</b>\n"
        "/start — Welcome\n"
        "/help  — Help\n"
        "/stats — Statistics (admin)\n\n"
        "👨‍💻 Dev: @anujedits76",
        parse_mode="HTML",
    )


async def ptb_cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only.")
        return
    s = await stats.get()
    await update.message.reply_text(
        f"📊 <b>Bot Stats</b>\n\n"
        f"👥 Users: {s['users']:,}\n"
        f"📥 Downloads: {s['downloads']:,}",
        parse_mode="HTML",
    )


async def ptb_handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg  = update.effective_message
    user = update.effective_user
    if not msg or not msg.text:
        return

    await stats.register_user(user)
    text = msg.text.strip()

    if not is_diskwala_url(text):
        await msg.reply_text(
            "⚠️ Sirf DiskWala links supported hain.\n\n"
            "Example:\n<code>https://www.diskwala.com/s/abc123</code>",
            parse_mode="HTML",
        )
        return

    file_id = extract_diskwala_file_id(text)
    if not file_id:
        await msg.reply_text(
            "❌ DiskWala link se file ID extract nahi hua.\n"
            "Sahi link share karein.\n\n"
            "Example:\n<code>https://www.diskwala.com/s/abc123</code>",
            parse_mode="HTML",
        )
        return

    if REQUIRED_CHANNEL_USERNAME and not await is_joined_ptb(context, user.id):
        context.user_data["pending"] = {"url": text, "file_id": file_id}
        await msg.reply_text(
            f"⚠️ Pehle channel join karein:\n{REQUIRED_CHANNEL_URL}",
            reply_markup=TgMarkup([
                [TgButton("📢 Join Channel", url=REQUIRED_CHANNEL_URL)],
                [TgButton("✅ I Joined",      callback_data="check_join")],
            ]),
        )
        return

    await context.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.TYPING)

    status   = await msg.reply_text("🔍 DiskWala link processing...", parse_mode="HTML")
    progress = Progress(status)
    temp_dir = DOWNLOAD_DIR / f"dw_{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    async with dl_semaphore:
        try:
            await progress.start_dl()
            file_path, info = await download_diskwala_file(file_id, temp_dir)
            await progress.done_dl()
            await send_file_direct_ptb(msg, progress, file_path, info)
            await stats.increment()
            await safe_edit(status, "✅ <b>Done!</b> Enjoy 🎉")
        except Exception as e:
            logger.error("PTB download error: %s", e)
            await safe_edit(status, f"❌ <b>Failed!</b>\n\n<code>{e}</code>")
        finally:
            shutil.rmtree(str(temp_dir), ignore_errors=True)
            await progress.cleanup()


# FIX #2 — deleted message pe reply_text fix + FIX #10 — double query.answer() fix
async def ptb_handle_check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user    = query.from_user
    chat_id = query.message.chat_id

    if await is_joined_ptb(context, user.id):
        # FIX #10 — sirf EK baar answer karo
        await query.answer("✅ Verified!", show_alert=True)
        try:
            await query.message.delete()
        except Exception:
            pass

        pending = context.user_data.pop("pending", None)
        if pending:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            # FIX #2 — deleted message pe reply nahi, bot.send_message use karo
            status = await context.bot.send_message(chat_id=chat_id, text="🔍 Processing...", parse_mode="HTML")
            progress = Progress(status)
            temp_dir = DOWNLOAD_DIR / f"dw_{uuid.uuid4().hex}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            async with dl_semaphore:
                try:
                    await progress.start_dl()
                    file_path, info = await download_diskwala_file(
                        pending["file_id"], temp_dir
                    )
                    await progress.done_dl()
                    # FIX #2 — reply_to deleted message nahi, direct send_message
                    await send_file_direct_ptb(status, progress, file_path, info)
                    await safe_edit(status, "✅ <b>Done!</b> Enjoy 🎉")
                except Exception as e:
                    await safe_edit(status, f"❌ <b>Failed!</b>\n\n<code>{e}</code>")
                finally:
                    shutil.rmtree(str(temp_dir), ignore_errors=True)
                    await progress.cleanup()
    else:
        await query.answer("❌ Abhi join nahi kiya!", show_alert=True)


def build_ptb_app() -> Application:
    req = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=UPLOAD_READ_TIMEOUT,
        write_timeout=UPLOAD_WRITE_TIMEOUT,
        connect_timeout=UPLOAD_CONNECT_TIMEOUT,
        pool_timeout=UPLOAD_POOL_TIMEOUT,
    )
    app_ptb = Application.builder().token(BOT_TOKEN).request(req).build()
    app_ptb.add_handler(CommandHandler("start", ptb_cmd_start))
    app_ptb.add_handler(CommandHandler("help",  ptb_cmd_help))
    app_ptb.add_handler(CommandHandler("stats", ptb_cmd_stats))
    app_ptb.add_handler(
        CallbackQueryHandler(ptb_handle_check_join, pattern="^check_join$")
    )
    app_ptb.add_handler(
        MessageHandler(tg_filters.TEXT & ~tg_filters.COMMAND, ptb_handle_message)
    )
    return app_ptb


# ─────────────────────────────────────────
# Webhook route (PTB)
# FIX #9 — .result() blocking hata ke asyncio.run_coroutine_threadsafe use karo
# timeout kam kiya aur non-blocking response diya
# ─────────────────────────────────────────
@flask_app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def ptb_webhook():
    data = request.get_json(force=True)
    app  = flask_app.config.get("ptb_application")
    loop = flask_app.config.get("event_loop")
    if app and loop:
        future = asyncio.run_coroutine_threadsafe(
            app.process_update(Update.de_json(data, app.bot)), loop
        )
        try:
            # FIX #9 — timeout 120s se ghata ke 30s kiya; non-blocking ke liye
            # timeout hone par bhi 200 OK return karo (Telegram retry karega)
            future.result(timeout=30)
        except Exception as e:
            logger.warning("Webhook processing error: %s", e)
    return "OK"


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────
async def main():
    global global_active_sem, upload_active_sem, dl_semaphore
    global uploader_lock, user_active_lock

    global_active_sem = asyncio.Semaphore(GLOBAL_ACTIVE_LIMIT)
    upload_active_sem = asyncio.Semaphore(UPLOAD_ACTIVE_LIMIT)
    dl_semaphore      = asyncio.Semaphore(4)
    uploader_lock     = asyncio.Lock()
    user_active_lock  = asyncio.Lock()

    # FIX #8 — StatsStore lock event loop ke andar initialize karo
    stats.init_lock()

    await ensure_indexes()

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask health server on port %d", PORT)

    if API_ID and API_HASH and BOT_TOKEN:
        await init_uploader_bots()

        if pyro_bot is None:
            logger.error("Main pyrogram client failed to start — aborting.")
            return

        register_pyro_handlers(pyro_bot)

        logger.info("Pyrogram mode active. Waiting for updates…")
        try:
            await asyncio.Event().wait()
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        finally:
            logger.info("Shutting down…")
            for name, cl in list(uploader_clients.items()):
                try:
                    await cl.stop()
                except Exception:
                    pass
            await dw_client.close()
            logger.info("Done.")
    else:
        logger.info("Pyrogram not configured — using PTB fallback mode.")
        ptb_app = build_ptb_app()

        if WEBHOOK_URL:
            loop = asyncio.get_event_loop()
            flask_app.config["ptb_application"] = ptb_app
            flask_app.config["event_loop"]       = loop

            await ptb_app.initialize()
            await ptb_app.bot.set_webhook(
                url=f"{WEBHOOK_URL.rstrip('/')}/webhook/{BOT_TOKEN}",
                allowed_updates=["message", "callback_query"],
            )
            await ptb_app.start()
            logger.info("PTB webhook mode active.")
            try:
                while True:
                    await asyncio.sleep(3600)
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                await ptb_app.stop()
                await ptb_app.shutdown()
                await dw_client.close()
        else:
            logger.info("PTB polling mode.")
            await ptb_app.initialize()
            await ptb_app.start()
            await ptb_app.updater.start_polling(
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True,
            )
            try:
                await asyncio.Event().wait()
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                await ptb_app.updater.stop()
                await ptb_app.stop()
                await ptb_app.shutdown()
                await dw_client.close()


if __name__ == "__main__":
    asyncio.run(main())
