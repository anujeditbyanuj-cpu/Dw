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

## ⚙️ Environment Variables

Set these in your hosting platform or `.env` file:

| Variable | Description | Example |
|---|---|---|
| `BOT_TOKEN` | Your Telegram bot token | `123456:ABC...` |
| `BOT_USERNAME` | Bot username without @ | `my_bot` |
| `API_ID` | Telegram API ID (from my.telegram.org) | `12345678` |
| `API_HASH` | Telegram API Hash | `abc123...` |
| `MONGO_DB_URI` | MongoDB connection URI | `mongodb+srv://...` |
| `DB_CHANNEL` | Channel ID for file storage | `-1001234567890` |
| `ADMIN_USER_ID` | Main admin Telegram user ID | `123456789` |
| `ADMIN_IDS` | Comma-separated admin IDs | `123456789,987654321` |
| `DISKWALA_API_KEY` | DiskWala API key | `69ffffb2...` |
| `DISKWALA_BASE_URL` | DiskWala API base URL | `https://ddudapidd.diskwala.com/api/v1` |
| `REQUIRED_CHANNEL_USERNAME` | Channel users must join | `MyChannel` |
| `REQUIRED_CHANNEL_URL` | Channel invite link | `https://t.me/MyChannel` |
| `CHANNEL_LINK` | Channel link shown in bot | `MyChannel` |
| `SUPPORT_USERNAME` | Support contact username | `MySupportBot` |
| `WEBHOOK_URL` | Webhook URL (optional) | `https://myapp.onrender.com` |
| `PORT` | Flask server port | `5000` |
| `UPI_ID` | UPI ID for payments | `xxx@ybl` |
| `UPI_NAME` | UPI payee name | `ANUJ` |
| `PHOTO_URL` | Welcome photo URL | `https://...` |
| `DUMMY_URL` | Replacement image after deletion | `https://...` |
| `FREE_DOWNLOAD_LIMIT` | Free user download limit | `10` |
| `SUPPORT_BOT_TOKENS` | Extra bot tokens (comma-separated) | `token1,token2` |

---

## 📦 Requirements

```
pyrogram
python-telegram-bot[webhooks]
motor
httpx
flask
uvloop
```

Install with:
```bash
pip install pyrogram python-telegram-bot[webhooks] motor httpx flask uvloop
```

---

## 🚀 Setup & Run

### 1. Clone the repo
```bash
git clone anujedits76
cd Dw
```
ables
```bash
export BOT_TOKEN="your_bot_token"
export API_ID="your_api_id"
export API_HASH="your_api_hash"
export MONGO_DB_URI="your_mongodb_uri"
export DB_CHANNEL="-1001234567890"
export ADMIN_USER_ID="your_user_id"
export DISKWALA_API_KEY="your_api_key"
```

### 3. Run the bot
```bash
python bot.py
```

---

## 🌐 Deploy on Render / Railway / Koyeb

1. Create new web service
2. Set all environment variables in the dashboard
3. Set start command: `python bot.py`
4. Set `WEBHOOK_URL` to your app's public URL
5. Deploy!

---

## 📋 Bot Commands

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

## 💎 Premium Plans

| Plan | Price | Duration |
|---|---|---|
| Basic | ₹19 | 12 Days |
| Standard | ₹29 | 21 Days |
| Popular | ₹45 | 35 Days |
| Pro | ₹99 | 99 Days |
| Lifetime | ₹999 | Forever ♾️ |

---

## 🔗 Supported DiskWala Link Formats

```
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

## 📁 File Size Limits

| Plan | Max Size |
|---|---|
| Free | 50 MB inline / 2 GB as document |
| Premium | Up to 4 GB |

---

## 🗂️ Project Structure

```
Dw/
├── main.py           ← Full bot code
├── requirements.txt  ← Python dependencies
├── Procfile          ← For Heroku/Render
├── .env.example      ← All env variables explained
└── README.dw
```

---

## ⚠️ Important Notes

- Never hardcode `BOT_TOKEN`, `API_HASH`, or `MONGO_DB_URI` in the code
- Bot must be **admin** in `DB_CHANNEL` to upload files
- Bot must be **admin** in the required channel to check membership
- Files sent to users are **auto-deleted after 1 hour**

---

## 👨‍💻 Developer

Made with ❤️ by [@anujbyedit](https://t.me/anujbyedit)
