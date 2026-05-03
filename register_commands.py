"""
register_commands.py — Run this LOCALLY (not on Render) to register slash commands.

Usage:
    1. Make sure your .env has DISCORD_TOKEN=your_token
    2. pip install requests python-dotenv
    3. python register_commands.py

This registers commands directly via Discord's REST API without needing
the bot's WebSocket connection. Commands will show in the server immediately.
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN    = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = "1497396093506551909"

if not TOKEN:
    print("[ERROR] DISCORD_TOKEN not set in .env")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bot {TOKEN}",
    "Content-Type": "application/json",
}

BASE = "https://discord.com/api/v10"


def api(method, path, **kwargs):
    r = getattr(requests, method)(f"{BASE}{path}", headers=HEADERS, **kwargs)
    if r.status_code == 429:
        wait = r.json().get("retry_after", 5)
        print(f"  Rate limited — waiting {wait}s...")
        import time; import time as t; t.sleep(wait + 1)
        return api(method, path, **kwargs)
    return r


# ── Get Application ID ────────────────────────────────────────────────────────
print("[1] Fetching application info...")
r = api("get", "/oauth2/applications/@me")
if r.status_code != 200:
    print(f"[ERROR] Could not fetch app info: {r.status_code} {r.text}")
    sys.exit(1)
APP_ID = r.json()["id"]
APP_NAME = r.json()["name"]
print(f"    App: {APP_NAME} (ID: {APP_ID})")


# ── Command definitions ───────────────────────────────────────────────────────
# Option types: 3=STRING  4=INTEGER  5=BOOLEAN  6=USER  7=CHANNEL  8=ROLE

def opt(name, desc, type_, required=True, choices=None):
    o = {"name": name, "description": desc, "type": type_, "required": required}
    if choices:
        o["choices"] = [{"name": c, "value": c} for c in choices]
    return o

COMMANDS = [
    {
        "name": "ban",
        "description": "Ban a user from the server",
        "options": [
            opt("user",          "User to ban",                    6),
            opt("reason",        "Reason for ban",                 3),
            opt("delete_option", "Message deletion (1d/5d/7d)",    3, required=False,
                choices=["1d", "5d", "7d"]),
        ]
    },
    {
        "name": "mute",
        "description": "Mute a user for 1 hour",
        "options": [
            opt("user",   "User to mute",     6),
            opt("reason", "Reason for mute",  3),
        ]
    },
    {
        "name": "warn",
        "description": "Warn a user (5 warnings = auto-ban)",
        "options": [
            opt("user",   "User to warn",        6),
            opt("reason", "Reason for warning",  3),
        ]
    },
    {
        "name": "promote",
        "description": "Promote a user to a new rank",
        "options": [
            opt("user",     "User to promote",  6),
            opt("reason",   "Reason",           3),
            opt("new_rank", "New role",         8),
        ]
    },
    {
        "name": "infract",
        "description": "Infract a user for policy violations",
        "options": [
            opt("user",            "User",            6),
            opt("reason",          "Reason",          3),
            opt("infraction_type", "strike/warning/demotion", 3),
        ]
    },
    {
        "name": "rank",
        "description": "Modify user roles",
        "options": [
            opt("user",          "User to modify",      6),
            opt("role_add_1",    "Role to add 1",       8, required=False),
            opt("role_add_2",    "Role to add 2",       8, required=False),
            opt("role_add_3",    "Role to add 3",       8, required=False),
            opt("role_remove_1", "Role to remove 1",    8, required=False),
            opt("role_remove_2", "Role to remove 2",    8, required=False),
            opt("role_remove_3", "Role to remove 3",    8, required=False),
        ]
    },
    {
        "name": "lock",
        "description": "Lock a channel",
        "options": [
            opt("channel", "Channel to lock", 7),
            opt("reason",  "Reason",          3),
            opt("time",    "Duration",        3, required=False),
        ]
    },
    {
        "name": "unlock",
        "description": "Unlock a channel",
        "options": [
            opt("channel", "Channel to unlock", 7),
            opt("reason",  "Reason",            3, required=False),
        ]
    },
    {
        "name": "lockdown_start",
        "description": "Lock down the entire server",
        "options": [opt("reason", "Reason", 3, required=False)]
    },
    {
        "name": "lockdown_end",
        "description": "End server lockdown",
        "options": [opt("reason", "Reason", 3, required=False)]
    },
    {
        "name": "user_history",
        "description": "View a user's moderation history",
        "options": [opt("user", "User to check", 6)]
    },
    {
        "name": "application_channel",
        "description": "Open application menu",
        "options": []
    },
    {
        "name": "application_open",
        "description": "Open an application for submissions",
        "options": [opt("application_name", "Application name", 3,
                        choices=["Customer Support", "Risk Management", "Public Relations"])]
    },
    {
        "name": "application_close",
        "description": "Close an application",
        "options": [opt("application_name", "Application name", 3,
                        choices=["Customer Support", "Risk Management", "Public Relations"])]
    },
    {
        "name": "whitelist_add",
        "description": "Add a user to the moderation whitelist",
        "options": [opt("user", "User to whitelist", 6)]
    },
    {
        "name": "whitelist_remove",
        "description": "Remove a user from the whitelist",
        "options": [opt("user", "User to remove", 6)]
    },
    {
        "name": "say",
        "description": "Send a message as the bot",
        "options": [
            opt("channel", "Target channel", 7),
            opt("message", "Message text",   3),
        ]
    },
    {
        "name": "help",
        "description": "Show all available commands",
        "options": []
    },
    {
        "name": "status",
        "description": "View bot status",
        "options": []
    },
]


# ── Register (bulk overwrite — replaces ALL existing guild commands) ───────────
print(f"\n[2] Registering {len(COMMANDS)} commands to guild {GUILD_ID}...")
r = api("put", f"/applications/{APP_ID}/guilds/{GUILD_ID}/commands", json=COMMANDS)

if r.status_code in (200, 201):
    registered = r.json()
    print(f"\n[SUCCESS] Registered {len(registered)} commands:")
    for c in registered:
        print(f"  /{c['name']} — {c['description']}")
    print("\nSlash commands should now appear in your Discord server.")
    print("Note: The bot still needs to be online for commands to respond.")
else:
    print(f"\n[ERROR] Failed: {r.status_code}")
    try:
        err = r.json()
        print(json.dumps(err, indent=2))
        if r.status_code == 401:
            print("\nFix: Your DISCORD_TOKEN is wrong or expired.")
            print("Get a fresh token from: discord.com/developers/applications → Bot → Reset Token")
        elif r.status_code == 403:
            print("\nFix: Make sure your bot is added to the server with 'applications.commands' scope.")
            print("Invite URL: https://discord.com/oauth2/authorize?client_id=YOUR_APP_ID&scope=bot+applications.commands&permissions=8")
    except Exception:
        print(r.text)
