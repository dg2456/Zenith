"""
moderation.py — automatic Zenith sync listeners

Events handled:
  on_member_update  → role changes synced to Zenith via /api/discord/role-sync
  on_member_ban     → ban synced to Zenith via /api/discord/ban-sync
"""

import os
import discord
from discord.ext import commands
import aiohttp
from config import GUILD_ID, MOD_LOG_CHANNEL_ID

API_URL    = os.getenv("ZENITH_API_URL", "").rstrip("/")
BOT_SECRET = os.getenv("DISCORD_BOT_SECRET", "")

HEADERS = {
    "Content-Type": "application/json",
    "x-bot-secret": BOT_SECRET,
}


async def _post(url: str, payload: dict) -> tuple[int, dict]:
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.post(url, json=payload) as resp:
            try:
                body = await resp.json()
            except Exception:
                body = {}
            return resp.status, body


async def _send_mod_log(bot: commands.Bot, embed: discord.Embed):
    try:
        channel = bot.get_channel(MOD_LOG_CHANNEL_ID)
        if channel:
            await channel.send(embed=embed)
    except Exception:
        pass


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Role change → sync to Zenith ──────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.guild.id != GUILD_ID:
            return
        if before.roles == after.roles:
            return
        if not API_URL:
            return

        role_ids = [str(r.id) for r in after.roles]
        status, data = await _post(
            f"{API_URL}/api/discord/role-sync",
            {"discordId": str(after.id), "roleIds": role_ids},
        )

        if status == 200 and data.get("role"):
            new_role = data["role"]
            embed = discord.Embed(
                title="🔄 Role Synced",
                description=f"{after.mention} → Zenith role updated to **{new_role.replace('_', ' ').title()}**",
                color=discord.Color.blurple(),
            )
            embed.set_footer(text=f"Discord ID: {after.id}")
            await _send_mod_log(self.bot, embed)

    # ── Member banned from Discord → ban on Zenith ────────────────────────
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        if guild.id != GUILD_ID:
            return
        if not API_URL:
            return

        reason = "Banned from Discord server"
        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=5):
                if entry.target.id == user.id:
                    reason = entry.reason or reason
                    break
        except discord.Forbidden:
            pass

        status, data = await _post(
            f"{API_URL}/api/discord/ban-sync",
            {"discordId": str(user.id), "reason": reason},
        )

        embed = discord.Embed(
            title="🔨 Ban Synced to Zenith" if status == 200 else "⚠️ Ban Sync — No Linked Account",
            color=discord.Color.red() if status == 200 else discord.Color.orange(),
        )
        embed.add_field(name="User",   value=f"{user} (`{user.id}`)", inline=True)
        embed.add_field(name="Reason", value=reason,                  inline=False)
        if status != 200:
            embed.description = "_User has no linked Zenith account — Discord ban only._"
        await _send_mod_log(self.bot, embed)

    # ── Member unbanned from Discord ──────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        if guild.id != GUILD_ID:
            return
        embed = discord.Embed(
            title="✅ Discord Unban",
            description=f"{user} (`{user.id}`) was unbanned from Discord.\n"
                        "_Zenith account status is **not** automatically restored. "
                        "Use `/unban` in the Chairman panel if needed._",
            color=discord.Color.green(),
        )
        await _send_mod_log(self.bot, embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
