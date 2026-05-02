"""
licenses.py — Zenith license lookup commands

Slash commands:
  /licenses discord <member>   — look up by Discord account
  /licenses roblox  <username> — look up by Roblox username
"""

import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

API_URL    = os.getenv("ZENITH_API_URL", "").rstrip("/")
BOT_SECRET = os.getenv("DISCORD_BOT_SECRET", "")

HEADERS = {
    "Content-Type": "application/json",
    "x-bot-secret": BOT_SECRET,
}

PURCHASE_LABELS = {
    "robux":    "Robux",
    "credits":  "Credits",
    "gift":     "Gift",
    "transfer": "Transfer",
    "granted":  "Granted",
}


def _build_embed(user_data: dict, licenses: list) -> discord.Embed:
    username     = user_data.get("robloxUsername", "Unknown")
    display_name = user_data.get("robloxDisplayName") or username
    role         = user_data.get("role", "user").replace("_", " ").title()
    status       = user_data.get("accountStatus", "active")
    credits      = user_data.get("zenithCredits", 0)

    color = discord.Color.green() if status == "active" else discord.Color.red()
    embed = discord.Embed(
        title=f"🔑 Licenses — {display_name}",
        color=color,
    )
    embed.add_field(name="Roblox", value=f"@{username}", inline=True)
    embed.add_field(name="Role",   value=role,           inline=True)
    embed.add_field(name="Status", value=status.title(), inline=True)
    embed.add_field(name="Credits", value=str(credits),  inline=True)

    if not licenses:
        embed.description = "_No licenses found._"
        return embed

    lines = []
    for lic in licenses[:20]:
        product = lic.get("product", {})
        name    = product.get("name", "Unknown")
        tag     = product.get("tag") or "—"
        method  = PURCHASE_LABELS.get(lic.get("purchaseMethod", ""), "Unknown")
        date    = lic.get("purchasedAt", "")[:10]
        lines.append(f"**{name}** `{tag}` · {method} · {date}")

    if len(licenses) > 20:
        lines.append(f"_…and {len(licenses) - 20} more_")

    embed.add_field(name=f"Products ({len(licenses)})", value="\n".join(lines), inline=False)
    return embed


class Licenses(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    licenses_group = app_commands.Group(
        name="licenses",
        description="Look up Zenith product licenses.",
    )

    @licenses_group.command(name="discord", description="Look up licenses by Discord member.")
    @app_commands.describe(member="The Discord member to look up.")
    async def by_discord(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(ephemeral=True)

        if not API_URL:
            await interaction.followup.send("❌ `ZENITH_API_URL` is not configured.", ephemeral=True)
            return

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            url = f"{API_URL}/api/discord/licenses/{member.id}"
            async with session.get(url) as resp:
                if resp.status == 404:
                    await interaction.followup.send(
                        f"❌ **{member.display_name}** has no Zenith account linked to their Discord.",
                        ephemeral=True,
                    )
                    return
                if not resp.ok:
                    await interaction.followup.send(
                        f"❌ API error `{resp.status}`. Check `DISCORD_BOT_SECRET`.", ephemeral=True
                    )
                    return
                data = await resp.json()

        embed = _build_embed(data["user"], data["licenses"])
        await interaction.followup.send(embed=embed, ephemeral=True)

    @licenses_group.command(name="roblox", description="Look up licenses by Roblox username.")
    @app_commands.describe(username="The Roblox username to look up.")
    async def by_roblox(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer(ephemeral=True)

        if not API_URL:
            await interaction.followup.send("❌ `ZENITH_API_URL` is not configured.", ephemeral=True)
            return

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            url = f"{API_URL}/api/discord/licenses/roblox/{username}"
            async with session.get(url) as resp:
                if resp.status == 404:
                    await interaction.followup.send(
                        f"❌ No Zenith account found for Roblox user **{username}**.", ephemeral=True
                    )
                    return
                if not resp.ok:
                    await interaction.followup.send(
                        f"❌ API error `{resp.status}`.", ephemeral=True
                    )
                    return
                data = await resp.json()

        embed = _build_embed(data["user"], data["licenses"])
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Licenses(bot))
