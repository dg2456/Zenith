import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
from datetime import datetime, timedelta
import asyncio
from typing import Optional
from dotenv import load_dotenv
from aiohttp import web

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

GUILD_ID = 1497396093506551909

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class ZenithBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="/", intents=intents)

    async def setup_hook(self):
        for cog in ("cogs.licenses", "cogs.moderation", "cogs.admin"):
            try:
                await self.load_extension(cog)
            except Exception as e:
                print(f"[Zenith] Could not load {cog}: {e}")

        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print(f"[Zenith] Synced slash commands to guild {GUILD_ID}")

bot = ZenithBot()

async def health_check(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    print(f"Web server started on port {port}")

MODERATION_LOG_CHANNEL = 1497742120080117781
MESSAGE_LOG_CHANNEL = 1498697496434708593
ROLE_LOG_CHANNEL = 1498697446778339489
PROMOTE_CHANNEL = 1497715773676720319
INFRACT_CHANNEL = 1497716344777478324
LOCKDOWN_CHANNELS = [1497396094240424099, 1497656322798391337, 1497665979583430828]
APPLICATIONS_CHANNEL = 1499971385064292472
GRADED_APPS_CHANNEL = 1499971253665271860

APP_CHANNELS = {
    "Customer Support": 1497637827922624662,
    "Risk Management": 1497638380337500330,
    "Public Relations": 1497651516138323968
}

MODERATION_ROLES = [1497450917576835153, 1497451381295026287, 1497637066559983718, 1497637204758106344, 1497647192872194220, 1497645398439755978, 1497647049112289350]
RANKING_ROLES = [1497631995923005583, 1497650011775832205, 1497647192872194220, 1497648482452901978, 1497651655326568709]
LOCKDOWN_ROLES = [1497450917576835153, 1497451381295026287, 1497637066559983718, 1497637204758106344, 1497651024523952138, 1497647192872194220, 1497645398439755978]
HISTORY_ROLES = [1497450917576835153, 1497451381295026287, 1497638380337500330, 1497637204758106344, 1497637066559983718]
ADMIN_ROLES = [1497450917576835153, 1497451381295026287]
APPLICATION_ROLES = [1497450917576835153, 1497451381295026287, 1497637066559983718, 1497637204758106344]
BAN_LIMIT_IMMUNE = [1497450917576835153, 1497451381295026287]

USER_DATA_FILE = "user_data.json"
BAN_TRACKER_FILE = "ban_tracker.json"
CHANNEL_OVERRIDES_FILE = "channel_overrides.json"
OPEN_APPS_FILE = "open_applications.json"
WHITELIST_FILE = "whitelist.json"

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def has_role(member, role_ids):
    return any(role.id in role_ids for role in member.roles)

async def log_moderation(guild, action, user, moderator, reason="", additional_notes=""):
    channel = guild.get_channel(MODERATION_LOG_CHANNEL)
    if channel:
        embed = discord.Embed(title=f"Moderation Log - {action}", color=discord.Color.red(), timestamp=datetime.now())
        embed.add_field(name="Action", value=action, inline=False)
        embed.add_field(name="Target User", value=f"{user.mention} ({user.id})", inline=False)
        embed.add_field(name="Moderator", value=f"{moderator.mention} ({moderator.id})", inline=False)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        if additional_notes:
            embed.add_field(name="Additional Notes", value=additional_notes, inline=False)
        await channel.send(embed=embed)

async def log_role_change(guild, action, user, details=""):
    channel = guild.get_channel(ROLE_LOG_CHANNEL)
    if channel:
        embed = discord.Embed(title=f"Role/Channel Log - {action}", color=discord.Color.blue(), timestamp=datetime.now())
        embed.add_field(name="Action", value=action, inline=False)
        embed.add_field(name="Target", value=f"{user.mention if isinstance(user, discord.Member) else user}", inline=False)
        if details:
            embed.add_field(name="Details", value=details, inline=False)
        await channel.send(embed=embed)

async def add_warning(guild, user, moderator, reason):
    user_data = load_json(USER_DATA_FILE)
    user_id = str(user.id)
    if user_id not in user_data:
        user_data[user_id] = {"warnings": 0, "mutes": [], "history": []}
    user_data[user_id]["warnings"] += 1
    user_data[user_id]["history"].append({"type": "warning", "reason": reason, "moderator": str(moderator.id), "timestamp": datetime.now().isoformat()})
    warnings = user_data[user_id]["warnings"]
    save_json(USER_DATA_FILE, user_data)
    try:
        await user.send(f"You have received a warning. Reason: {reason}\nYou now have {warnings}/5 warnings.")
    except:
        pass
    if warnings >= 5:
        await guild.ban(user, reason="Warning limit reached")
        try:
            await user.send(f"You have been automatically banned from {guild.name} due to reaching 5 warnings.")
        except:
            pass
        await log_moderation(guild, "AUTO-BAN", user, guild.me, "Warning limit reached")
    return warnings

@bot.event
async def on_ready():
    await asyncio.sleep(2)
    try:
        await bot.tree.sync()
    except discord.errors.HTTPException as e:
        if e.status == 429:
            retry_after = int(e.response.headers.get('Retry-After', 60))
            print(f"Rate limited during sync. Waiting {retry_after} seconds...")
            await asyncio.sleep(retry_after)
            try:
                await bot.tree.sync()
            except Exception as retry_error:
                print(f"Retry failed: {retry_error}")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    print(f"[Zenith] Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Zenith Development"))
    if not hasattr(bot, 'web_server_started'):
        asyncio.create_task(start_web_server())
        bot.web_server_started = True

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    whitelist = load_json(WHITELIST_FILE)
    is_whitelisted = str(message.author.id) in whitelist
    if not is_whitelisted and ("discord.gg/" in message.content or "discord.com/invite/" in message.content):
        await message.delete()
        try:
            await message.author.send("Invite links are not allowed in this server.")
        except:
            pass
        return
    await bot.process_commands(message)

@bot.event
async def on_message_edit(before, after):
    if before.author == bot.user:
        return
    channel = before.guild.get_channel(MESSAGE_LOG_CHANNEL)
    if channel and before.content != after.content:
        embed = discord.Embed(title="Message Edited", color=discord.Color.orange(), timestamp=datetime.now())
        embed.add_field(name="User", value=f"{before.author.mention} ({before.author.id})", inline=False)
        embed.add_field(name="Channel", value=before.channel.mention, inline=False)
        embed.add_field(name="Before", value=before.content[:1024], inline=False)
        embed.add_field(name="After", value=after.content[:1024], inline=False)
        await channel.send(embed=embed)

@bot.event
async def on_message_delete(message):
    if message.author == bot.user:
        return
    channel = message.guild.get_channel(MESSAGE_LOG_CHANNEL)
    if channel:
        embed = discord.Embed(title="Message Deleted", color=discord.Color.red(), timestamp=datetime.now())
        embed.add_field(name="User", value=f"{message.author.mention} ({message.author.id})", inline=False)
        embed.add_field(name="Channel", value=message.channel.mention, inline=False)
        embed.add_field(name="Content", value=message.content[:1024] if message.content else "No content", inline=False)
        await channel.send(embed=embed)

@bot.tree.command(name="ban", description="Ban a user")
@app_commands.describe(user="User to ban", reason="Reason for ban", delete_option="Message deletion period (1d/5d/7d)")
async def ban(interaction: discord.Interaction, user: discord.User, reason: str, delete_option: str = None):
    if not has_role(interaction.user, MODERATION_ROLES):
        await interaction.response.send_message("Rank to low to execute this command", ephemeral=True)
        return
    whitelist = load_json(WHITELIST_FILE)
    if str(user.id) in whitelist:
        await interaction.response.send_message("Cannot moderate whitelisted users.", ephemeral=True)
        return
    guild = interaction.guild
    ban_tracker = load_json(BAN_TRACKER_FILE)
    if not has_role(interaction.user, BAN_LIMIT_IMMUNE):
        current_time = datetime.now().timestamp()
        tracker_key = str(interaction.user.id)
        if tracker_key not in ban_tracker:
            ban_tracker[tracker_key] = []
        ban_tracker[tracker_key] = [t for t in ban_tracker[tracker_key] if current_time - t < 600]
        if len(ban_tracker[tracker_key]) >= 3:
            await interaction.user.send("Ban limit reached (3 bans per 10 minutes). You cannot ban again at this time.")
            await interaction.response.send_message("You have reached your ban limit", ephemeral=True)
            return
        ban_tracker[tracker_key].append(current_time)
        save_json(BAN_TRACKER_FILE, ban_tracker)
        remaining = 3 - len(ban_tracker[tracker_key])
        await interaction.user.send(f"Ban executed. You have {remaining} ban(s) remaining in this 10-minute window.")
    delete_days = 0
    if delete_option == "1d":
        delete_days = 1
    elif delete_option == "5d":
        delete_days = 5
    elif delete_option == "7d":
        delete_days = 7
    await guild.ban(user, reason=reason, delete_message_days=delete_days)
    try:
        await user.send(f"You have been banned from {guild.name}. Reason: {reason}")
    except:
        pass
    await log_moderation(guild, "BAN", user, interaction.user, reason, f"Delete messages: {delete_days} days")
    await interaction.response.send_message(f"User {user} has been banned.", ephemeral=True)

@bot.tree.command(name="mute", description="Mute a user")
@app_commands.describe(user="User to mute", reason="Reason for mute")
async def mute(interaction: discord.Interaction, user: discord.User, reason: str):
    if not has_role(interaction.user, MODERATION_ROLES):
        await interaction.response.send_message("Rank to low to execute this command", ephemeral=True)
        return
    whitelist = load_json(WHITELIST_FILE)
    if str(user.id) in whitelist:
        await interaction.response.send_message("Cannot moderate whitelisted users.", ephemeral=True)
        return
    guild = interaction.guild
    member = await guild.fetch_member(user.id)
    user_data = load_json(USER_DATA_FILE)
    user_id = str(user.id)
    if user_id not in user_data:
        user_data[user_id] = {"warnings": 0, "mutes": [], "history": []}
    mute_until = datetime.now() + timedelta(hours=1)
    user_data[user_id]["mutes"].append({"until": mute_until.isoformat(), "reason": reason, "moderator": str(interaction.user.id)})
    user_data[user_id]["history"].append({"type": "mute", "reason": reason, "moderator": str(interaction.user.id), "timestamp": datetime.now().isoformat()})
    save_json(USER_DATA_FILE, user_data)
    try:
        await user.send(f"You have been muted in {guild.name} for 1 hour. Reason: {reason}")
    except:
        pass
    await log_moderation(guild, "MUTE", user, interaction.user, reason)
    await interaction.response.send_message(f"User {user} has been muted.", ephemeral=True)

@bot.tree.command(name="warn", description="Warn a user")
@app_commands.describe(user="User to warn", reason="Reason for warning")
async def warn(interaction: discord.Interaction, user: discord.User, reason: str):
    if not has_role(interaction.user, MODERATION_ROLES):
        await interaction.response.send_message("Rank to low to execute this command", ephemeral=True)
        return
    whitelist = load_json(WHITELIST_FILE)
    if str(user.id) in whitelist:
        await interaction.response.send_message("Cannot moderate whitelisted users.", ephemeral=True)
        return
    guild = interaction.guild
    member = await guild.fetch_member(user.id)
    warnings = await add_warning(guild, member, interaction.user, reason)
    await log_moderation(guild, "WARN", member, interaction.user, reason, f"Total warnings: {warnings}/5")
    await interaction.response.send_message(f"User {user} has been warned. ({warnings}/5)", ephemeral=True)

@bot.tree.command(name="promote", description="Promote a user")
@app_commands.describe(user="User to promote", reason="Reason for promotion", new_rank="New rank to assign")
async def promote(interaction: discord.Interaction, user: discord.User, reason: str, new_rank: discord.Role):
    if not has_role(interaction.user, RANKING_ROLES):
        await interaction.response.send_message("Rank to low to execute this command", ephemeral=True)
        return
    guild = interaction.guild
    member = await guild.fetch_member(user.id)
    await member.add_roles(new_rank)
    user_data = load_json(USER_DATA_FILE)
    user_id = str(user.id)
    if user_id not in user_data:
        user_data[user_id] = {"warnings": 0, "mutes": [], "history": []}
    user_data[user_id]["history"].append({"type": "promotion", "new_rank": new_rank.name, "reason": reason, "moderator": str(interaction.user.id), "timestamp": datetime.now().isoformat()})
    save_json(USER_DATA_FILE, user_data)
    channel = guild.get_channel(PROMOTE_CHANNEL)
    if channel:
        embed = discord.Embed(title="User Promoted", color=discord.Color.green(), timestamp=datetime.now())
        embed.add_field(name="User", value=f"{member.mention}", inline=False)
        embed.add_field(name="New Rank", value=new_rank.mention, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Promoted By", value=interaction.user.mention, inline=False)
        await channel.send(embed=embed, content=member.mention)
    try:
        await member.send(f"You have been promoted to {new_rank.mention}! Reason: {reason}")
    except:
        pass
    await log_role_change(guild, "PROMOTION", member, f"New rank: {new_rank.mention}")
    await interaction.response.send_message(f"User {user} has been promoted.", ephemeral=True)

@bot.tree.command(name="infract", description="Infract a user")
@app_commands.describe(user="User to infract", reason="Reason for infraction", infraction_type="Type: strike, warning, or demotion")
async def infract(interaction: discord.Interaction, user: discord.User, reason: str, infraction_type: str):
    if not has_role(interaction.user, RANKING_ROLES):
        await interaction.response.send_message("Rank to low to execute this command", ephemeral=True)
        return
    guild = interaction.guild
    member = await guild.fetch_member(user.id)
    user_data = load_json(USER_DATA_FILE)
    user_id = str(user.id)
    if user_id not in user_data:
        user_data[user_id] = {"warnings": 0, "mutes": [], "history": []}
    user_data[user_id]["history"].append({"type": infraction_type, "reason": reason, "moderator": str(interaction.user.id), "timestamp": datetime.now().isoformat()})
    save_json(USER_DATA_FILE, user_data)
    channel = guild.get_channel(INFRACT_CHANNEL)
    if channel:
        embed = discord.Embed(title=f"User Infracted - {infraction_type.upper()}", color=discord.Color.orange(), timestamp=datetime.now())
        embed.add_field(name="User", value=f"{member.mention}", inline=False)
        embed.add_field(name="Type", value=infraction_type, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Issued By", value=interaction.user.mention, inline=False)
        await channel.send(embed=embed, content=member.mention)
    try:
        await member.send(f"You have received an infraction ({infraction_type}) in {guild.name}. Reason: {reason}")
    except:
        pass
    await log_role_change(guild, "INFRACTION", member, f"Type: {infraction_type}")
    await interaction.response.send_message(f"User {user} has been infracted.", ephemeral=True)

@bot.tree.command(name="rank", description="Modify user roles")
@app_commands.describe(user="User to modify", role_add_1="First role to add (optional)", role_add_2="Second role to add (optional)", role_add_3="Third role to add (optional)", role_remove_1="First role to remove (optional)", role_remove_2="Second role to remove (optional)", role_remove_3="Third role to remove (optional)")
async def rank(interaction: discord.Interaction, user: discord.User, role_add_1: Optional[discord.Role] = None, role_add_2: Optional[discord.Role] = None, role_add_3: Optional[discord.Role] = None, role_remove_1: Optional[discord.Role] = None, role_remove_2: Optional[discord.Role] = None, role_remove_3: Optional[discord.Role] = None):
    if not has_role(interaction.user, RANKING_ROLES):
        await interaction.response.send_message("Rank to low to execute this command", ephemeral=True)
        return
    guild = interaction.guild
    member = await guild.fetch_member(user.id)
    roles_added = []
    roles_removed = []
    for role in [role_add_1, role_add_2, role_add_3]:
        if role:
            await member.add_roles(role)
            roles_added.append(role.mention)
    for role in [role_remove_1, role_remove_2, role_remove_3]:
        if role:
            await member.remove_roles(role)
            roles_removed.append(role.mention)
    if not roles_added and not roles_removed:
        await interaction.response.send_message("No roles were specified to add or remove.", ephemeral=True)
        return
    details = ""
    if roles_added:
        details += f"Added: {', '.join(roles_added)}\n"
    if roles_removed:
        details += f"Removed: {', '.join(roles_removed)}"
    await log_role_change(guild, "RANK MODIFICATION", member, details)
    await interaction.response.send_message(f"User {user} roles have been modified.", ephemeral=True)

@bot.tree.command(name="lock", description="Lock a channel")
@app_commands.describe(channel="Channel to lock", reason="Reason for lock", time="Lock duration (optional)")
async def lock(interaction: discord.Interaction, channel: discord.TextChannel, reason: str, time: str = None):
    if not has_role(interaction.user, LOCKDOWN_ROLES):
        await interaction.response.send_message("Rank to low to execute this command", ephemeral=True)
        return
    guild = interaction.guild
    overrides = load_json(CHANNEL_OVERRIDES_FILE)
    channel_id = str(channel.id)
    if channel_id not in overrides:
        overrides[channel_id] = {}
    for role, overwrite in channel.overwrites.items():
        if isinstance(role, discord.Role):
            overrides[channel_id][str(role.id)] = {"send": overwrite.send_messages.value if overwrite.send_messages else None, "read": overwrite.read_messages.value if overwrite.read_messages else None}
    await channel.set_permissions(guild.default_role, send_messages=False)
    for role_id in LOCKDOWN_ROLES:
        role = guild.get_role(role_id)
        if role:
            await channel.set_permissions(role, send_messages=True)
    save_json(CHANNEL_OVERRIDES_FILE, overrides)
    await log_moderation(guild, "CHANNEL LOCK", channel, interaction.user, reason, f"Duration: {time if time else 'Indefinite'}")
    await interaction.response.send_message(f"Channel {channel.mention} has been locked.", ephemeral=True)

@bot.tree.command(name="unlock", description="Unlock a channel")
@app_commands.describe(channel="Channel to unlock", reason="Reason for unlock")
async def unlock(interaction: discord.Interaction, channel: discord.TextChannel, reason: str = ""):
    if not has_role(interaction.user, LOCKDOWN_ROLES):
        await interaction.response.send_message("Rank to low to execute this command", ephemeral=True)
        return
    guild = interaction.guild
    overrides = load_json(CHANNEL_OVERRIDES_FILE)
    channel_id = str(channel.id)
    if channel_id in overrides:
        for role_id_str, perms in overrides[channel_id].items():
            role = guild.get_role(int(role_id_str))
            if role:
                await channel.set_permissions(role, send_messages=perms.get("send"))
        del overrides[channel_id]
        save_json(CHANNEL_OVERRIDES_FILE, overrides)
    else:
        await channel.set_permissions(guild.default_role, send_messages=True)
    await log_moderation(guild, "CHANNEL UNLOCK", channel, interaction.user, reason)
    await interaction.response.send_message(f"Channel {channel.mention} has been unlocked.", ephemeral=True)

@bot.tree.command(name="lockdown_start", description="Start server lockdown")
@app_commands.describe(reason="Reason for lockdown")
async def lockdown_start(interaction: discord.Interaction, reason: str = ""):
    if not has_role(interaction.user, LOCKDOWN_ROLES):
        await interaction.response.send_message("Rank to low to execute this command", ephemeral=True)
        return
    guild = interaction.guild
    overrides = load_json(CHANNEL_OVERRIDES_FILE)
    for channel_id in LOCKDOWN_CHANNELS:
        channel = guild.get_channel(channel_id)
        if channel:
            channel_str = str(channel_id)
            if channel_str not in overrides:
                overrides[channel_str] = {}
            for role, overwrite in channel.overwrites.items():
                if isinstance(role, discord.Role):
                    overrides[channel_str][str(role.id)] = {"send": overwrite.send_messages.value if overwrite.send_messages else None, "read": overwrite.read_messages.value if overwrite.read_messages else None}
            await channel.set_permissions(guild.default_role, send_messages=False)
            for role_id in LOCKDOWN_ROLES:
                role = guild.get_role(role_id)
                if role:
                    await channel.set_permissions(role, send_messages=True)
    save_json(CHANNEL_OVERRIDES_FILE, overrides)
    await log_moderation(guild, "LOCKDOWN START", guild, interaction.user, reason)
    await interaction.response.send_message("Server lockdown started.", ephemeral=True)

@bot.tree.command(name="lockdown_end", description="End server lockdown")
@app_commands.describe(reason="Reason for unlock")
async def lockdown_end(interaction: discord.Interaction, reason: str = ""):
    if not has_role(interaction.user, LOCKDOWN_ROLES):
        await interaction.response.send_message("Rank to low to execute this command", ephemeral=True)
        return
    guild = interaction.guild
    overrides = load_json(CHANNEL_OVERRIDES_FILE)
    for channel_id in LOCKDOWN_CHANNELS:
        channel = guild.get_channel(channel_id)
        if channel:
            channel_str = str(channel_id)
            if channel_str in overrides:
                for role_id_str, perms in overrides[channel_str].items():
                    role = guild.get_role(int(role_id_str))
                    if role:
                        await channel.set_permissions(role, send_messages=perms.get("send"))
                del overrides[channel_str]
            else:
                await channel.set_permissions(guild.default_role, send_messages=True)
    save_json(CHANNEL_OVERRIDES_FILE, overrides)
    await log_moderation(guild, "LOCKDOWN END", guild, interaction.user, reason)
    await interaction.response.send_message("Server lockdown ended.", ephemeral=True)

@bot.tree.command(name="user_history", description="View user history")
@app_commands.describe(user="User to check")
async def user_history(interaction: discord.Interaction, user: discord.User):
    if not has_role(interaction.user, HISTORY_ROLES):
        await interaction.response.send_message("Rank to low to execute this command", ephemeral=True)
        return
    user_data = load_json(USER_DATA_FILE)
    user_id = str(user.id)
    if user_id not in user_data:
        await interaction.response.send_message(f"No history found for {user}", ephemeral=True)
        return
    data = user_data[user_id]
    embed = discord.Embed(title=f"User History - {user}", color=discord.Color.blue(), timestamp=datetime.now())
    embed.add_field(name="Total Warnings", value=data.get("warnings", 0), inline=True)
    embed.add_field(name="Active Mutes", value=len(data.get("mutes", [])), inline=True)
    history_text = ""
    for event in data.get("history", []):
        history_text += f"**{event['type'].upper()}** - {event.get('reason', 'No reason')}\n"
        history_text += f"  *{event['timestamp']}*\n"
    if history_text:
        embed.add_field(name="History", value=history_text[:2048], inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="application_channel", description="Open application menu")
async def application_channel(interaction: discord.Interaction):
    if not has_role(interaction.user, APPLICATION_ROLES):
        await interaction.response.send_message("Rank to low to execute this command", ephemeral=True)
        return
    class AppSelectView(discord.ui.View):
        @discord.ui.select(
            placeholder="Select an application",
            options=[
                discord.SelectOption(label="Customer Support", value="Customer Support"),
                discord.SelectOption(label="Risk Management", value="Risk Management"),
                discord.SelectOption(label="Public Relations", value="Public Relations")
            ]
        )
        async def select_app(self, interaction: discord.Interaction, select: discord.ui.Select):
            selected = select.values[0]
            open_apps = load_json(OPEN_APPS_FILE)
            if selected not in open_apps or not open_apps[selected]:
                await interaction.response.send_message(f"The {selected} application is currently closed.", ephemeral=True)
                return
            await start_application(interaction, selected)
    view = AppSelectView()
    await interaction.response.send_message("Select an application:", view=view, ephemeral=True)

@bot.tree.command(name="application_open", description="Open an application")
@app_commands.describe(application_name="Application to open (Customer Support/Risk Management/Public Relations)")
async def application_open(interaction: discord.Interaction, application_name: str):
    if not has_role(interaction.user, APPLICATION_ROLES):
        await interaction.response.send_message("Rank to low to execute this command", ephemeral=True)
        return
    open_apps = load_json(OPEN_APPS_FILE)
    open_apps[application_name] = True
    save_json(OPEN_APPS_FILE, open_apps)
    await interaction.response.send_message(f"The {application_name} application is now open.", ephemeral=True)

@bot.tree.command(name="application_close", description="Close an application")
@app_commands.describe(application_name="Application to close (Customer Support/Risk Management/Public Relations)")
async def application_close(interaction: discord.Interaction, application_name: str):
    if not has_role(interaction.user, APPLICATION_ROLES):
        await interaction.response.send_message("Rank to low to execute this command", ephemeral=True)
        return
    open_apps = load_json(OPEN_APPS_FILE)
    open_apps[application_name] = False
    save_json(OPEN_APPS_FILE, open_apps)
    await interaction.response.send_message(f"The {application_name} application is now closed.", ephemeral=True)

APPLICATIONS = {
    "Public Relations": {
        "questions": [
            "What is your Discord username and ID?",
            "What timezone are you in?",
            "How active are you daily from a 1 being never active to 10 being super active?",
            "Do you have any previous experience in public relations? If yes, explain.",
            "What skills do you have that would help the public relations team?",
            "Why do you want to join the Zenith Development public relations team?"
        ],
        "role": 1497651516138323968
    },
    "Risk Management": {
        "questions": [
            "What is your Discord username and ID?",
            "What timezone are you in?",
            "How active are you daily from a 1 being never active to 10 being super active?",
            "Do you have any previous experience in risk management? If yes, explain.",
            "What skills do you have that would help the risk management team?",
            "Why do you want to join the Zenith Development risk management team?"
        ],
        "role": 1497638380337500330
    },
    "Customer Support": {
        "questions": [
            "What is your Discord username and ID?",
            "What timezone are you in?",
            "How active are you daily from a 1 being never active to 10 being super active?",
            "Do you have any previous experience in customer support? If yes, explain.",
            "What skills do you have that would help the customer support team?",
            "Why do you want to join the Zenith Development customer support team?"
        ],
        "role": 1497637827922624662
    }
}

async def start_application(interaction: discord.Interaction, app_name: str):
    user = interaction.user
    applications_data = load_json("applications.json")
    app_id = f"{user.id}_{app_name}_{datetime.now().timestamp()}"
    applications_data[app_id] = {"user_id": user.id, "app_name": app_name, "responses": [], "started_at": datetime.now().isoformat(), "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(), "status": "in_progress"}
    save_json("applications.json", applications_data)
    embed = discord.Embed(title=app_name, description="This application will expire in 1 hour.", color=discord.Color.blue())
    await user.send(embed=embed)
    await ask_question(user, app_id, 0)

async def ask_question(user: discord.User, app_id: str, question_index: int):
    applications_data = load_json("applications.json")
    if app_id not in applications_data:
        return
    app_data = applications_data[app_id]
    app_name = app_data["app_name"]
    app_info = APPLICATIONS[app_name]
    if question_index >= len(app_info["questions"]):
        await submit_application(user, app_id)
        return
    question = app_info["questions"][question_index]
    embed = discord.Embed(title=f"Question {question_index + 1}/{len(app_info['questions'])}", description=question, color=discord.Color.blue())
    await user.send(embed=embed)
    def check(m):
        return m.author == user and isinstance(m.channel, discord.DMChannel)
    try:
        response = await bot.wait_for('message', check=check, timeout=3600)
        app_data["responses"].append(response.content)
        save_json("applications.json", applications_data)
        await ask_question(user, app_id, question_index + 1)
    except asyncio.TimeoutError:
        await user.send("Your application has expired.")
        app_data["status"] = "expired"
        save_json("applications.json", applications_data)

async def submit_application(user: discord.User, app_id: str):
    applications_data = load_json("applications.json")
    if app_id not in applications_data:
        return
    app_data = applications_data[app_id]
    app_name = app_data["app_name"]
    app_info = APPLICATIONS[app_name]
    embed = discord.Embed(title=f"{app_name} Application", color=discord.Color.gold(), timestamp=datetime.now())
    embed.add_field(name="Applicant", value=f"{user.mention} ({user.id})", inline=False)
    for i, question in enumerate(app_info["questions"]):
        response = app_data["responses"][i] if i < len(app_data["responses"]) else "No response"
        embed.add_field(name=f"Q{i+1}: {question}", value=response, inline=False)
    guild = bot.get_guild(list(bot.guilds)[0].id) if bot.guilds else None
    if guild:
        pending_channel = guild.get_channel(APPLICATIONS_CHANNEL)
        if pending_channel:
            role = guild.get_role(app_info["role"])
            class AppActionView(discord.ui.View):
                @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
                async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
                    modal = AppReasonModal("Accept", user, app_id, True)
                    await interaction.response.send_modal(modal)
                @discord.ui.button(label="Deny", style=discord.ButtonStyle.red)
                async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
                    modal = AppReasonModal("Deny", user, app_id, False)
                    await interaction.response.send_modal(modal)
            view = AppActionView()
            msg = await pending_channel.send(embed=embed, content=role.mention if role else "", view=view)
            app_data["pending_message_id"] = msg.id
            app_data["status"] = "pending_review"
            save_json("applications.json", applications_data)
    await user.send(f"Your {app_name} application has been submitted for review!")

class AppReasonModal(discord.ui.Modal):
    def __init__(self, action, user, app_id, approved):
        super().__init__(title=f"{action} Application")
        self.action = action
        self.user = user
        self.app_id = app_id
        self.approved = approved
        self.reason = discord.ui.TextInput(label="Reason", style=discord.TextStyle.long)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        applications_data = load_json("applications.json")
        if self.app_id not in applications_data:
            await interaction.response.send_message("Application not found.", ephemeral=True)
            return
        app_data = applications_data[self.app_id]
        app_name = app_data["app_name"]
        embed = discord.Embed(title=f"{app_name} Application - {'ACCEPTED' if self.approved else 'DENIED'}", color=discord.Color.green() if self.approved else discord.Color.red(), timestamp=datetime.now())
        embed.add_field(name="Applicant", value=f"{self.user.mention} ({self.user.id})", inline=False)
        embed.add_field(name="Reviewed By", value=f"{interaction.user.mention}", inline=False)
        embed.add_field(name="Reason", value=self.reason.value, inline=False)
        guild = interaction.guild
        graded_channel = guild.get_channel(GRADED_APPS_CHANNEL)
        if graded_channel:
            await graded_channel.send(embed=embed)
        result_embed = discord.Embed(title=f"{app_name} Application Result", description=f"Your application has been **{'ACCEPTED' if self.approved else 'DENIED'}**", color=discord.Color.green() if self.approved else discord.Color.red())
        result_embed.add_field(name="Reason", value=self.reason.value, inline=False)
        try:
            await self.user.send(embed=result_embed)
        except:
            pass
        pending_channel = guild.get_channel(APPLICATIONS_CHANNEL)
        if pending_channel and "pending_message_id" in app_data:
            try:
                msg = await pending_channel.fetch_message(app_data["pending_message_id"])
                await msg.delete()
            except:
                pass
        app_data["status"] = "completed"
        app_data["result"] = "accepted" if self.approved else "denied"
        save_json("applications.json", applications_data)
        if self.approved:
            guild = interaction.guild
            member = await guild.fetch_member(self.user.id)
            role_mappings = {
                "Risk Management": [1497645064623493142, 1497638380337500330, 1497639703443148861],
                "Customer Support": [1497639703443148861, 1497637827922624662, 1497646855511867442],
                "Public Relations": [1497651581838037212, 1497651516138323968, 1497639703443148861]
            }
            roles_to_add = role_mappings.get(app_name, [])
            for role_id in roles_to_add:
                role = guild.get_role(role_id)
                if role:
                    await member.add_roles(role)
        await interaction.response.send_message(f"Application {'accepted' if self.approved else 'denied'}.", ephemeral=True)

@bot.tree.command(name="whitelist_add", description="Add user to whitelist (immune to moderation)")
@app_commands.describe(user="User to whitelist")
async def whitelist_add(interaction: discord.Interaction, user: discord.User):
    if not has_role(interaction.user, ADMIN_ROLES):
        await interaction.response.send_message("Only admins can use this command", ephemeral=True)
        return
    whitelist = load_json(WHITELIST_FILE)
    user_id = str(user.id)
    if user_id not in whitelist:
        whitelist[user_id] = True
        save_json(WHITELIST_FILE, whitelist)
        guild = interaction.guild
        await log_moderation(guild, "WHITELIST ADD", user, interaction.user, "User added to whitelist")
        await interaction.response.send_message(f"User {user} has been added to whitelist.", ephemeral=True)
    else:
        await interaction.response.send_message(f"User {user} is already whitelisted.", ephemeral=True)

@bot.tree.command(name="whitelist_remove", description="Remove user from whitelist")
@app_commands.describe(user="User to remove from whitelist")
async def whitelist_remove(interaction: discord.Interaction, user: discord.User):
    if not has_role(interaction.user, ADMIN_ROLES):
        await interaction.response.send_message("Only admins can use this command", ephemeral=True)
        return
    whitelist = load_json(WHITELIST_FILE)
    user_id = str(user.id)
    if user_id in whitelist:
        del whitelist[user_id]
        save_json(WHITELIST_FILE, whitelist)
        guild = interaction.guild
        await log_moderation(guild, "WHITELIST REMOVE", user, interaction.user, "User removed from whitelist")
        await interaction.response.send_message(f"User {user} has been removed from whitelist.", ephemeral=True)
    else:
        await interaction.response.send_message(f"User {user} is not whitelisted.", ephemeral=True)

@bot.tree.command(name="say", description="Make the bot say a message in a channel")
@app_commands.describe(channel="Channel to send message to", message="Message to send")
async def say(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    if not has_role(interaction.user, RANKING_ROLES):
        await interaction.response.send_message("Rank too low to execute this command", ephemeral=True)
        return
    guild = interaction.guild
    try:
        await channel.send(message)
        await log_moderation(guild, "SAY COMMAND", channel, interaction.user, f"Message: {message}")
        await interaction.response.send_message(f"Message sent to {channel.mention}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Failed to send message: {str(e)}", ephemeral=True)

# ── Run ────────────────────────────────────────────────────────────────────

async def main():
    delay = 10
    while True:
        try:
            async with bot:
                await bot.start(TOKEN)
        except discord.errors.HTTPException as e:
            if e.status == 429:
                print(f"[Zenith] Rate limited by Discord/Cloudflare. Retrying in {delay}s..." **...**

_This response is too long to display in full._
