import discord
from discord.ext import commands
import json
import os
from flask import Flask
from threading import Thread

# --- RENDER KEEP-ALIVE SERVER ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is alive and running!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "server_messages.json"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def copy(ctx):
    await ctx.send("Starting the cloning process. Fetching all messages...")
    all_messages = []
    
    for channel in ctx.guild.text_channels:
        channel_messages = []
        try:
            # oldest_first=True so they paste in the correct chronological order
            async for msg in channel.history(limit=None, oldest_first=True):
                if not msg.content:
                    continue # Skips pure attachments/pics/videos
                
                channel_messages.append({
                    "channel": channel.name,
                    "author_id": str(msg.author.id),
                    "author_name": msg.author.display_name,
                    "author_avatar": msg.author.display_avatar.url if msg.author.display_avatar else None,
                    "content": msg.content,
                    "date_str": msg.created_at.strftime("%m/%d/%Y , %I:%M %p"),
                    "use_webhook": False
                })
            all_messages.extend(channel_messages)
            print(f"Fetched #{channel.name}")
        except Exception as e:
            print(f"Skipped #{channel.name} due to error: {e}")

    # Flag the absolute latest 25 messages per user globally
    user_counts = {}
    for msg in reversed(all_messages):
        uid = msg["author_id"]
        if user_counts.get(uid, 0) < 25:
            msg["use_webhook"] = True
            user_counts[uid] = user_counts.get(uid, 0) + 1

    # Group by channel
    server_data = {}
    for msg in all_messages:
        c = msg["channel"]
        if c not in server_data:
            server_data[c] = []
        server_data[c].append(msg)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(server_data, f, indent=4)
        
    await ctx.send("Copy complete! Data saved. Run `!paste` in the new server immediately.")

@bot.command()
@commands.has_permissions(administrator=True)
async def paste(ctx):
    await ctx.send("Pasting messages as fast as possible relying on discord.py's internal API handler...")
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            server_data = json.load(f)
    except FileNotFoundError:
        return await ctx.send("No copied data found. Run `!copy` first.")

    for channel in ctx.guild.text_channels:
        if channel.name in server_data and server_data[channel.name]:
            print(f"Pasting in #{channel.name}")
            webhook = await channel.create_webhook(name="MessageCloner")
            
            for msg in server_data[channel.name]:
                try:
                    if msg["use_webhook"]:
                        # Webhook for the latest 25 per user
                        await webhook.send(
                            content=msg["content"],
                            username=msg["author_name"],
                            avatar_url=msg["author_avatar"]
                        )
                    else:
                        # User requested exact format: Teleost (12/5/2024 , 6:47 PM) : hi
                        formatted_text = f"{msg['author_name']} ({msg['date_str']}) : {msg['content']}"
                        await channel.send(formatted_text)
                        
                except discord.errors.HTTPException as e:
                    # Fallback just in case Discord API temporarily chokes on the speed
                    print(f"Discord API bottleneck in #{channel.name}: {e}. Pausing briefly...")
                    import asyncio
                    await asyncio.sleep(2) 
                except Exception as e:
                    print(f"Failed message in #{channel.name}: {e}")
            
            await webhook.delete()
            
    await ctx.send("Server completely cloned!")

# Fire up the background server and bot
keep_alive()
bot.run(os.environ.get('DISCORD_TOKEN'))
