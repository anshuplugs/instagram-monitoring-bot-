# bot.py
import discord
from discord.ext import tasks, commands
from telegram import Update, Bot as TelegramBot
from telegram.ext import Application, CommandHandler, ContextTypes
import os
import aiosqlite
import asyncio
import random
from datetime import datetime
from dotenv import load_dotenv
from instagram_monitor import InstagramMonitor

# --- Setup ---
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DATABASE_FILE = os.getenv('DATABASE_FILE', 'monitor.db')
PROXY_URL = os.getenv('PROXY_URL')

# --- Bot Initialization ---
# Discord Bot
intents = discord.Intents.default()
intents.message_content = True
discord_bot = commands.Bot(command_prefix='/', intents=intents)

# Global objects for db and monitor
db_connection = None
instagram_monitor = None
telegram_app = None

# --- Discord Commands ---
@discord_bot.command(name='ban')
async def monitor_ban(ctx, username: str):
    username = username.replace('@', '').strip().lower()
    if not username:
        await ctx.send("❌ Please provide a valid username.")
        return

    async with db_connection.cursor() as cursor:
        await cursor.execute(
            'INSERT OR REPLACE INTO monitored_profiles (username, chat_id, user_id, platform) VALUES (?, ?, ?, ?)',
            (username, ctx.channel.id, ctx.author.id, 'discord')
        )
        await db_connection.commit()
    await ctx.send(f"✅ Now monitoring **@{username}** for ban/unban events.")

# --- Telegram Commands ---
async def tg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I'm the Instagram Monitor Bot. Use /ban <username> to start.")

async def tg_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a username. Usage: /ban <username>")
        return
    
    username = context.args[0].replace('@', '').strip().lower()
    async with db_connection.cursor() as cursor:
        await cursor.execute(
            'INSERT OR REPLACE INTO monitored_profiles (username, chat_id, user_id, platform) VALUES (?, ?, ?, ?)',
            (username, update.message.chat_id, update.message.from_user.id, 'telegram')
        )
        await db_connection.commit()
    await update.message.reply_text(f"✅ Now monitoring @{username} for ban/unban events.")

# --- Background Monitoring Task & Notifications ---
@tasks.loop(minutes=5)
async def monitor_profiles():
    await discord_bot.wait_until_ready()
    async with db_connection.cursor() as cursor:
        await cursor.execute('SELECT username, chat_id, platform FROM monitored_profiles WHERE is_active = 1')
        profiles_to_check = await cursor.fetchall()

    for username, chat_id, platform in profiles_to_check:
        try:
            result = await instagram_monitor.get_profile_info(username)
            current_status = result['status']
            
            async with db_connection.cursor() as cursor:
                await cursor.execute('SELECT status FROM profile_history WHERE username = ? ORDER BY checked_at DESC LIMIT 1', (username,))
                last_check = await cursor.fetchone()
                previous_status = last_check[0] if last_check else None
                
                await cursor.execute('INSERT INTO profile_history (username, status) VALUES (?, ?)', (username, current_status))
                await db_connection.commit()

                if previous_status and previous_status != current_status:
                    await handle_notification(username, previous_status, current_status, chat_id, platform)
            
            await asyncio.sleep(random.uniform(2, 5))
        except Exception as e:
            print(f"Error monitoring {username}: {e}")

async def handle_notification(username: str, old_status: str, new_status: str, chat_id: int, platform: str):
    title, description, color, event_type = "", "", 0x0099ff, "status_change"
    
    if old_status in ['active', 'private'] and new_status == 'not_found':
        title, description, color, event_type = "🚨 PROFILE BANNED/DELETED!", f"**@{username}** has become inaccessible!", 0xff4444, "banned"
    elif old_status == 'not_found' and new_status in ['active', 'private']:
        title, description, color, event_type = "🎉 PROFILE IS BACK!", f"**@{username}** is now accessible again.", 0x00ff00, "unbanned"
    else:
        title, description = "📊 Status Change", f"**@{username}** status changed from `{old_status}` to `{new_status}`."

    if platform == 'discord':
        channel = discord_bot.get_channel(chat_id)
        if channel:
            embed = discord.Embed(title=title, description=description, color=color)
            embed.add_field(name="📱 Profile Link", value=f"[Open on Instagram](https://instagram.com/{username})")
            embed.set_footer(text=f"Detected at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            await channel.send(embed=embed)
    elif platform == 'telegram':
        tg_bot = TelegramBot(token=TELEGRAM_TOKEN)
        message = f"*{title}*\n{description.replace('**', '*')}\n[Open on Instagram](https://instagram.com/{username})"
        await tg_bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

    if event_type in ['banned', 'unbanned']:
        async with db_connection.cursor() as cursor:
            await cursor.execute('INSERT INTO ban_events (username, event_type) VALUES (?, ?)', (username, event_type))
            await db_connection.commit()

# --- Main Application Logic ---
async def main():
    global db_connection, instagram_monitor, telegram_app
    
    # Initialize shared components
    db_connection = await aiosqlite.connect(DATABASE_FILE)
    instagram_monitor = InstagramMonitor(proxy=PROXY_URL)
    
    # Setup Telegram bot
    telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", tg_start))
    telegram_app.add_handler(CommandHandler("ban", tg_ban))
    await telegram_app.initialize()
    await telegram_app.start()
    
    # Start background task and bots
    monitor_profiles.start()
    
    async with discord_bot:
        print("Starting bots...")
        # Start polling for Telegram in the background
        await telegram_app.updater.start_polling()
        # Start the Discord bot (this is a blocking call)
        await discord_bot.start(DISCORD_TOKEN)
        # When Discord bot stops, stop Telegram bot
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()

if __name__ == "__main__":
    if not DISCORD_TOKEN or not TELEGRAM_TOKEN:
        print("Error: Bot tokens are not set in the .env file.")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("Bots shutting down.")
