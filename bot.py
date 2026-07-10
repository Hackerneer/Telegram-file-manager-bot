import sqlite3
import os
import uuid
import datetime
from telethon import TelegramClient, events

# ---------- ENVIRONMENT VARIABLES (Render pe set karna) ----------
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
# -----------------------------------------------------------------

UPLOAD_DIR = "uploads/"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Database
conn = sqlite3.connect("files.db")
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY,
        file_name TEXT,
        file_path TEXT,
        token TEXT UNIQUE,
        uploader_id INTEGER,
        expiry_time TEXT,
        downloads INTEGER DEFAULT 0,
        max_downloads INTEGER DEFAULT 1
    )
""")
conn.commit()

bot = TelegramClient("secure_bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def generate_token():
    return uuid.uuid4().hex[:16]

def save_file_to_db(file_name, file_path, uploader_id, expiry_minutes=10):
    token = generate_token()
    expiry = datetime.datetime.now() + datetime.timedelta(minutes=expiry_minutes)
    c.execute("""
        INSERT INTO files (file_name, file_path, token, uploader_id, expiry_time)
        VALUES (?, ?, ?, ?, ?)
    """, (file_name, file_path, token, uploader_id, expiry))
    conn.commit()
    return token

def get_file_by_token(token):
    c.execute("""
        SELECT file_path, file_name, expiry_time, downloads, max_downloads 
        FROM files WHERE token = ?
    """, (token,))
    result = c.fetchone()
    if not result:
        return None
    file_path, file_name, expiry, downloads, max_downloads = result
    if datetime.datetime.now() > datetime.datetime.fromisoformat(expiry):
        return "expired"
    if downloads >= max_downloads:
        return "limit_reached"
    return {"path": file_path, "name": file_name}

def increment_download(token):
    c.execute("UPDATE files SET downloads = downloads + 1 WHERE token = ?", (token,))
    conn.commit()

@bot.on(events.NewMessage(pattern="/start"))
async def start(event):
    await event.reply(
        "📁 *Secure File Manager Bot*\n\n"
        "Mujhe koi file bhejo → Main private link doonga\n"
        "Sirf wohi file download hogi, baaki hidden rahengi\n\n"
        "⏳ Link 10 minute mein expire ho jayegi\n"
        "📥 Sirf 1 baar download ho sakti hai",
        parse_mode="markdown"
    )

@bot.on(events.NewMessage(func=lambda e: e.document))
async def upload_file(event):
    msg = await event.reply("⏳ File upload ho rahi hai...")
    try:
        file_path = await event.message.download_media(file=UPLOAD_DIR)
        file_name = event.message.document.attributes[0].file_name
        token = save_file_to_db(file_name, file_path, event.sender_id)
        bot_username = (await bot.get_me()).username
        link = f"https://t.me/{bot_username}?start=download_{token}"
        await msg.edit(
            f"✅ *File upload ho gayi!*\n\n"
            f"📄 {file_name}\n"
            f"🔗 *Aapki private link:*\n{link}\n\n"
            f"⚠️ 10 minute baad link expire ho jayegi\n"
            f"📥 Sirf 1 baar download ho sakti hai",
            parse_mode="markdown",
            link_preview=False
        )
    except Exception as e:
        await msg.edit(f"❌ Error: {str(e)}")

@bot.on(events.NewMessage(pattern="/start download_(.*)"))
async def download_file(event):
    token = event.pattern_match.group(1)
    file_data = get_file_by_token(token)
    if file_data == "expired":
        await event.reply("❌ Link expire ho gayi! Naya link lo.")
        return
    if file_data == "limit_reached":
        await event.reply("❌ Download limit khatam! Link ab inactive hai.")
        return
    if not file_data:
        await event.reply("❌ Galat link!")
        return
    try:
        await event.reply(f"📥 *Download ho raha hai:* {file_data['name']}", parse_mode="markdown")
        await event.reply(file=file_data['path'])
        increment_download(token)
        os.remove(file_data['path'])
    except Exception as e:
        await event.reply(f"❌ Download failed: {str(e)}")

print("🤖 Bot chal raha hai...")
bot.run_until_disconnected()