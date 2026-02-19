import discord
from discord.ext import commands
import os
import time
from datetime import timedelta
from collections import defaultdict

# --- Bot Setup ---
# We need to enable intents to read messages and member data
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Dictionary for simple anti-spam: tracks timestamps of messages per user
user_messages = defaultdict(list)
# Dictionary for warnings (Note: In a real production bot, use a database like SQLite instead of memory)
user_warnings = defaultdict(int)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')

# --- Anti-Spam Feature ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Anti-spam logic: Check if user sent more than 5 messages in 5 seconds
    author_id = message.author.id
    current_time = time.time()
    user_messages[author_id].append(current_time)
    
    # Filter out messages older than 5 seconds
    user_messages[author_id] = [t for t in user_messages[author_id] if current_time - t < 5]
    
    if len(user_messages[author_id]) > 5:
        await message.delete()
        try:
            await message.author.send("You are sending messages too quickly. Please slow down!")
        except discord.Forbidden:
            pass # User has DMs disabled
        return # Don't process commands if spamming

    # Required to make sure @bot.command() works alongside on_message
    await bot.process_commands(message)

# --- Moderation Commands ---

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    """Kicks a member from the server."""
    await member.kick(reason=reason)
    await ctx.send(f'**{member.name}** has been kicked. Reason: {reason}')

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    """Bans a member from the server."""
    await member.ban(reason=reason)
    await ctx.send(f'**{member.name}** has been banned. Reason: {reason}')

@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, minutes: int, *, reason="No reason provided"):
    """Mutes (timeouts) a member for a specified number of minutes."""
    duration = timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await ctx.send(f'**{member.name}** has been muted for {minutes} minutes. Reason: {reason}')

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    """Deletes a specified number of messages."""
    # amount + 1 to also delete the command message itself
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f'Deleted {len(deleted)-1} messages.', delete_after=5)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    """Locks the current channel so regular members can't send messages."""
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 This channel has been locked.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    """Unlocks the current channel."""
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("🔓 This channel has been unlocked.")

@bot.command()
@commands.has_permissions(kick_members=True)
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    """Issues a warning to a member."""
    user_warnings[member.id] += 1
    warnings_count = user_warnings[member.id]
    
    try:
        await member.send(f"You have been warned in {ctx.guild.name}. Reason: {reason}. You now have {warnings_count} warning(s).")
    except discord.Forbidden:
        await ctx.send(f"Could not DM {member.name}, but the warning was recorded.")
        
    await ctx.send(f"**{member.name}** has been warned. They now have {warnings_count} warning(s).")

@bot.command()
@commands.has_permissions(administrator=True)
async def dm(ctx, member: discord.Member, *, message_content):
    """Sends a direct message to a specific member."""
    try:
        await member.send(message_content)
        await ctx.send(f"Successfully sent a DM to **{member.name}**.")
    except discord.Forbidden:
        await ctx.send(f"Failed to DM **{member.name}**. Their DMs might be closed.")

# --- Error Handling ---
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have permission to use this command!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("You are missing a required argument for this command.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("Could not find that member.")

# --- Start Bot ---
if __name__ == "__main__":
    # Grabs the token from the environment variable set in Render
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN is None:
        print("Error: DISCORD_TOKEN environment variable not set.")
    else:
        bot.run(TOKEN)
