# 🚀 DiskWala VIP Downloader Bot

A powerful Telegram bot to download files from DiskWala and send them directly to users via Telegram.

**Developer:** [@anujbyedit](https://t.me/anujbyedit)

---

## ✨ Features

- 📥 Fast file downloading from DiskWala
- 🎬 HD Video support with streaming
- ⚡ DB Cache — instant resend without re-downloading
- 💎 Premium & Free plan system
- 📊 Download limit for free users
- 🔐 Channel join verification
- 📢 Admin broadcast system
- 🤖 Multi-uploader bot support
- 🗄️ MongoDB database integration
- 🌍 Multi-format support (Video, Audio, Image, Document)

---

# ⚙️ Environment Variables

Create a `.env` file and add:

```env
# ─────────────────────────────────────────
# DiskWala Bot — Environment Variables
# Developer: @anujbyedit
# ─────────────────────────────────────────

# ── Telegram Bot ──
BOT_TOKEN=YOUR_BOT_TOKEN
BOT_USERNAME=your_bot_username

# Webhook URL
WEBHOOK_URL=

# Port
PORT=5000

# ── Admin ──
ADMIN_USER_ID=123456789
ADMIN_IDS=123456789

# ── Channel Membership Gate ──
REQUIRED_CHANNEL_USERNAME=YourChannel
REQUIRED_CHANNEL_URL=https://t.me/YourChannel
CHANNEL_LINK=YourChannel
SUPPORT_USERNAME=YourSupportBot

# ── DiskWala API ──
DISKWALA_API_KEY=YOUR_API_KEY
DISKWALA_BASE_URL=https://ddudapidd.diskwala.com/api/v1

# ── MongoDB ──
MONGO_DB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
DB_CHANNEL=-1001234567890

# ── Pyrogram ──
API_ID=12345678
API_HASH=your_api_hash

# Support bot tokens
SUPPORT_BOT_TOKENS=

# ── Premium / UPI ──
UPI_ID=example@ybl
UPI_NAME=ANUJ

# ── Free Limit ──
FREE_DOWNLOAD_LIMIT=10

# ── Media URLs ──
PHOTO_URL=https://example.com/photo.jpg
DUMMY_URL=https://example.com/dummy.jpg
```

---

# 📦 Requirements

Create `requirements.txt`

```txt
# DiskWala Downloader Bot — Dependencies
# Developer: @anujbyedit

# Telegram
python-telegram-bot==21.6
pyrogram==2.0.106
TgCrypto

# HTTP
httpx[http2]==0.27.0
requests==2.32.3

# Database
motor==3.5.1
pymongo==4.8.0

# Web server
flask==3.0.3

# Environment loader
python-dotenv==1.0.1

# Optional fast event loop
uvloop==0.20.0; sys_platform != "win32"
```

Install:

```bash
pip install -r requirements.txt
```

---

# 🚀 Setup & Run

## 1. Clone Repository

```bash
git clone https://github.com/anujedits76/Dw.git
cd Dw
```

---

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 3. Run the Bot

```bash
python bot.py
```

---

# 🌐 Deploy on Render / Railway / Koyeb

1. Create new Web Service
2. Upload repository
3. Add all environment variables
4. Start command:

```bash
python bot.py
```

5. Add public URL in:

```env
WEBHOOK_URL=https://your-app.onrender.com
```

6. Deploy 🚀

---

# 📋 Bot Commands

| Command | Description | Access |
|---|---|---|
| `/start` | Welcome message | All users |
| `/help` | How to use the bot | All users |
| `/status` | Check your plan & downloads | All users |
| `/plans` | View premium plans | All users |
| `/cancel` | Cancel active download | All users |
| `/stats` | Bot statistics | Admin only |
| `/addpremium <id> <days>` | Give premium to user | Admin only |
| `/removepremium <id>` | Remove premium from user | Admin only |
| `/checkuser <id>` | Check user details | Admin only |
| `/broadcast` | Broadcast message to all users | Admin only |

---

# 💎 Premium Plans

| Plan | Price | Duration |
|---|---|---|
| Basic | ₹19 | 12 Days |
| Standard | ₹29 | 21 Days |
| Popular | ₹45 | 35 Days |
| Pro | ₹99 | 99 Days |
| Lifetime | ₹999 | Forever ♾️ |

---

# 🔗 Supported DiskWala Links

```txt
https://www.diskwala.com/s/abc123
https://www.diskwala.com/file/abc123
https://www.diskwala.com/app/abc123
https://www.diskwala.com/share/abc123
https://www.diskwala.com/dl/abc123
https://www.diskwala.com/download/abc123
https://www.diskwala.com/v/abc123
https://www.diskwala.com/f/abc123
```

---

# 📁 File Size Limits

| Plan | Max Size |
|---|---|
| Free | 50 MB inline / 2 GB as document |
| Premium | Up to 4 GB |

---

# 🗂️ Project Structure

```txt
Dw/
├── bot.py
├── requirements.txt
├── Procfile
├── .env.example
└── README.md
```

---

# ⚠️ Important Notes

- Never hardcode `BOT_TOKEN`, `API_HASH`, or `MONGO_DB_URI`
- Bot must be admin in `DB_CHANNEL`
- Bot must be admin in required channel
- Files auto-delete after 1 hour
- If `WEBHOOK_URL` is empty, bot runs in polling mode

---

# 👨‍💻 Developer

Made with ❤️ by [@anujbyedit](https://t.me/anujbyedit)
