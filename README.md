# 🚀 DiskWala Downloader Bot

**Developer: [@anujedits76](https://t.me/anujedits76)**

A full-featured Telegram bot that downloads files from DiskWala and sends them to users — with premium plans, DB_CHANNEL caching, multi-bot uploads, and auto video deletion.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📥 DiskWala Download | Video, audio, image, any file |
| ⚡ Fast DB Cache | Files cached in DB_CHANNEL — instant resend |
| 🤖 Multi-Bot Upload | Multiple support bots upload in parallel |
| 💎 Premium System | Free (10 downloads) / Paid plans via UPI |
| 📢 Channel Gate | Require users to join a channel before use |
| ⏱ Auto-Delete | User's video deleted after 1 hour |
| 📊 Admin Panel | addpremium, removepremium, checkuser, broadcast, stats |
| 🌐 Flask Server | Health check endpoint at `/` |
| 🔀 Webhook + Polling | Both modes supported |

---

## 📁 Repo Structure

```
diskwala_bot/
├── main.py           ← Full bot code
├── requirements.txt  ← Python dependencies
├── Procfile          ← For Heroku/Render
├── .env.example      ← All env variables explained
└── README.md
```

---

## ⚙️ Setup

### 1. Clone & Install

```bash
git clone https://github.com/yourrepo/diskwala-bot
cd diskwala-bot
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
nano .env
```

**Required variables:**
- `BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
- `DISKWALA_API_KEY` — your DiskWala API key

**For full features (DB cache + multi-bot):**
- `API_ID` + `API_HASH` — from [my.telegram.org](https://my.telegram.org)
- `MONGO_DB_URI` — MongoDB connection string
- `DB_CHANNEL` — Channel ID where files are cached (bot must be admin)

### 3. Run

```bash
python main.py
```

---

## 🤖 Two Modes

### Mode A — Full (Pyrogram) ✅ Recommended
Set `API_ID`, `API_HASH`, `MONGO_DB_URI`, `DB_CHANNEL`.

Features: DB cache, multi-bot uploads, premium system, 1-hour deletion.

### Mode B — Lite (PTB fallback)
Only set `BOT_TOKEN`. No Pyrogram/MongoDB needed.

Features: Basic download & send, channel gate, stats.

---

## 📦 Deploy to Render / Railway / Heroku

1. Set all env variables in the platform dashboard
2. Build command: `pip install -r requirements.txt`
3. Start command: `python main.py`
4. For webhook mode, set `WEBHOOK_URL` to your app's public URL

---

## 💎 Premium Plans

| Price | Duration |
|---|---|
| ₹19 | 12 days |
| ₹29 | 21 days |
| ₹45 | 35 days |
| ₹99 | 99 days |
| ₹999 | Lifetime |

Admin activates via `/addpremium <user_id> <days>`

---

## 🛠 Admin Commands

| Command | Description |
|---|---|
| `/addpremium <id> <days>` | Activate premium (-1 = lifetime) |
| `/removepremium <id>` | Revoke premium |
| `/checkuser <id>` | View user plan & stats |
| `/broadcast` | Reply to a message to broadcast |
| `/stats` | Bot statistics |

---

## 🔗 DiskWala Link Formats Supported

```
https://www.diskwala.com/s/abc123
https://diskwala.com/s/abc123
https://diskwala.com/file/abc123
https://diskwala.com/f/abc123
https://diskwala.com/v/abc123
https://diskwala.com/d/abc123
```

---

## 📞 Support

- Telegram: [@anujedits76](https://t.me/anujedits76)
