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
import sys
import traceback

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = 1497396093506551909

# Verify token exists
if not TOKEN:
    print("[ERROR] DISCORD_TOKEN not found in .env file!", file=sys.stderr)
    print("[ERROR] Add DISCORD_TOKEN=your_token to .env", file=sys.stderr)

# Bot setup with proper intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.moderation = True

print("[INIT] Bot intents configured", file=sys.stderr)

# ── ZenithBot class ────────────────────────────────────────────────────────
class ZenithBot(commands.Bot):
    def __init__(self):
        print("[INIT] Creating ZenithBot instance", file=sys.stderr)
        super().__init__(
            command_prefix="/",
            intents=intents,
            help_command=None,
            sync_commands=True
        )
        self.synced = False
        self.ready_once = False

    async def setup_hook(self):
        """Load extensions and sync slash commands"""
        print("[SETUP] setup_hook() starting", file=sys.stderr)
        
        # Load cogs (optional)
        cogs_to_load = ["cogs.licenses", "cogs.moderation", "cogs.admin"]
        for cog in cogs_to_load:
            try:
                await self.load_extension(cog)
                print(f"[SETUP] ✓ Loaded cog: {cog}", file=sys.stderr)
            except Exception as e:
                print(f"[SETUP] ⚠ Could not load {cog}: {e}", file=sys.stderr)

        # Sync slash commands to guild
        print(f"[SETUP] Syncing commands to guild {GUILD_ID}...", file=sys.stderr)
        try:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"[SETUP] ✓ Synced {len(synced)} slash commands", file=sys.stderr)
            self.synced = True
        except Exception as e:
            print(f"[SETUP] ⚠ Failed to sync commands: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Global error handler for slash commands"""
        try:
            if isinstance(error, app_commands.MissingPermissions):
                await interaction.response.send_message(
                    "❌ You don't have permission to use this command.",
                    ephemeral=True
                )
            elif isinstance(error, app_commands.MissingAnyRole):
                await interaction.response.send_message(
                    "❌ You don't have the required role for this command.",
                    ephemeral=True
                )
            else:
                print(f"[ERROR] Command error: {error}", file=sys.stderr)
                await interaction.response.send_message(
                    f"❌ An error occurred: {str(error)[:100]}",
                    ephemeral=True
                )
        except Exception as e:
            print(f"[ERROR] Error handler failed: {e}", file=sys.stderr)

bot = ZenithBot()

# Channel IDs
MODERATION_LOG_CHANNEL = 1497742120080117781
MESSAGE_LOG_CHANNEL = 1498697496434708593
ROLE_LOG_CHANNEL = 1498697446778339489
PROMOTE_CHANNEL = 1497715773676720319
INFRACT_CHANNEL = 1497716344777478324
LOCKDOWN_CHANNELS = [1497396094240424099, 1497656322798391337, 1497665979583430828]
APPLICATIONS_CHANNEL = 1499971385064292472
GRADED_APPS_CHANNEL = 1499971253665271860

# Application channels
APP_CHANNELS = {
    "Customer Support": 1497637827922624662,
    "Risk Management": 1497638380337500330,
    "Public Relations": 1497651516138323968
}

# Role IDs
MODERATION_ROLES = [1497450917576835153, 1497451381295026287, 1497637066559983718, 1497637204758106344, 1497647192872194220, 1497645398439755978, 1497647049112289350]
RANKING_ROLES = [1497631995923005583, 1497650011775832205, 1497647192872194220, 1497648482452901978, 1497651655326568709]
LOCKDOWN_ROLES = [1497450917576835153, 1497451381295026287, 1497637066559983718, 1497637204758106344, 1497651024523952138, 1497647192872194220, 1497645398439755978]
HISTORY_ROLES = [1497450917576835153, 1497451381295026287, 1497638380337500330, 1497637204758106344, 1497637066559983718]
ADMIN_ROLES = [1497450917576835153, 1497451381295026287]
APPLICATION_ROLES = [1497450917576835153, 1497451381295026287, 1497637066559983718, 1497637204758106344]
BAN_LIMIT_IMMUNE = [1497450917576835153, 1497451381295026287]

# Data files
USER_DATA_FILE = "user_data.json"
BAN_TRACKER_FILE = "ban_tracker.json"
CHANNEL_OVERRIDES_FILE = "channel_overrides.json"
OPEN_APPS_FILE = "open_applications.json"
WHITELIST_FILE = "whitelist.json"

def load_json(filename):
    """Load JSON file safely"""
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Error loading {filename}: {e}", file=sys.stderr)
    return {}

def save_json(filename, data):
    """Save JSON file safely"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"[WARN] Error saving {filename}: {e}", file=sys.stderr)

def has_role(member, role_ids):
    """Check if member has any of the specified roles"""
    if not member or not hasattr(member, 'roles'):
        return False
    return any(role.id in role_ids for role in member.roles)

async def log_moderation(guild, action, user, moderator, reason="", additional_notes=""):
    """Log moderation actions to the designated channel"""
    try:
        channel = guild.get_channel(MODERATION_LOG_CHANNEL)
        if channel:
            embed = discord.Embed(
                title=f"Moderation Log - {action}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Action", value=action, inline=False)
            embed.add_field(name="Target User", value=f"{user.mention} ({user.id})", inline=False)
            embed.add_field(name="Moderator", value=f"{moderator.mention} ({moderator.id})", inline=False)
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            if additional_notes:
                embed.add_field(name="Additional Notes", value=additional_notes, inline=False)
            await channel.send(embed=embed)
    except Exception as e:
        print(f"[WARN] Error logging moderation: {e}", file=sys.stderr)

async def log_role_change(guild, action, user, details=""):
    """Log role and channel changes"""
    try:
        channel = guild.get_channel(ROLE_LOG_CHANNEL)
        if channel:
            embed = discord.Embed(
                title=f"Role/Channel Log - {action}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Action", value=action, inline=False)
            embed.add_field(name="Target", value=f"{user.mention if isinstance(user, discord.Member) else user}", inline=False)
            if details:
                embed.add_field(name="Details", value=details, inline=False)
            await channel.send(embed=embed)
    except Exception as e:
        print(f"[WARN] Error logging role change: {e}", file=sys.stderr)

async def add_warning(guild, user, moderator, reason):
    """Add a warning to a user and handle auto-ban at 5 warnings"""
    user_data = load_json(USER_DATA_FILE)
    user_id = str(user.id)
    
    if user_id not in user_data:
        user_data[user_id] = {"warnings": 0, "mutes": [], "history": []}
    
    user_data[user_id]["warnings"] += 1
    user_data[user_id]["history"].append({
        "type": "warning",
        "reason": reason,
        "moderator": str(moderator.id),
        "timestamp": datetime.now().isoformat()
    })
    
    warnings = user_data[user_id]["warnings"]
    save_json(USER_DATA_FILE, user_data)
    
    try:
        await user.send(f"You have received a warning. Reason: {reason}\nYou now have {warnings}/5 warnings.")
    except:
        pass
    
    if warnings >= 5:
        try:
            await guild.ban(user, reason="Warning limit reached")
            try:
                await user.send(f"You have been automatically banned from {guild.name} due to reaching 5 warnings.")
            except:
                pass
            await log_moderation(guild, "AUTO-BAN", user, guild.me, "Warning limit reached")
        except Exception as e:
            print(f"[WARN] Error auto-banning user: {e}", file=sys.stderr)
    
    return warnings

# ── Bot Events ─────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    """Called when bot is ready and connected to Discord"""
    print("\n" + "="*60, file=sys.stderr)
    print(f"[READY] ✓ Logged in as {bot.user} (ID: {bot.user.id})", file=sys.stderr)
    print(f"[READY] ✓ Bot is ONLINE", file=sys.stderr)
    print(f"[READY] Guilds: {len(bot.guilds)}", file=sys.stderr)
    print(f"[READY] Synced: {bot.synced}", file=sys.stderr)
    
    # List all commands
    try:
        all_commands = await bot.tree.find_commands(None, None)
        print(f"[READY] Commands registered: {len(all_commands)}", file=sys.stderr)
    except:
        pass
    
    print("="*60 + "\n", file=sys.stderr)

    # Update bot status
    try:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Zenith Development"
            )
        )
        print("[READY] ✓ Status set to online", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] Error setting status: {e}", file=sys.stderr)
    
    # Start status loop if not already running
    if not bot.ready_once:
        bot.ready_once = True
        if not update_bot_status.is_running():
            try:
                update_bot_status.start()
                print("[READY] ✓ Status update loop started", file=sys.stderr)
            except Exception as e:
                print(f"[WARN] Error starting status loop: {e}", file=sys.stderr)

@tasks.loop(minutes=5)
async def update_bot_status():
    """Update bot status every 5 minutes"""
    try:
        import random
        activities = [
            discord.Activity(type=discord.ActivityType.watching, name="Zenith Development"),
            discord.Activity(type=discord.ActivityType.listening, name="/help for commands"),
            discord.Activity(type=discord.ActivityType.playing, name="with moderation tools"),
            discord.Activity(type=discord.ActivityType.watching, name=f"{len(bot.guilds)} servers"),
        ]
        
        activity = random.choice(activities)
        await bot.change_presence(status=discord.Status.online, activity=activity)
        print(f"[STATUS] Updated: {activity.name}", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] Error updating status: {e}", file=sys.stderr)

@bot.event
async def on_message(message):
    """Handle message events (invite filtering, etc.)"""
    if message.author == bot.user:
        return
    
    try:
        whitelist = load_json(WHITELIST_FILE)
        is_whitelisted = str(message.author.id) in whitelist
        
        # Filter invite links
        if not is_whitelisted and ("discord.gg/" in message.content or "discord.com/invite/" in message.content):
            try:
                await message.delete()
                await message.author.send("Invite links are not allowed in this server.")
            except:
                pass
            return
    except Exception as e:
        print(f"[WARN] Error in on_message: {e}", file=sys.stderr)
    
    await bot.process_commands(message)

@bot.event
async def on_message_edit(before, after):
    """Log edited messages"""
    if before.author == bot.user:
        return
    
    try:
        channel = before.guild.get_channel(MESSAGE_LOG_CHANNEL)
        if channel and before.content != after.content:
            embed = discord.Embed(
                title="Message Edited",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="User", value=f"{before.author.mention} ({before.author.id})", inline=False)
            embed.add_field(name="Channel", value=before.channel.mention, inline=False)
            embed.add_field(name="Before", value=before.content[:1024], inline=False)
            embed.add_field(name="After", value=after.content[:1024], inline=False)
            await channel.send(embed=embed)
    except Exception as e:
        print(f"[WARN] Error in on_message_edit: {e}", file=sys.stderr)

@bot.event
async def on_message_delete(message):
    """Log deleted messages"""
    if message.author == bot.user:
        return
    
    try:
        channel = message.guild.get_channel(MESSAGE_LOG_CHANNEL)
        if channel:
            embed = discord.Embed(
                title="Message Deleted",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="User", value=f"{message.author.mention} ({message.author.id})", inline=False)
            embed.add_field(name="Channel", value=message.channel.mention, inline=False)
            embed.add_field(name="Content", value=message.content[:1024] if message.content else "No content", inline=False)
            await channel.send(embed=embed)
    except Exception as e:
        print(f"[WARN] Error in on_message_delete: {e}", file=sys.stderr)

# ── Moderation Commands ────────────────────────────────────────────────────

@bot.tree.command(name="ban", description="Ban a user from the server")
@app_commands.describe(user="User to ban", reason="Reason for ban", delete_option="Message deletion period (1d/5d/7d)")
async def ban(interaction: discord.Interaction, user: discord.User, reason: str, delete_option: str = None):
    """Ban a user with optional message history deletion"""
    try:
        if not has_role(interaction.user, MODERATION_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
            return
        
        whitelist = load_json(WHITELIST_FILE)
        if str(user.id) in whitelist:
            await interaction.response.send_message("Cannot moderate whitelisted users.", ephemeral=True)
            return
        
        guild = interaction.guild
        ban_tracker = load_json(BAN_TRACKER_FILE)
        
        # Rate limiting for non-immune users
        if not has_role(interaction.user, BAN_LIMIT_IMMUNE):
            current_time = datetime.now().timestamp()
            tracker_key = str(interaction.user.id)
            
            if tracker_key not in ban_tracker:
                ban_tracker[tracker_key] = []
            
            ban_tracker[tracker_key] = [t for t in ban_tracker[tracker_key] if current_time - t < 600]
            
            if len(ban_tracker[tracker_key]) >= 3:
                await interaction.user.send("Ban limit reached (3 bans per 10 minutes).")
                await interaction.response.send_message("You have reached your ban limit", ephemeral=True)
                return
            
            ban_tracker[tracker_key].append(current_time)
            save_json(BAN_TRACKER_FILE, ban_tracker)
        
        delete_days = {"1d": 1, "5d": 5, "7d": 7}.get(delete_option, 0)
        
        await guild.ban(user, reason=reason, delete_message_days=delete_days)
        
        try:
            await user.send(f"You have been banned from {guild.name}. Reason: {reason}")
        except:
            pass
        
        await log_moderation(guild, "BAN", user, interaction.user, reason, f"Delete messages: {delete_days} days")
        await interaction.response.send_message(f"✓ User {user} has been banned.", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Ban command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="mute", description="Mute a user for 1 hour")
@app_commands.describe(user="User to mute", reason="Reason for mute")
async def mute(interaction: discord.Interaction, user: discord.User, reason: str):
    """Mute a user temporarily"""
    try:
        if not has_role(interaction.user, MODERATION_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
            return
        
        whitelist = load_json(WHITELIST_FILE)
        if str(user.id) in whitelist:
            await interaction.response.send_message("Cannot moderate whitelisted users.", ephemeral=True)
            return
        
        guild = interaction.guild
        user_data = load_json(USER_DATA_FILE)
        user_id = str(user.id)
        
        if user_id not in user_data:
            user_data[user_id] = {"warnings": 0, "mutes": [], "history": []}
        
        mute_until = datetime.now() + timedelta(hours=1)
        user_data[user_id]["mutes"].append({
            "until": mute_until.isoformat(),
            "reason": reason,
            "moderator": str(interaction.user.id)
        })
        user_data[user_id]["history"].append({
            "type": "mute",
            "reason": reason,
            "moderator": str(interaction.user.id),
            "timestamp": datetime.now().isoformat()
        })
        
        save_json(USER_DATA_FILE, user_data)
        
        try:
            await user.send(f"You have been muted in {guild.name} for 1 hour. Reason: {reason}")
        except:
            pass
        
        await log_moderation(guild, "MUTE", user, interaction.user, reason)
        await interaction.response.send_message(f"✓ User {user} has been muted.", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Mute command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="warn", description="Warn a user (5 warnings = auto-ban)")
@app_commands.describe(user="User to warn", reason="Reason for warning")
async def warn(interaction: discord.Interaction, user: discord.User, reason: str):
    """Warn a user"""
    try:
        if not has_role(interaction.user, MODERATION_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
            return
        
        whitelist = load_json(WHITELIST_FILE)
        if str(user.id) in whitelist:
            await interaction.response.send_message("Cannot moderate whitelisted users.", ephemeral=True)
            return
        
        guild = interaction.guild
        member = await guild.fetch_member(user.id)
        
        warnings = await add_warning(guild, member, interaction.user, reason)
        await log_moderation(guild, "WARN", member, interaction.user, reason, f"Total warnings: {warnings}/5")
        await interaction.response.send_message(f"✓ User {user} has been warned. ({warnings}/5)", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Warn command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

# ── Ranking Commands ───────────────────────────────────────────────────────

@bot.tree.command(name="promote", description="Promote a user to a new rank")
@app_commands.describe(user="User to promote", reason="Reason for promotion", new_rank="New rank to assign")
async def promote(interaction: discord.Interaction, user: discord.User, reason: str, new_rank: discord.Role):
    """Promote a user to a new rank"""
    try:
        if not has_role(interaction.user, RANKING_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
            return
        
        guild = interaction.guild
        member = await guild.fetch_member(user.id)
        
        await member.add_roles(new_rank)
        
        user_data = load_json(USER_DATA_FILE)
        user_id = str(user.id)
        
        if user_id not in user_data:
            user_data[user_id] = {"warnings": 0, "mutes": [], "history": []}
        
        user_data[user_id]["history"].append({
            "type": "promotion",
            "new_rank": new_rank.name,
            "reason": reason,
            "moderator": str(interaction.user.id),
            "timestamp": datetime.now().isoformat()
        })
        
        save_json(USER_DATA_FILE, user_data)
        
        channel = guild.get_channel(PROMOTE_CHANNEL)
        if channel:
            embed = discord.Embed(
                title="User Promoted",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="User", value=f"{member.mention}", inline=False)
            embed.add_field(name="New Rank", value=new_rank.mention, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Promoted By", value=interaction.user.mention, inline=False)
            await channel.send(embed=embed, content=member.mention)
        
        try:
            await member.send(f"Congratulations! You have been promoted to {new_rank.mention}!\nReason: {reason}")
        except:
            pass
        
        await log_role_change(guild, "PROMOTION", member, f"New rank: {new_rank.mention}")
        await interaction.response.send_message(f"✓ User {user} has been promoted.", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Promote command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="infract", description="Infract a user for policy violations")
@app_commands.describe(user="User to infract", reason="Reason for infraction", infraction_type="Type: strike, warning, or demotion")
async def infract(interaction: discord.Interaction, user: discord.User, reason: str, infraction_type: str):
    """Infract a user"""
    try:
        if not has_role(interaction.user, RANKING_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
            return
        
        guild = interaction.guild
        member = await guild.fetch_member(user.id)
        
        user_data = load_json(USER_DATA_FILE)
        user_id = str(user.id)
        
        if user_id not in user_data:
            user_data[user_id] = {"warnings": 0, "mutes": [], "history": []}
        
        user_data[user_id]["history"].append({
            "type": infraction_type,
            "reason": reason,
            "moderator": str(interaction.user.id),
            "timestamp": datetime.now().isoformat()
        })
        
        save_json(USER_DATA_FILE, user_data)
        
        channel = guild.get_channel(INFRACT_CHANNEL)
        if channel:
            embed = discord.Embed(
                title=f"User Infracted - {infraction_type.upper()}",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="User", value=f"{member.mention}", inline=False)
            embed.add_field(name="Type", value=infraction_type, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Issued By", value=interaction.user.mention, inline=False)
            await channel.send(embed=embed, content=member.mention)
        
        try:
            await member.send(f"You have received an infraction ({infraction_type}) in {guild.name}.\nReason: {reason}")
        except:
            pass
        
        await log_role_change(guild, "INFRACTION", member, f"Type: {infraction_type}")
        await interaction.response.send_message(f"✓ User {user} has been infracted.", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Infract command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="rank", description="Modify user roles")
@app_commands.describe(
    user="User to modify",
    role_add_1="First role to add (optional)",
    role_add_2="Second role to add (optional)",
    role_add_3="Third role to add (optional)",
    role_remove_1="First role to remove (optional)",
    role_remove_2="Second role to remove (optional)",
    role_remove_3="Third role to remove (optional)"
)
async def rank(
    interaction: discord.Interaction,
    user: discord.User,
    role_add_1: Optional[discord.Role] = None,
    role_add_2: Optional[discord.Role] = None,
    role_add_3: Optional[discord.Role] = None,
    role_remove_1: Optional[discord.Role] = None,
    role_remove_2: Optional[discord.Role] = None,
    role_remove_3: Optional[discord.Role] = None
):
    """Modify user roles in bulk"""
    try:
        if not has_role(interaction.user, RANKING_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
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
        await interaction.response.send_message(f"✓ User {user} roles have been modified.", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Rank command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

# ── Lockdown Commands ──────────────────────────────────────────────────────

@bot.tree.command(name="lock", description="Lock a channel")
@app_commands.describe(channel="Channel to lock", reason="Reason for lock", time="Lock duration (optional)")
async def lock(interaction: discord.Interaction, channel: discord.TextChannel, reason: str, time: str = None):
    """Lock a channel from regular users"""
    try:
        if not has_role(interaction.user, LOCKDOWN_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
            return
        
        guild = interaction.guild
        
        overrides = load_json(CHANNEL_OVERRIDES_FILE)
        channel_id = str(channel.id)
        
        if channel_id not in overrides:
            overrides[channel_id] = {}
        
        # Save current permissions
        for role, overwrite in channel.overwrites.items():
            if isinstance(role, discord.Role):
                overrides[channel_id][str(role.id)] = {
                    "send": overwrite.send_messages.value if overwrite.send_messages else None,
                    "read": overwrite.read_messages.value if overwrite.read_messages else None
                }
        
        # Lock for everyone except mods
        await channel.set_permissions(guild.default_role, send_messages=False)
        
        for role_id in LOCKDOWN_ROLES:
            role = guild.get_role(role_id)
            if role:
                await channel.set_permissions(role, send_messages=True)
        
        save_json(CHANNEL_OVERRIDES_FILE, overrides)
        
        await log_moderation(guild, "CHANNEL LOCK", channel, interaction.user, reason, f"Duration: {time if time else 'Indefinite'}")
        await interaction.response.send_message(f"✓ Channel {channel.mention} has been locked.", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Lock command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="unlock", description="Unlock a channel")
@app_commands.describe(channel="Channel to unlock", reason="Reason for unlock")
async def unlock(interaction: discord.Interaction, channel: discord.TextChannel, reason: str = ""):
    """Unlock a previously locked channel"""
    try:
        if not has_role(interaction.user, LOCKDOWN_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
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
        await interaction.response.send_message(f"✓ Channel {channel.mention} has been unlocked.", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Unlock command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="lockdown_start", description="Lock down the entire server")
@app_commands.describe(reason="Reason for lockdown")
async def lockdown_start(interaction: discord.Interaction, reason: str = ""):
    """Start server-wide lockdown"""
    try:
        if not has_role(interaction.user, LOCKDOWN_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
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
                        overrides[channel_str][str(role.id)] = {
                            "send": overwrite.send_messages.value if overwrite.send_messages else None,
                            "read": overwrite.read_messages.value if overwrite.read_messages else None
                        }
                
                await channel.set_permissions(guild.default_role, send_messages=False)
                
                for role_id in LOCKDOWN_ROLES:
                    role = guild.get_role(role_id)
                    if role:
                        await channel.set_permissions(role, send_messages=True)
        
        save_json(CHANNEL_OVERRIDES_FILE, overrides)
        
        await log_moderation(guild, "LOCKDOWN START", guild, interaction.user, reason)
        await interaction.response.send_message("✓ Server lockdown started.", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Lockdown start command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="lockdown_end", description="End server lockdown")
@app_commands.describe(reason="Reason for unlock")
async def lockdown_end(interaction: discord.Interaction, reason: str = ""):
    """End server-wide lockdown"""
    try:
        if not has_role(interaction.user, LOCKDOWN_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
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
        await interaction.response.send_message("✓ Server lockdown ended.", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Lockdown end command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

# ── User History Command ───────────────────────────────────────────────────

@bot.tree.command(name="user_history", description="View detailed user history")
@app_commands.describe(user="User to check")
async def user_history(interaction: discord.Interaction, user: discord.User):
    """View a user's moderation and activity history"""
    try:
        if not has_role(interaction.user, HISTORY_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
            return
        
        user_data = load_json(USER_DATA_FILE)
        user_id = str(user.id)
        
        if user_id not in user_data:
            await interaction.response.send_message(f"No history found for {user}", ephemeral=True)
            return
        
        data = user_data[user_id]
        
        embed = discord.Embed(
            title=f"User History - {user}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Total Warnings", value=data.get("warnings", 0), inline=True)
        embed.add_field(name="Active Mutes", value=len(data.get("mutes", [])), inline=True)
        
        history_text = ""
        for event in data.get("history", []):
            history_text += f"**{event['type'].upper()}** - {event.get('reason', 'No reason')}\n"
            history_text += f"  *{event['timestamp']}*\n"
        
        if history_text:
            embed.add_field(name="History", value=history_text[:2048], inline=False)
        else:
            embed.add_field(name="History", value="No history recorded", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"[ERROR] User history command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

# ── Application Commands ───────────────────────────────────────────────────

@bot.tree.command(name="application_channel", description="Open application menu")
async def application_channel(interaction: discord.Interaction):
    """Select and start an application"""
    try:
        if not has_role(interaction.user, APPLICATION_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
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
    except Exception as e:
        print(f"[ERROR] Application channel command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="application_open", description="Open an application for submissions")
@app_commands.describe(application_name="Application to open (Customer Support/Risk Management/Public Relations)")
async def application_open(interaction: discord.Interaction, application_name: str):
    """Open an application"""
    try:
        if not has_role(interaction.user, APPLICATION_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
            return
        
        open_apps = load_json(OPEN_APPS_FILE)
        open_apps[application_name] = True
        save_json(OPEN_APPS_FILE, open_apps)
        
        await interaction.response.send_message(f"✓ The {application_name} application is now open.", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Application open command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="application_close", description="Close an application")
@app_commands.describe(application_name="Application to close (Customer Support/Risk Management/Public Relations)")
async def application_close(interaction: discord.Interaction, application_name: str):
    """Close an application"""
    try:
        if not has_role(interaction.user, APPLICATION_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
            return
        
        open_apps = load_json(OPEN_APPS_FILE)
        open_apps[application_name] = False
        save_json(OPEN_APPS_FILE, open_apps)
        
        await interaction.response.send_message(f"✓ The {application_name} application is now closed.", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Application close command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

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
    """Start an application process"""
    user = interaction.user
    
    applications_data = load_json("applications.json")
    app_id = f"{user.id}_{app_name}_{datetime.now().timestamp()}"
    
    applications_data[app_id] = {
        "user_id": user.id,
        "app_name": app_name,
        "responses": [],
        "started_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        "status": "in_progress"
    }
    save_json("applications.json", applications_data)
    
    embed = discord.Embed(
        title=f"{app_name} Application",
        description=f"This application will expire in 1 hour.",
        color=discord.Color.blue()
    )
    await user.send(embed=embed)
    
    await ask_question(user, app_id, 0)

async def ask_question(user: discord.User, app_id: str, question_index: int):
    """Ask the next application question"""
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
    
    embed = discord.Embed(
        title=f"Question {question_index + 1}/{len(app_info['questions'])}",
        description=question,
        color=discord.Color.blue()
    )
    
    msg = await user.send(embed=embed)
    
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
    """Submit an application for review"""
    applications_data = load_json("applications.json")
    
    if app_id not in applications_data:
        return
    
    app_data = applications_data[app_id]
    app_name = app_data["app_name"]
    app_info = APPLICATIONS[app_name]
    
    embed = discord.Embed(
        title=f"{app_name} Application",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Applicant", value=f"{user.mention} ({user.id})", inline=False)
    
    for i, question in enumerate(app_info["questions"]):
        response = app_data["responses"][i] if i < len(app_data["responses"]) else "No response"
        embed.add_field(name=f"Q{i+1}: {question}", value=response, inline=False)
    
    guild = bot.get_guild(GUILD_ID)
    
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
    
    await user.send(f"✓ Your {app_name} application has been submitted for review!")

class AppReasonModal(discord.ui.Modal):
    """Modal for reviewing applications"""
    def __init__(self, action, user, app_id, approved):
        super().__init__(title=f"{action} Application")
        self.action = action
        self.user = user
        self.app_id = app_id
        self.approved = approved
        self.reason = discord.ui.TextInput(label="Reason", style=discord.TextStyle.long)
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            applications_data = load_json("applications.json")
            
            if self.app_id not in applications_data:
                await interaction.response.send_message("Application not found.", ephemeral=True)
                return
            
            app_data = applications_data[self.app_id]
            app_name = app_data["app_name"]
            
            embed = discord.Embed(
                title=f"{app_name} Application - {'ACCEPTED' if self.approved else 'DENIED'}",
                color=discord.Color.green() if self.approved else discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Applicant", value=f"{self.user.mention} ({self.user.id})", inline=False)
            embed.add_field(name="Reviewed By", value=f"{interaction.user.mention}", inline=False)
            embed.add_field(name="Reason", value=self.reason.value, inline=False)
            
            guild = interaction.guild
            graded_channel = guild.get_channel(GRADED_APPS_CHANNEL)
            
            if graded_channel:
                await graded_channel.send(embed=embed)
            
            result_embed = discord.Embed(
                title=f"{app_name} Application Result",
                description=f"Your application has been **{'ACCEPTED' if self.approved else 'DENIED'}**",
                color=discord.Color.green() if self.approved else discord.Color.red()
            )
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
            
            await interaction.response.send_message(f"✓ Application {'accepted' if self.approved else 'denied'}.", ephemeral=True)
        except Exception as e:
            print(f"[ERROR] App reason modal error: {e}", file=sys.stderr)
            await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

# ── Whitelist Commands ─────────────────────────────────────────────────────

@bot.tree.command(name="whitelist_add", description="Add user to whitelist (immune to moderation)")
@app_commands.describe(user="User to whitelist")
async def whitelist_add(interaction: discord.Interaction, user: discord.User):
    """Add a user to the whitelist"""
    try:
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
            
            await interaction.response.send_message(f"✓ User {user} has been added to whitelist.", ephemeral=True)
        else:
            await interaction.response.send_message(f"User {user} is already whitelisted.", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Whitelist add command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

@bot.tree.command(name="whitelist_remove", description="Remove user from whitelist")
@app_commands.describe(user="User to remove from whitelist")
async def whitelist_remove(interaction: discord.Interaction, user: discord.User):
    """Remove a user from the whitelist"""
    try:
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
            
            await interaction.response.send_message(f"✓ User {user} has been removed from whitelist.", ephemeral=True)
        else:
            await interaction.response.send_message(f"User {user} is not whitelisted.", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Whitelist remove command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

# ── Say Command ────────────────────────────────────────────────────────────

@bot.tree.command(name="say", description="Make the bot say a message in a channel")
@app_commands.describe(channel="Channel to send message to", message="Message to send")
async def say(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    """Send a message as the bot"""
    try:
        if not has_role(interaction.user, RANKING_ROLES):
            await interaction.response.send_message("Your rank is too low to execute this command", ephemeral=True)
            return
        
        guild = interaction.guild
        
        await channel.send(message)
        await log_moderation(guild, "SAY COMMAND", channel, interaction.user, f"Message: {message}")
        await interaction.response.send_message(f"✓ Message sent to {channel.mention}", ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Say command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

# ── Help Command ───────────────────────────────────────────────────────────

@bot.tree.command(name="help", description="Display bot commands and features")
async def help_command(interaction: discord.Interaction):
    """Display help information"""
    try:
        embed = discord.Embed(
            title="Zenith Bot - Command Help",
            description="Here are all available slash commands",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📋 Moderation Commands",
            value="`/ban` - Ban a user\n`/mute` - Mute a user\n`/warn` - Warn a user",
            inline=False
        )
        embed.add_field(
            name="📊 Ranking Commands",
            value="`/promote` - Promote a user\n`/infract` - Infract a user\n`/rank` - Modify user roles",
            inline=False
        )
        embed.add_field(
            name="🔒 Lockdown Commands",
            value="`/lock` - Lock a channel\n`/unlock` - Unlock a channel\n`/lockdown_start` - Start server lockdown\n`/lockdown_end` - End server lockdown",
            inline=False
        )
        embed.add_field(
            name="📝 Application Commands",
            value="`/application_channel` - Open application menu\n`/application_open` - Open applications\n`/application_close` - Close applications",
            inline=False
        )
        embed.add_field(
            name="🔍 Utility Commands",
            value="`/user_history` - View user history\n`/whitelist_add` - Whitelist user\n`/whitelist_remove` - Remove from whitelist\n`/say` - Send message as bot\n`/help` - Show this message\n`/status` - Bot status",
            inline=False
        )
        
        embed.set_footer(text="Use /command_name for more information")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Help command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

# ── Status Command ─────────────────────────────────────────────────────────

@bot.tree.command(name="status", description="View bot and server status")
async def status(interaction: discord.Interaction):
    """Display bot and server status"""
    try:
        guild = interaction.guild
        
        embed = discord.Embed(
            title="Zenith Bot Status",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(name="Bot Status", value="🟢 Online", inline=True)
        embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Guilds", value=len(bot.guilds), inline=True)
        
        if guild:
            embed.add_field(name="Server Members", value=guild.member_count, inline=True)
            embed.add_field(name="Server ID", value=guild.id, inline=True)
            embed.add_field(name="Server Name", value=guild.name, inline=True)
        
        embed.add_field(name="Commands Synced", value="✓ Yes" if bot.synced else "⏳ Syncing", inline=True)
        embed.add_field(name="Bot Version", value="v1.3.0", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"[ERROR] Status command error: {e}", file=sys.stderr)
        await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)

# ── Web Server (for Render deployment) ─────────────────────────────────────

async def health_check(request):
    """Health check endpoint"""
    return web.Response(text="Zenith Bot is running ✓")

async def start_web_server():
    """Start web server for deployment"""
    try:
        app = web.Application()
        app.router.add_get("/", health_check)

        port = int(os.environ.get("PORT", 10000))

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, host="0.0.0.0", port=port)
        await site.start()

        print(f"[SERVER] ✓ Web server started on port {port}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Web server error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

# ── Main Bot Startup ───────────────────────────────────────────────────────

async def main():
    """Main bot startup function with auto-reconnect"""
    print("[MAIN] Starting bot startup sequence...", file=sys.stderr)
    
    # Start web server FIRST for Render
    await start_web_server()

    delay = 10
    attempt = 0

    while True:
        attempt += 1
        print(f"[MAIN] Connection attempt #{attempt}...", file=sys.stderr)
        
        try:
            async with bot:
                print("[MAIN] ✓ Starting bot connection...", file=sys.stderr)
                await bot.start(TOKEN)

        except discord.errors.HTTPException as e:
            if e.status == 429:
                print(f"[ERROR] Rate limited. Retrying in {delay}s...", file=sys.stderr)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 300)
            else:
                print(f"[ERROR] HTTP Exception: {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                raise

        except discord.errors.LoginFailure as e:
            print(f"[ERROR] Login failure - check your token: {e}", file=sys.stderr)
            await asyncio.sleep(10)

        except Exception as e:
            print(f"[ERROR] Connection error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 300)

if __name__ == "__main__":
    print("[START] Zenith Bot initializing...", file=sys.stderr)
    
    if not TOKEN or TOKEN == "":
        print("[ERROR] No valid DISCORD_TOKEN set!", file=sys.stderr)
        print("[ERROR] Add DISCORD_TOKEN=your_token to .env file", file=sys.stderr)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[STOP] Bot stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Fatal error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
