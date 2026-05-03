import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import sys
import time
import asyncio
import traceback
import socket
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv
from aiohttp import web

load_dotenv()
TOKEN   = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = 1497396093506551909

# ── Channel IDs ──────────────────────────────────────────────────────────────
MODERATION_LOG_CHANNEL  = 1497742120080117781
MESSAGE_LOG_CHANNEL     = 1498697496434708593
ROLE_LOG_CHANNEL        = 1498697446778339489
PROMOTE_CHANNEL         = 1497715773676720319
INFRACT_CHANNEL         = 1497716344777478324
LOCKDOWN_CHANNELS       = [1497396094240424099, 1497656322798391337, 1497665979583430828]
APPLICATIONS_CHANNEL    = 1499971385064292472
GRADED_APPS_CHANNEL     = 1499971253665271860

# ── Role IDs ─────────────────────────────────────────────────────────────────
MODERATION_ROLES  = [1497450917576835153,1497451381295026287,1497637066559983718,1497637204758106344,1497647192872194220,1497645398439755978,1497647049112289350]
RANKING_ROLES     = [1497631995923005583,1497650011775832205,1497647192872194220,1497648482452901978,1497651655326568709]
LOCKDOWN_ROLES    = [1497450917576835153,1497451381295026287,1497637066559983718,1497637204758106344,1497651024523952138,1497647192872194220,1497645398439755978]
HISTORY_ROLES     = [1497450917576835153,1497451381295026287,1497638380337500330,1497637204758106344,1497637066559983718]
ADMIN_ROLES       = [1497450917576835153,1497451381295026287]
APPLICATION_ROLES = [1497450917576835153,1497451381295026287,1497637066559983718,1497637204758106344]
BAN_LIMIT_IMMUNE  = [1497450917576835153,1497451381295026287]

# ── Data files ────────────────────────────────────────────────────────────────
USER_DATA_FILE         = "user_data.json"
BAN_TRACKER_FILE       = "ban_tracker.json"
CHANNEL_OVERRIDES_FILE = "channel_overrides.json"
OPEN_APPS_FILE         = "open_applications.json"
WHITELIST_FILE         = "whitelist.json"

APPLICATIONS = {
    "Public Relations": {
        "questions": [
            "What is your Discord username and ID?",
            "What timezone are you in?",
            "How active are you daily from 1-10?",
            "Do you have previous experience in public relations?",
            "What skills would help the public relations team?",
            "Why do you want to join the Zenith PR team?"
        ],
        "role": 1497651516138323968
    },
    "Risk Management": {
        "questions": [
            "What is your Discord username and ID?",
            "What timezone are you in?",
            "How active are you daily from 1-10?",
            "Do you have previous experience in risk management?",
            "What skills would help the risk management team?",
            "Why do you want to join the Zenith Risk Management team?"
        ],
        "role": 1497638380337500330
    },
    "Customer Support": {
        "questions": [
            "What is your Discord username and ID?",
            "What timezone are you in?",
            "How active are you daily from 1-10?",
            "Do you have previous experience in customer support?",
            "What skills would help the customer support team?",
            "Why do you want to join the Zenith Customer Support team?"
        ],
        "role": 1497637827922624662
    }
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg):
    print(msg, flush=True)

def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename) as f:
                return json.load(f)
        except Exception as e:
            log(f"[WARN] Error loading {filename}: {e}")
    return {}

def save_json(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        log(f"[WARN] Error saving {filename}: {e}")

def has_role(member, role_ids):
    if not member or not hasattr(member, "roles"):
        return False
    return any(r.id in role_ids for r in member.roles)

# ── ZenithBot class (events live here so fresh instances inherit them) ────────

class ZenithBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.moderation = True
        super().__init__(command_prefix="/", intents=intents, help_command=None)
        self.synced = False

    async def setup_hook(self):
        log("[SETUP] Loading cogs...")
        for cog in ("cogs.licenses", "cogs.moderation", "cogs.admin"):
            try:
                await self.load_extension(cog)
                log(f"[SETUP] Loaded cog: {cog}")
            except Exception as e:
                log(f"[SETUP] Skipped cog {cog}: {e}")

        log(f"[SETUP] Syncing slash commands to guild {GUILD_ID}...")
        try:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log(f"[SETUP] Synced {len(synced)} commands: {[c.name for c in synced]}")
            self.synced = True
        except Exception as e:
            log(f"[SETUP] Sync failed: {e}")
            traceback.print_exc()

    async def on_ready(self):
        log("=" * 50)
        log(f"[READY] Logged in as {self.user} (ID: {self.user.id})")
        log(f"[READY] Guilds: {[g.name for g in self.guilds]}")
        log(f"[READY] Commands synced: {self.synced}")
        log("=" * 50)
        try:
            await self.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="Zenith Development"
                )
            )
            log("[READY] Status set to ONLINE")
        except Exception as e:
            log(f"[WARN] Could not set status: {e}")

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        try:
            msg = "You don't have permission to use this command." if isinstance(
                error, (app_commands.MissingPermissions, app_commands.MissingAnyRole)
            ) else f"Error: {str(error)[:100]}"
            await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    async def on_message(self, message):
        if message.author == self:
            return
        try:
            wl = load_json(WHITELIST_FILE)
            if str(message.author.id) not in wl:
                if "discord.gg/" in message.content or "discord.com/invite/" in message.content:
                    try:
                        await message.delete()
                        await message.author.send("Invite links are not allowed here.")
                    except Exception:
                        pass
                    return
        except Exception:
            pass
        await self.process_commands(message)

    async def on_message_edit(self, before, after):
        if before.author == self.user:
            return
        try:
            ch = before.guild.get_channel(MESSAGE_LOG_CHANNEL)
            if ch and before.content != after.content:
                embed = discord.Embed(title="Message Edited", color=discord.Color.orange(), timestamp=datetime.now())
                embed.add_field(name="User", value=f"{before.author.mention} ({before.author.id})", inline=False)
                embed.add_field(name="Channel", value=before.channel.mention, inline=False)
                embed.add_field(name="Before", value=before.content[:1024], inline=False)
                embed.add_field(name="After", value=after.content[:1024], inline=False)
                await ch.send(embed=embed)
        except Exception:
            pass

    async def on_message_delete(self, message):
        if message.author == self.user:
            return
        try:
            ch = message.guild.get_channel(MESSAGE_LOG_CHANNEL)
            if ch:
                embed = discord.Embed(title="Message Deleted", color=discord.Color.red(), timestamp=datetime.now())
                embed.add_field(name="User", value=f"{message.author.mention} ({message.author.id})", inline=False)
                embed.add_field(name="Channel", value=message.channel.mention, inline=False)
                embed.add_field(name="Content", value=(message.content[:1024] or "No content"), inline=False)
                await ch.send(embed=embed)
        except Exception:
            pass


# ── Shared moderation helpers ─────────────────────────────────────────────────

async def log_moderation(guild, action, user, moderator, reason="", notes=""):
    try:
        ch = guild.get_channel(MODERATION_LOG_CHANNEL)
        if not ch:
            return
        embed = discord.Embed(title=f"Mod Log — {action}", color=discord.Color.red(), timestamp=datetime.now())
        embed.add_field(name="Action", value=action, inline=False)
        embed.add_field(name="Target", value=f"{user.mention} ({user.id})", inline=False)
        embed.add_field(name="Moderator", value=f"{moderator.mention} ({moderator.id})", inline=False)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        if notes:
            embed.add_field(name="Notes", value=notes, inline=False)
        await ch.send(embed=embed)
    except Exception:
        pass

async def log_role_change(guild, action, user, details=""):
    try:
        ch = guild.get_channel(ROLE_LOG_CHANNEL)
        if not ch:
            return
        embed = discord.Embed(title=f"Role Log — {action}", color=discord.Color.blue(), timestamp=datetime.now())
        embed.add_field(name="Action", value=action, inline=False)
        embed.add_field(name="Target", value=f"{user.mention if isinstance(user, discord.Member) else user}", inline=False)
        if details:
            embed.add_field(name="Details", value=details, inline=False)
        await ch.send(embed=embed)
    except Exception:
        pass

async def add_warning(guild, user, moderator, reason):
    data = load_json(USER_DATA_FILE)
    uid = str(user.id)
    if uid not in data:
        data[uid] = {"warnings": 0, "mutes": [], "history": []}
    data[uid]["warnings"] += 1
    data[uid]["history"].append({"type": "warning", "reason": reason, "moderator": str(moderator.id), "timestamp": datetime.now().isoformat()})
    warnings = data[uid]["warnings"]
    save_json(USER_DATA_FILE, data)
    try:
        await user.send(f"You have received a warning. Reason: {reason}\nTotal: {warnings}/5")
    except Exception:
        pass
    if warnings >= 5:
        try:
            await guild.ban(user, reason="5 warnings reached")
            await log_moderation(guild, "AUTO-BAN", user, guild.me, "5 warnings reached")
        except Exception:
            pass
    return warnings


# ── Command registration (called on each fresh bot instance) ──────────────────

def setup_commands(bot: ZenithBot):

    # ── Moderation ────────────────────────────────────────────────────────────

    @bot.tree.command(name="ban", description="Ban a user from the server")
    @app_commands.describe(user="User to ban", reason="Reason for ban", delete_option="Message deletion: 1d/5d/7d")
    async def ban(interaction: discord.Interaction, user: discord.User, reason: str, delete_option: str = "0"):
        try:
            if not has_role(interaction.user, MODERATION_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return
            wl = load_json(WHITELIST_FILE)
            if str(user.id) in wl:
                await interaction.response.send_message("Cannot moderate whitelisted users.", ephemeral=True); return
            guild = interaction.guild
            bt = load_json(BAN_TRACKER_FILE)
            if not has_role(interaction.user, BAN_LIMIT_IMMUNE):
                now = datetime.now().timestamp()
                key = str(interaction.user.id)
                bt.setdefault(key, [])
                bt[key] = [t for t in bt[key] if now - t < 600]
                if len(bt[key]) >= 3:
                    await interaction.response.send_message("Ban limit reached (3 per 10 min).", ephemeral=True); return
                bt[key].append(now)
                save_json(BAN_TRACKER_FILE, bt)
            days = {"1d": 1, "5d": 5, "7d": 7}.get(delete_option, 0)
            await guild.ban(user, reason=reason, delete_message_days=days)
            try: await user.send(f"You were banned from {guild.name}. Reason: {reason}")
            except Exception: pass
            await log_moderation(guild, "BAN", user, interaction.user, reason, f"Delete days: {days}")
            await interaction.response.send_message(f"Banned {user}.", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    @bot.tree.command(name="mute", description="Mute a user for 1 hour")
    @app_commands.describe(user="User to mute", reason="Reason for mute")
    async def mute(interaction: discord.Interaction, user: discord.User, reason: str):
        try:
            if not has_role(interaction.user, MODERATION_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return
            wl = load_json(WHITELIST_FILE)
            if str(user.id) in wl:
                await interaction.response.send_message("Cannot moderate whitelisted users.", ephemeral=True); return
            guild = interaction.guild
            data = load_json(USER_DATA_FILE)
            uid = str(user.id)
            data.setdefault(uid, {"warnings": 0, "mutes": [], "history": []})
            until = datetime.now() + timedelta(hours=1)
            data[uid]["mutes"].append({"until": until.isoformat(), "reason": reason, "moderator": str(interaction.user.id)})
            data[uid]["history"].append({"type": "mute", "reason": reason, "moderator": str(interaction.user.id), "timestamp": datetime.now().isoformat()})
            save_json(USER_DATA_FILE, data)
            try: await user.send(f"You have been muted in {guild.name} for 1 hour. Reason: {reason}")
            except Exception: pass
            await log_moderation(guild, "MUTE", user, interaction.user, reason)
            await interaction.response.send_message(f"Muted {user}.", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    @bot.tree.command(name="warn", description="Warn a user (5 warnings = auto-ban)")
    @app_commands.describe(user="User to warn", reason="Reason for warning")
    async def warn(interaction: discord.Interaction, user: discord.User, reason: str):
        try:
            if not has_role(interaction.user, MODERATION_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return
            wl = load_json(WHITELIST_FILE)
            if str(user.id) in wl:
                await interaction.response.send_message("Cannot moderate whitelisted users.", ephemeral=True); return
            guild = interaction.guild
            member = await guild.fetch_member(user.id)
            w = await add_warning(guild, member, interaction.user, reason)
            await log_moderation(guild, "WARN", member, interaction.user, reason, f"Warnings: {w}/5")
            await interaction.response.send_message(f"Warned {user}. ({w}/5)", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    # ── Ranking ───────────────────────────────────────────────────────────────

    @bot.tree.command(name="promote", description="Promote a user to a new rank")
    @app_commands.describe(user="User to promote", reason="Reason", new_rank="New role to assign")
    async def promote(interaction: discord.Interaction, user: discord.User, reason: str, new_rank: discord.Role):
        try:
            if not has_role(interaction.user, RANKING_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return
            guild = interaction.guild
            member = await guild.fetch_member(user.id)
            await member.add_roles(new_rank)
            data = load_json(USER_DATA_FILE)
            uid = str(user.id)
            data.setdefault(uid, {"warnings": 0, "mutes": [], "history": []})
            data[uid]["history"].append({"type": "promotion", "new_rank": new_rank.name, "reason": reason, "moderator": str(interaction.user.id), "timestamp": datetime.now().isoformat()})
            save_json(USER_DATA_FILE, data)
            ch = guild.get_channel(PROMOTE_CHANNEL)
            if ch:
                embed = discord.Embed(title="User Promoted", color=discord.Color.green(), timestamp=datetime.now())
                embed.add_field(name="User", value=member.mention, inline=False)
                embed.add_field(name="New Rank", value=new_rank.mention, inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="By", value=interaction.user.mention, inline=False)
                await ch.send(embed=embed, content=member.mention)
            try: await member.send(f"You were promoted to {new_rank.name}! Reason: {reason}")
            except Exception: pass
            await log_role_change(guild, "PROMOTION", member, f"New rank: {new_rank.name}")
            await interaction.response.send_message(f"Promoted {user}.", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    @bot.tree.command(name="infract", description="Infract a user for policy violations")
    @app_commands.describe(user="User", reason="Reason", infraction_type="strike / warning / demotion")
    async def infract(interaction: discord.Interaction, user: discord.User, reason: str, infraction_type: str):
        try:
            if not has_role(interaction.user, RANKING_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return
            guild = interaction.guild
            member = await guild.fetch_member(user.id)
            data = load_json(USER_DATA_FILE)
            uid = str(user.id)
            data.setdefault(uid, {"warnings": 0, "mutes": [], "history": []})
            data[uid]["history"].append({"type": infraction_type, "reason": reason, "moderator": str(interaction.user.id), "timestamp": datetime.now().isoformat()})
            save_json(USER_DATA_FILE, data)
            ch = guild.get_channel(INFRACT_CHANNEL)
            if ch:
                embed = discord.Embed(title=f"User Infracted — {infraction_type.upper()}", color=discord.Color.orange(), timestamp=datetime.now())
                embed.add_field(name="User", value=member.mention, inline=False)
                embed.add_field(name="Type", value=infraction_type, inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="By", value=interaction.user.mention, inline=False)
                await ch.send(embed=embed, content=member.mention)
            try: await member.send(f"You received an infraction ({infraction_type}) in {guild.name}. Reason: {reason}")
            except Exception: pass
            await log_role_change(guild, "INFRACTION", member, f"Type: {infraction_type}")
            await interaction.response.send_message(f"Infracted {user}.", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    @bot.tree.command(name="rank", description="Modify user roles")
    @app_commands.describe(user="User", role_add_1="Add role 1", role_add_2="Add role 2", role_add_3="Add role 3",
                           role_remove_1="Remove role 1", role_remove_2="Remove role 2", role_remove_3="Remove role 3")
    async def rank(interaction: discord.Interaction, user: discord.User,
                   role_add_1: Optional[discord.Role] = None, role_add_2: Optional[discord.Role] = None,
                   role_add_3: Optional[discord.Role] = None, role_remove_1: Optional[discord.Role] = None,
                   role_remove_2: Optional[discord.Role] = None, role_remove_3: Optional[discord.Role] = None):
        try:
            if not has_role(interaction.user, RANKING_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return
            guild = interaction.guild
            member = await guild.fetch_member(user.id)
            added, removed = [], []
            for r in [role_add_1, role_add_2, role_add_3]:
                if r: await member.add_roles(r); added.append(r.mention)
            for r in [role_remove_1, role_remove_2, role_remove_3]:
                if r: await member.remove_roles(r); removed.append(r.mention)
            if not added and not removed:
                await interaction.response.send_message("No roles specified.", ephemeral=True); return
            details = (f"Added: {', '.join(added)}\n" if added else "") + (f"Removed: {', '.join(removed)}" if removed else "")
            await log_role_change(guild, "RANK MODIFICATION", member, details)
            await interaction.response.send_message("Roles updated.", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    # ── Lockdown ──────────────────────────────────────────────────────────────

    @bot.tree.command(name="lock", description="Lock a channel")
    @app_commands.describe(channel="Channel to lock", reason="Reason", time="Duration (optional)")
    async def lock(interaction: discord.Interaction, channel: discord.TextChannel, reason: str, time: str = None):
        try:
            if not has_role(interaction.user, LOCKDOWN_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return
            guild = interaction.guild
            overrides = load_json(CHANNEL_OVERRIDES_FILE)
            cid = str(channel.id)
            overrides.setdefault(cid, {})
            for role, ow in channel.overwrites.items():
                if isinstance(role, discord.Role):
                    overrides[cid][str(role.id)] = {"send": ow.send_messages.value if ow.send_messages else None}
            await channel.set_permissions(guild.default_role, send_messages=False)
            for rid in LOCKDOWN_ROLES:
                r = guild.get_role(rid)
                if r: await channel.set_permissions(r, send_messages=True)
            save_json(CHANNEL_OVERRIDES_FILE, overrides)
            await log_moderation(guild, "CHANNEL LOCK", channel, interaction.user, reason, f"Duration: {time or 'Indefinite'}")
            await interaction.response.send_message(f"Locked {channel.mention}.", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    @bot.tree.command(name="unlock", description="Unlock a channel")
    @app_commands.describe(channel="Channel to unlock", reason="Reason")
    async def unlock(interaction: discord.Interaction, channel: discord.TextChannel, reason: str = ""):
        try:
            if not has_role(interaction.user, LOCKDOWN_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return
            guild = interaction.guild
            overrides = load_json(CHANNEL_OVERRIDES_FILE)
            cid = str(channel.id)
            if cid in overrides:
                for rid_str, perms in overrides[cid].items():
                    r = guild.get_role(int(rid_str))
                    if r: await channel.set_permissions(r, send_messages=perms.get("send"))
                del overrides[cid]
                save_json(CHANNEL_OVERRIDES_FILE, overrides)
            else:
                await channel.set_permissions(guild.default_role, send_messages=True)
            await log_moderation(guild, "CHANNEL UNLOCK", channel, interaction.user, reason)
            await interaction.response.send_message(f"Unlocked {channel.mention}.", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    @bot.tree.command(name="lockdown_start", description="Lock down the entire server")
    @app_commands.describe(reason="Reason")
    async def lockdown_start(interaction: discord.Interaction, reason: str = ""):
        try:
            if not has_role(interaction.user, LOCKDOWN_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return
            guild = interaction.guild
            overrides = load_json(CHANNEL_OVERRIDES_FILE)
            for cid in LOCKDOWN_CHANNELS:
                ch = guild.get_channel(cid)
                if ch:
                    overrides.setdefault(str(cid), {})
                    for role, ow in ch.overwrites.items():
                        if isinstance(role, discord.Role):
                            overrides[str(cid)][str(role.id)] = {"send": ow.send_messages.value if ow.send_messages else None}
                    await ch.set_permissions(guild.default_role, send_messages=False)
                    for rid in LOCKDOWN_ROLES:
                        r = guild.get_role(rid)
                        if r: await ch.set_permissions(r, send_messages=True)
            save_json(CHANNEL_OVERRIDES_FILE, overrides)
            await log_moderation(guild, "LOCKDOWN START", guild, interaction.user, reason)
            await interaction.response.send_message("Server lockdown started.", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    @bot.tree.command(name="lockdown_end", description="End server lockdown")
    @app_commands.describe(reason="Reason")
    async def lockdown_end(interaction: discord.Interaction, reason: str = ""):
        try:
            if not has_role(interaction.user, LOCKDOWN_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return
            guild = interaction.guild
            overrides = load_json(CHANNEL_OVERRIDES_FILE)
            for cid in LOCKDOWN_CHANNELS:
                ch = guild.get_channel(cid)
                if ch:
                    cid_str = str(cid)
                    if cid_str in overrides:
                        for rid_str, perms in overrides[cid_str].items():
                            r = guild.get_role(int(rid_str))
                            if r: await ch.set_permissions(r, send_messages=perms.get("send"))
                        del overrides[cid_str]
                    else:
                        await ch.set_permissions(guild.default_role, send_messages=True)
            save_json(CHANNEL_OVERRIDES_FILE, overrides)
            await log_moderation(guild, "LOCKDOWN END", guild, interaction.user, reason)
            await interaction.response.send_message("Server lockdown ended.", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    # ── History ───────────────────────────────────────────────────────────────

    @bot.tree.command(name="user_history", description="View a user's moderation history")
    @app_commands.describe(user="User to check")
    async def user_history(interaction: discord.Interaction, user: discord.User):
        try:
            if not has_role(interaction.user, HISTORY_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return
            data = load_json(USER_DATA_FILE)
            uid = str(user.id)
            if uid not in data:
                await interaction.response.send_message(f"No history for {user}.", ephemeral=True); return
            d = data[uid]
            embed = discord.Embed(title=f"History — {user}", color=discord.Color.blue(), timestamp=datetime.now())
            embed.add_field(name="Warnings", value=d.get("warnings", 0), inline=True)
            embed.add_field(name="Mutes", value=len(d.get("mutes", [])), inline=True)
            hist = "".join(f"**{e['type'].upper()}** — {e.get('reason','')}\n  *{e['timestamp']}*\n" for e in d.get("history", []))
            embed.add_field(name="History", value=hist[:2048] or "None", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    # ── Applications ──────────────────────────────────────────────────────────

    @bot.tree.command(name="application_channel", description="Open application menu")
    async def application_channel(interaction: discord.Interaction):
        try:
            if not has_role(interaction.user, APPLICATION_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return

            class AppView(discord.ui.View):
                @discord.ui.select(placeholder="Select an application", options=[
                    discord.SelectOption(label="Customer Support", value="Customer Support"),
                    discord.SelectOption(label="Risk Management",  value="Risk Management"),
                    discord.SelectOption(label="Public Relations", value="Public Relations"),
                ])
                async def pick(self, inter: discord.Interaction, sel: discord.ui.Select):
                    name = sel.values[0]
                    apps = load_json(OPEN_APPS_FILE)
                    if not apps.get(name):
                        await inter.response.send_message(f"The {name} application is closed.", ephemeral=True); return
                    await start_application(inter, name, bot)

            await interaction.response.send_message("Select an application:", view=AppView(), ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    @bot.tree.command(name="application_open", description="Open an application for submissions")
    @app_commands.describe(application_name="Application name")
    async def application_open(interaction: discord.Interaction, application_name: str):
        try:
            if not has_role(interaction.user, APPLICATION_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return
            apps = load_json(OPEN_APPS_FILE); apps[application_name] = True; save_json(OPEN_APPS_FILE, apps)
            await interaction.response.send_message(f"{application_name} application opened.", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    @bot.tree.command(name="application_close", description="Close an application")
    @app_commands.describe(application_name="Application name")
    async def application_close(interaction: discord.Interaction, application_name: str):
        try:
            if not has_role(interaction.user, APPLICATION_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return
            apps = load_json(OPEN_APPS_FILE); apps[application_name] = False; save_json(OPEN_APPS_FILE, apps)
            await interaction.response.send_message(f"{application_name} application closed.", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    # ── Whitelist ─────────────────────────────────────────────────────────────

    @bot.tree.command(name="whitelist_add", description="Add user to moderation whitelist")
    @app_commands.describe(user="User to whitelist")
    async def whitelist_add(interaction: discord.Interaction, user: discord.User):
        try:
            if not has_role(interaction.user, ADMIN_ROLES):
                await interaction.response.send_message("Admins only.", ephemeral=True); return
            wl = load_json(WHITELIST_FILE); wl[str(user.id)] = True; save_json(WHITELIST_FILE, wl)
            await log_moderation(interaction.guild, "WHITELIST ADD", user, interaction.user)
            await interaction.response.send_message(f"{user} whitelisted.", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    @bot.tree.command(name="whitelist_remove", description="Remove user from whitelist")
    @app_commands.describe(user="User to remove")
    async def whitelist_remove(interaction: discord.Interaction, user: discord.User):
        try:
            if not has_role(interaction.user, ADMIN_ROLES):
                await interaction.response.send_message("Admins only.", ephemeral=True); return
            wl = load_json(WHITELIST_FILE)
            wl.pop(str(user.id), None)
            save_json(WHITELIST_FILE, wl)
            await log_moderation(interaction.guild, "WHITELIST REMOVE", user, interaction.user)
            await interaction.response.send_message(f"{user} removed from whitelist.", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    # ── Utility ───────────────────────────────────────────────────────────────

    @bot.tree.command(name="say", description="Send a message as the bot")
    @app_commands.describe(channel="Target channel", message="Message text")
    async def say(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
        try:
            if not has_role(interaction.user, RANKING_ROLES):
                await interaction.response.send_message("Your rank is too low.", ephemeral=True); return
            await channel.send(message)
            await log_moderation(interaction.guild, "SAY", channel, interaction.user, f"Message: {message}")
            await interaction.response.send_message(f"Sent to {channel.mention}.", ephemeral=True)
        except Exception as e:
            try: await interaction.response.send_message(f"Error: {str(e)[:100]}", ephemeral=True)
            except Exception: pass

    @bot.tree.command(name="help", description="Show all available commands")
    async def help_cmd(interaction: discord.Interaction):
        embed = discord.Embed(title="Zenith Bot — Commands", color=discord.Color.blue(), timestamp=datetime.now())
        embed.add_field(name="Moderation", value="`/ban` `/mute` `/warn`", inline=False)
        embed.add_field(name="Ranking", value="`/promote` `/infract` `/rank`", inline=False)
        embed.add_field(name="Lockdown", value="`/lock` `/unlock` `/lockdown_start` `/lockdown_end`", inline=False)
        embed.add_field(name="Applications", value="`/application_channel` `/application_open` `/application_close`", inline=False)
        embed.add_field(name="Utility", value="`/user_history` `/whitelist_add` `/whitelist_remove` `/say` `/help` `/status`", inline=False)
        embed.set_footer(text="Zenith Bot v1.4.0")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="status", description="View bot status")
    async def status_cmd(interaction: discord.Interaction):
        embed = discord.Embed(title="Zenith Bot Status", color=discord.Color.green(), timestamp=datetime.now())
        embed.add_field(name="Status", value="Online", inline=True)
        embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Commands Synced", value="Yes" if bot.synced else "Pending", inline=True)
        if interaction.guild:
            embed.add_field(name="Server", value=interaction.guild.name, inline=True)
            embed.add_field(name="Members", value=interaction.guild.member_count, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ── Application flow helpers ──────────────────────────────────────────────────

async def start_application(interaction: discord.Interaction, app_name: str, bot: ZenithBot):
    user = interaction.user
    apps_data = load_json("applications.json")
    app_id = f"{user.id}_{app_name}_{datetime.now().timestamp()}"
    apps_data[app_id] = {"user_id": user.id, "app_name": app_name, "responses": [],
                         "started_at": datetime.now().isoformat(), "status": "in_progress"}
    save_json("applications.json", apps_data)
    await user.send(embed=discord.Embed(title=f"{app_name} Application", description="Expires in 1 hour.", color=discord.Color.blue()))
    await ask_question(user, app_id, 0, bot)

async def ask_question(user: discord.User, app_id: str, idx: int, bot: ZenithBot):
    data = load_json("applications.json")
    if app_id not in data:
        return
    app_name = data[app_id]["app_name"]
    qs = APPLICATIONS[app_name]["questions"]
    if idx >= len(qs):
        await submit_application(user, app_id, bot); return
    await user.send(embed=discord.Embed(title=f"Question {idx+1}/{len(qs)}", description=qs[idx], color=discord.Color.blue()))
    try:
        msg = await bot.wait_for("message", check=lambda m: m.author == user and isinstance(m.channel, discord.DMChannel), timeout=3600)
        data = load_json("applications.json")
        data[app_id]["responses"].append(msg.content)
        save_json("applications.json", data)
        await ask_question(user, app_id, idx + 1, bot)
    except asyncio.TimeoutError:
        data[app_id]["status"] = "expired"
        save_json("applications.json", data)
        await user.send("Your application expired.")

async def submit_application(user: discord.User, app_id: str, bot: ZenithBot):
    data = load_json("applications.json")
    if app_id not in data:
        return
    app_name = data[app_id]["app_name"]
    app_info = APPLICATIONS[app_name]
    embed = discord.Embed(title=f"{app_name} Application", color=discord.Color.gold(), timestamp=datetime.now())
    embed.add_field(name="Applicant", value=f"{user.mention} ({user.id})", inline=False)
    for i, q in enumerate(app_info["questions"]):
        r = data[app_id]["responses"][i] if i < len(data[app_id]["responses"]) else "No response"
        embed.add_field(name=f"Q{i+1}: {q}", value=r[:1024], inline=False)
    guild = bot.get_guild(GUILD_ID)
    if guild:
        ch = guild.get_channel(APPLICATIONS_CHANNEL)
        if ch:
            role = guild.get_role(app_info["role"])

            class ActionView(discord.ui.View):
                @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
                async def accept(self, inter: discord.Interaction, btn: discord.ui.Button):
                    await inter.response.send_modal(AppModal("Accept", user, app_id, True, bot))

                @discord.ui.button(label="Deny", style=discord.ButtonStyle.red)
                async def deny(self, inter: discord.Interaction, btn: discord.ui.Button):
                    await inter.response.send_modal(AppModal("Deny", user, app_id, False, bot))

            msg = await ch.send(embed=embed, content=role.mention if role else "", view=ActionView())
            data[app_id]["pending_message_id"] = msg.id
            data[app_id]["status"] = "pending_review"
            save_json("applications.json", data)
    await user.send(f"Your {app_name} application has been submitted!")

class AppModal(discord.ui.Modal):
    def __init__(self, action, user, app_id, approved, bot):
        super().__init__(title=f"{action} Application")
        self.user = user; self.app_id = app_id; self.approved = approved; self.bot = bot
        self.reason = discord.ui.TextInput(label="Reason", style=discord.TextStyle.long)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        data = load_json("applications.json")
        if self.app_id not in data:
            await interaction.response.send_message("Application not found.", ephemeral=True); return
        app_name = data[self.app_id]["app_name"]
        guild = interaction.guild
        color = discord.Color.green() if self.approved else discord.Color.red()
        result = "ACCEPTED" if self.approved else "DENIED"
        embed = discord.Embed(title=f"{app_name} — {result}", color=color, timestamp=datetime.now())
        embed.add_field(name="Applicant", value=f"{self.user.mention} ({self.user.id})", inline=False)
        embed.add_field(name="Reviewed By", value=interaction.user.mention, inline=False)
        embed.add_field(name="Reason", value=self.reason.value, inline=False)
        graded = guild.get_channel(GRADED_APPS_CHANNEL)
        if graded: await graded.send(embed=embed)
        try: await self.user.send(embed=discord.Embed(title=f"{app_name} Result", description=f"**{result}**\nReason: {self.reason.value}", color=color))
        except Exception: pass
        pending_ch = guild.get_channel(APPLICATIONS_CHANNEL)
        if pending_ch and "pending_message_id" in data[self.app_id]:
            try: m = await pending_ch.fetch_message(data[self.app_id]["pending_message_id"]); await m.delete()
            except Exception: pass
        data[self.app_id]["status"] = "completed"
        data[self.app_id]["result"] = "accepted" if self.approved else "denied"
        save_json("applications.json", data)
        if self.approved:
            member = await guild.fetch_member(self.user.id)
            role_map = {"Risk Management": [1497645064623493142,1497638380337500330,1497639703443148861],
                        "Customer Support": [1497639703443148861,1497637827922624662,1497646855511867442],
                        "Public Relations": [1497651581838037212,1497651516138323968,1497639703443148861]}
            for rid in role_map.get(app_name, []):
                r = guild.get_role(rid)
                if r: await member.add_roles(r)
        await interaction.response.send_message(f"Application {result.lower()}.", ephemeral=True)


# ── Web server ────────────────────────────────────────────────────────────────

async def start_web_server():
    """Start the health check web server with proper socket reuse and error handling."""
    app_web = web.Application()
    
    async def health(req):
        """Simple health check endpoint."""
        return web.Response(text="Zenith Bot OK")
    
    app_web.router.add_get("/", health)
    app_web.router.add_get("/health", health)
    
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app_web)
    
    try:
        await runner.setup()
        
        # Create socket with SO_REUSEADDR to avoid "address already in use"
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            sock.bind(("0.0.0.0", port))
            sock.listen(128)
            log(f"[SERVER] Socket bound to port {port}")
        except OSError as e:
            log(f"[ERROR] Failed to bind socket on port {port}: {e}")
            await runner.cleanup()
            raise
        
        # Create and start the TCP site
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        log(f"[SERVER] Listening on 0.0.0.0:{port} (health check)")
        
    except Exception as e:
        log(f"[ERROR] Web server startup failed: {e}")
        try:
            await runner.cleanup()
        except Exception:
            pass
        raise


# ── Entry point ───────────────────────────────────────────────────────────────

async def run_bot():
    bot = ZenithBot()
    setup_commands(bot)
    await start_web_server()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    log("[START] Zenith Bot initializing...")
    log(f"[START] TOKEN set: {'YES' if TOKEN else 'NO — set DISCORD_TOKEN in Render environment variables!'}")
    log(f"[START] GUILD_ID: {GUILD_ID}")

    if not TOKEN:
        log("[ERROR] Cannot start: DISCORD_TOKEN is missing.")
        log("[ERROR] In Render: go to your service → Environment → Add Variable: DISCORD_TOKEN = your_bot_token")
        sys.exit(1)

    delay = 15
    attempt = 0
    while True:
        attempt += 1
        log(f"[MAIN] Attempt #{attempt}...")
        try:
            asyncio.run(run_bot())
            log("[MAIN] Bot exited cleanly.")
            break

        except discord.LoginFailure:
            log("[ERROR] INVALID TOKEN. Double-check DISCORD_TOKEN in Render → Environment.")
            log("[ERROR] Get your token from: discord.com/developers/applications → Your App → Bot → Reset Token")
            time.sleep(60)

        except discord.HTTPException as e:
            if e.status == 429:
                wait = max(delay, 60)
                try: wait = int(e.response.headers.get("Retry-After", wait))
                except Exception: pass
                log(f"[ERROR] Discord/Cloudflare rate limit (429). Retrying in {wait}s...")
                log("[INFO] If this keeps happening, Render's shared IPs may be blocked.")
                log("[INFO] Fix: switch to Railway.app (free, better IP reputation with Discord)")
                time.sleep(wait)
                delay = min(delay * 2, 300)
            else:
                log(f"[ERROR] HTTP {e.status}: {e}. Retry in {delay}s...")
                time.sleep(delay)
                delay = min(delay * 2, 300)

        except KeyboardInterrupt:
            log("[STOP] Interrupted.")
            break

        except Exception as e:
            log(f"[ERROR] {type(e).__name__}: {e}. Retry in {delay}s...")
            traceback.print_exc()
            time.sleep(delay)
            delay = min(delay * 2, 300)
