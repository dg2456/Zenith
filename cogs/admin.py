"""
admin.py — staff slash commands

Commands:
  /notify  <member> <action> <product>  — push a license notification to a Zenith user
  /syncban <member> <reason>            — manually sync a ban to Zenith
  /rolecheck <member>                   — force a role sync for a single member
  /rolemap                              — show the current Discord → Zenith role mapping
"""

import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from config import GUILD_ID, MOD_LOG_CHANNEL_ID, PURCHASE_LOG_CHANNEL_ID

API_URL    = os.getenv("ZENITH_API_URL", "").rstrip("/")
BOT_SECRET = os.getenv("DISCORD_BOT_SECRET", "")

HEADERS = {
    "Content-Type": "application/json",
    "x-bot-secret": BOT_SECRET,
}


def _check_api() -> bool:
    return bool(API_URL and BOT_SECRET)


async def _post(url: str, payload: dict) -> tuple[int, dict]:
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.post(url, json=payload) as resp:
            try:
                body = await resp.json()
            except Exception:
                body = {}
            return resp.status, body


async def _get(url: str) -> tuple[int, dict]:
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url) as resp:
            try:
                body = await resp.json()
            except Exception:
                body = {}
            return resp.status, body


async def _send_log(bot: commands.Bot, channel_id: int, embed: discord.Embed):
    try:
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed)
    except Exception:
        pass


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /notify ───────────────────────────────────────────────────────────
    @app_commands.command(
        name="notify",
        description="[Staff] Push a license granted/revoked notification to a Zenith user.",
    )
    @app_commands.describe(
        member="The Discord member to notify.",
        action="Whether the license was granted or revoked.",
        product="The exact product name.",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Granted", value="granted"),
        app_commands.Choice(name="Revoked",  value="revoked"),
    ])
    async def notify(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        action: app_commands.Choice[str],
        product: str,
    ):
        await interaction.response.defer(ephemeral=True)

        if not _check_api():
            await interaction.followup.send("❌ API not configured.", ephemeral=True)
            return

        status, data = await _post(
            f"{API_URL}/api/discord/license-notify",
            {"discordId": str(member.id), "action": action.value, "productName": product},
        )

        if status == 200:
            emoji = "✅" if action.value == "granted" else "🗑️"
            await interaction.followup.send(
                f"{emoji} Notification sent to **{member.display_name}**: "
                f"license **{action.name.lower()}** for `{product}`.",
                ephemeral=True,
            )

            # Log to purchase log channel
            embed = discord.Embed(
                title=f"{'✅ License Granted' if action.value == 'granted' else '🗑️ License Revoked'}",
                color=discord.Color.green() if action.value == "granted" else discord.Color.red(),
            )
            embed.add_field(name="Member",  value=f"{member.mention} (`{member.id}`)", inline=True)
            embed.add_field(name="Product", value=product,                              inline=True)
            embed.add_field(name="By",      value=str(interaction.user),               inline=True)
            await _send_log(self.bot, PURCHASE_LOG_CHANNEL_ID, embed)

        elif status == 404:
            await interaction.followup.send(
                f"❌ **{member.display_name}** has no linked Zenith account.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ API error `{status}`: {data.get('error', 'Unknown error')}", ephemeral=True
            )

    # ── /syncban ──────────────────────────────────────────────────────────
    @app_commands.command(
        name="syncban",
        description="[Staff] Manually sync a Discord ban to Zenith.",
    )
    @app_commands.describe(
        member="The Discord member (use their ID if they are not in the server).",
        reason="Reason for the ban.",
    )
    async def syncban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
    ):
        await interaction.response.defer(ephemeral=True)

        if not _check_api():
            await interaction.followup.send("❌ API not configured.", ephemeral=True)
            return

        status, data = await _post(
            f"{API_URL}/api/discord/ban-sync",
            {"discordId": str(member.id), "reason": reason},
        )

        if status == 200:
            await interaction.followup.send(
                f"🔨 **{member.display_name}** (`{member.id}`) has been banned on Zenith.\n"
                f"Reason: {reason}",
                ephemeral=True,
            )

            embed = discord.Embed(title="🔨 Manual Ban Sync", color=discord.Color.red())
            embed.add_field(name="Member", value=f"{member} (`{member.id}`)", inline=True)
            embed.add_field(name="Reason", value=reason,                      inline=False)
            embed.add_field(name="By",     value=str(interaction.user),       inline=True)
            await _send_log(self.bot, MOD_LOG_CHANNEL_ID, embed)

        elif status == 404:
            await interaction.followup.send(
                f"⚠️ **{member.display_name}** has no linked Zenith account. "
                f"The Discord ban was not synced.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"❌ API error `{status}`: {data.get('error', 'Unknown')}", ephemeral=True
            )

    # ── /rolecheck ────────────────────────────────────────────────────────
    @app_commands.command(
        name="rolecheck",
        description="[Staff] Force a Zenith role sync for a specific member.",
    )
    @app_commands.describe(member="The Discord member to sync.")
    async def rolecheck(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(ephemeral=True)

        if not _check_api():
            await interaction.followup.send("❌ API not configured.", ephemeral=True)
            return

        role_ids = [str(r.id) for r in member.roles]
        status, data = await _post(
            f"{API_URL}/api/discord/role-sync",
            {"discordId": str(member.id), "roleIds": role_ids},
        )

        if status == 200:
            new_role = data.get("role", "unchanged")
            await interaction.followup.send(
                f"✅ Role sync complete for **{member.display_name}**.\n"
                f"Zenith role → **{new_role.replace('_', ' ').title()}**",
                ephemeral=True,
            )
        elif status == 404:
            await interaction.followup.send(
                f"❌ **{member.display_name}** has no linked Zenith account.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ API error `{status}`: {data.get('error', 'Unknown')}", ephemeral=True
            )

    # ── /rolemap ──────────────────────────────────────────────────────────
    @app_commands.command(
        name="rolemap",
        description="[Staff] Show the current Discord → Zenith role mapping.",
    )
    async def rolemap(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not _check_api():
            await interaction.followup.send("❌ API not configured.", ephemeral=True)
            return

        status, data = await _get(f"{API_URL}/api/discord/role-map")

        if status != 200:
            await interaction.followup.send(f"❌ API error `{status}`", ephemeral=True)
            return

        mappings = data.get("roleMappings", {})
        junior   = data.get("juniorRoleId", "—")
        guild    = interaction.guild

        lines = []
        for role_id, zenith_role in mappings.items():
            discord_role = guild.get_role(int(role_id)) if guild else None
            name = discord_role.name if discord_role else f"ID:{role_id}"
            lines.append(f"`{name}` → **{zenith_role.replace('_', ' ').title()}**")

        junior_role = guild.get_role(int(junior)) if guild and junior != "—" else None
        junior_name = junior_role.name if junior_role else f"ID:{junior}"

        embed = discord.Embed(title="🗺️ Zenith Role Map", color=discord.Color.blurple())
        embed.add_field(name="Mappings",           value="\n".join(lines) or "None", inline=False)
        embed.add_field(name="Junior (blocks RM)", value=f"`{junior_name}`",         inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
