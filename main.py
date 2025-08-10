# Guardian++ (enhanced) — Anti‑nuke + Moderation bot
# Developed by Bruce Wayne • GitHub: https://github.com/Brucewayne34
# Install deps: pip install -r requirements.txt

import asyncio
import json
import logging
import os
import random
import re
import sys
from typing import Optional
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

# ----- Colored terminal output -----
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init(autoreset=True)
    COLOR_ENABLED = True
except Exception:
    COLOR_ENABLED = True
    class Fore:  # fallbacks
        CYAN = GREEN = MAGENTA = YELLOW = RED = BLUE = WHITE = ""
    class Style:
        BRIGHT = RESET_ALL = ""

GITHUB_URL = "https://github.com/Brucewayne34"
MADE_BY = "Developed by Bruce Wayne"

START_TIME = datetime.now(timezone.utc)

def banner(msg=""):
    if COLOR_ENABLED:
        print(
            f"{Fore.MAGENTA}{Style.BRIGHT}"
            "┌──────────────────────────────────────────────────────────────┐\n"
            "│                       Guardian++ v1.1                         │\n"
            "│  Anti‑Nuke • Moderation • Utilities • Slash • Logging         │\n"
            "│  {0}{1}                                                       │\n"
            "│  GitHub: {2}                                   │\n"
            "└──────────────────────────────────────────────────────────────┘".format(
                MADE_BY.ljust(32), "", GITHUB_URL)
        )
    else:
        print("Guardian++ v1.1 — " + MADE_BY + " — " + GITHUB_URL)
    if msg:
        print(msg)

# ---------------- Logging ----------------
class ColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: Fore.BLUE if COLOR_ENABLED else "",
        logging.INFO: Fore.GREEN if COLOR_ENABLED else "",
        logging.WARNING: Fore.YELLOW if COLOR_ENABLED else "",
        logging.ERROR: Fore.RED if COLOR_ENABLED else "",
        logging.CRITICAL: Fore.RED + Style.BRIGHT if COLOR_ENABLED else "",
    }
    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelno, "")
        reset = Style.RESET_ALL if COLOR_ENABLED else ""
        base = super().format(record)
        return f"{color}{base}{reset}"

handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[handler])
log = logging.getLogger("guardian_plus")
logging.getLogger("discord").setLevel(logging.INFO)

# ---------------- Load config ----------------
CONFIG_PATH = "config.json"
if not os.path.exists(CONFIG_PATH):
    banner(f"{Fore.RED if COLOR_ENABLED else ''}[Guardian++] config.json not found next to bot.py. Create it (sample provided).{Style.RESET_ALL if COLOR_ENABLED else ''}")
    sys.exit(1)

try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
except Exception as e:
    banner(f"{Fore.RED if COLOR_ENABLED else ''}[Guardian++] Failed to parse config.json: {e}{Style.RESET_ALL if COLOR_ENABLED else ''}")
    sys.exit(1)

TOKEN = os.getenv("DISCORD_TOKEN") or CONFIG.get("token")
if not TOKEN or TOKEN.strip() in ("", "YOUR_BOT_TOKEN_HERE"):
    banner(f"{Fore.RED if COLOR_ENABLED else ''}[Guardian++] No valid token in config.json ('token') or DISCORD_TOKEN env var.{Style.RESET_ALL if COLOR_ENABLED else ''}")
    sys.exit(1)

DEFAULT_PREFIX = CONFIG.get("default_prefix", "-")
OWNER_IDS = set(CONFIG.get("owner_ids", []))
EMBED_COLOR = CONFIG.get("embed", {}).get("color", 0x9B59B6)  # purple default
EMBED_FOOTER = CONFIG.get("embed", {}).get("footer", "Guardian++ • Moderation & Security")
SLASH_GUILD_SYNC_IDS = CONFIG.get("slash", {}).get("guild_sync_ids", [])
ANTI_DEFAULTS = CONFIG.get("antinuke_defaults", {})

DB_MODE = CONFIG.get("database", {}).get("mode", "json")
JSON_PATH = CONFIG.get("database", {}).get("json_path", "data.json")
MONGO_URI = CONFIG.get("database", {}).get("mongo_uri", "mongodb://localhost:27017")
MONGO_DB_NAME = CONFIG.get("database", {}).get("mongo_db", "modbot")

# ---------------- Intents ----------------
intents = discord.Intents(
    guilds=True,
    members=True,
    bans=True,
    emojis=True,
    messages=True,
    reactions=True,
    presences=False,
    message_content=True
)

# ---------------- Utils ----------------
INVITE_REGEX = re.compile(r"(?:discord\.gg|discord\.com/invite)/[a-zA-Z0-9\-]+", re.IGNORECASE)
UNDER = lambda s: f"__{s}__"
BOLD = lambda s: f"**{s}**"
ITAL = lambda s: f"*{s}*"
CODE = lambda s: f"`{s}`"

def human_timedelta(dt: timedelta) -> str:
    total = int(dt.total_seconds())
    d, r = divmod(total, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s and not parts: parts.append(f"{s}s")
    return " ".join(parts) if parts else "0s"

def parse_duration(s: Optional[str], default_seconds: int = 300) -> int:
    if not s:
        return default_seconds
    m = re.fullmatch(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", s.strip(), re.I)
    if not m:
        raise ValueError("Invalid duration. Examples: 5m, 1h, 2d, 1d2h30m")
    d, h, mm, ss = (int(x) if x else 0 for x in m.groups())
    secs = d*86400 + h*3600 + mm*60 + ss
    return secs if secs > 0 else default_seconds

def avatar_url(user: discord.abc.User) -> Optional[str]:
    try:
        return user.display_avatar.url
    except Exception:
        return None

def ok_embed(title=None, description=None, requester: Optional[discord.abc.User]=None, thumbnail_user: Optional[discord.abc.User]=None) -> discord.Embed:
    e = discord.Embed(color=EMBED_COLOR, title=title, description=description)
    if thumbnail_user:
        url = avatar_url(thumbnail_user)
        if url:
            e.set_thumbnail(url=url)
    footer_text = f"{EMBED_FOOTER} • {MADE_BY} • {GITHUB_URL}"
    footer_icon = avatar_url(requester) if requester else None
    e.set_footer(text=footer_text if requester is None else f"Requested by {requester} • {MADE_BY}", icon_url=footer_icon if footer_icon else discord.Embed.Empty)
    e.timestamp = datetime.now(timezone.utc)
    return e

# ---------------- Data layer ----------------
class AbstractDB:
    async def init(self): ...
    async def get_guild(self, gid): ...
    async def set_guild(self, gid, data): ...
    async def update_guild(self, gid, patch: dict): ...
    async def add_warn(self, gid, uid, warn): ...
    async def remove_warn(self, gid, uid, warn_id): ...
    async def get_warns(self, gid, uid): ...
    async def clear_warns(self, gid, uid): ...
    async def audit(self, gid, entry: dict): ...

class JSONDB(AbstractDB):
    def __init__(self, path: str):
        self.path = path
        self.data = {"guilds": {}}

    async def init(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                log.exception("Failed to load JSON DB; starting fresh.")
                self.data = {"guilds": {}}
        else:
            await self._commit()

    async def _commit(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    async def get_guild(self, gid):
        return self.data["guilds"].get(str(gid), {})

    async def set_guild(self, gid, data):
        self.data["guilds"][str(gid)] = data
        await self._commit()

    async def update_guild(self, gid, patch: dict):
        cur = self.data["guilds"].get(str(gid), {})
        cur.update(patch)
        self.data["guilds"][str(gid)] = cur
        await self._commit()

    async def add_warn(self, gid, uid, warn):
        g = self.data["guilds"].setdefault(str(gid), {})
        warns = g.setdefault("warns", {}).setdefault(str(uid), [])
        warns.append(warn)
        await self._commit()
        return warn

    async def remove_warn(self, gid, uid, warn_id):
        g = self.data["guilds"].get(str(gid), {})
        warns = g.get("warns", {}).get(str(uid), [])
        new = [w for w in warns if str(w.get("id")) != str(warn_id)]
        changed = len(new) != len(warns)
        if changed:
            g["warns"][str(uid)] = new
            await self._commit()
        return changed

    async def get_warns(self, gid, uid):
        g = self.data["guilds"].get(str(gid), {})
        return g.get("warns", {}).get(str(uid), [])

    async def clear_warns(self, gid, uid):
        g = self.data["guilds"].setdefault(str(gid), {})
        g.setdefault("warns", {})[str(uid)] = []
        await self._commit()

    async def audit(self, gid, entry: dict):
        g = self.data["guilds"].setdefault(str(gid), {})
        g.setdefault("audit", []).append(entry)
        await self._commit()

class MongoDB(AbstractDB):
    def __init__(self, uri: str, db_name: str):
        self.uri = uri; self.db_name = db_name
        self.client = None; self.db = None

    async def init(self):
        import motor.motor_asyncio
        self.client = motor.motor_asyncio.AsyncIOMotorClient(self.uri)
        self.db = self.client[self.db_name]
        await self.db.guilds.create_index("gid", unique=True)
        await self.db.warns.create_index([("gid", 1), ("uid", 1)])

    async def get_guild(self, gid):
        doc = await self.db.guilds.find_one({"gid": int(gid)}) or {}
        return doc.get("data", {})

    async def set_guild(self, gid, data):
        await self.db.guilds.update_one({"gid": int(gid)}, {"$set": {"data": data}}, upsert=True)

    async def update_guild(self, gid, patch: dict):
        await self.db.guilds.update_one({"gid": int(gid)}, {"$set": {f"data.{k}": v for k, v in patch.items()}}, upsert=True)

    async def add_warn(self, gid, uid, warn):
        await self.db.warns.insert_one({"gid": int(gid), "uid": int(uid), **warn})
        return warn

    async def remove_warn(self, gid, uid, warn_id):
        result = await self.db.warns.delete_one({"gid": int(gid), "uid": int(uid), "id": int(warn_id)})
        return result.deleted_count > 0

    async def get_warns(self, gid, uid):
        cur = self.db.warns.find({"gid": int(gid), "uid": int(uid)})
        return [w async for w in cur]

    async def clear_warns(self, gid, uid):
        await self.db.warns.delete_many({"gid": int(gid), "uid": int(uid)})

    async def audit(self, gid, entry: dict):
        await self.db.audit.insert_one({"gid": int(gid), **entry})

# ---------------- Bot core ----------------
class GuardianPlus(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=self.get_prefix,
            intents=intents,
            case_insensitive=True,
            help_command=None
        )
        self.db: AbstractDB = MongoDB(MONGO_URI, MONGO_DB_NAME) if DB_MODE == "mongo" else JSONDB(JSON_PATH)
        self.spam_cache = {}
        self.chan_del_cache = {}
        self.afk = {}
        self.snipes = {}
        self.editsnipes = {}

    async def setup_hook(self):
        await self.db.init()
        await self.add_cog(HelpCog(self))
        await self.add_cog(General(self))
        await self.add_cog(Moderation(self))
        await self.add_cog(Warns(self))
        await self.add_cog(AntiNuke(self))
        await self.add_cog(SetupCog(self))
        await self.add_cog(Utility(self))
        await self.add_cog(Info(self))
        self.antispam_cleanup.start()

        # Slash sync
        if SLASH_GUILD_SYNC_IDS:
            for gid in SLASH_GUILD_SYNC_IDS:
                try:
                    gobj = discord.Object(id=int(gid))
                    self.tree.copy_global_to(guild=gobj)
                    await self.tree.sync(guild=gobj)
                    log.info(f"Synced slash commands to guild {gid}")
                except Exception:
                    log.exception(f"Failed syncing to guild {gid}")
        else:
            try:
                await self.tree.sync()
                log.info("Globally synced application commands.")
            except Exception:
                log.exception("Global slash sync failed")

    async def get_prefix(self, message: discord.Message):
        if not message.guild:
            return DEFAULT_PREFIX
        g = await self.db.get_guild(message.guild.id)
        return g.get("prefix", DEFAULT_PREFIX)

    @tasks.loop(minutes=1)
    async def antispam_cleanup(self):
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        for cache in (self.spam_cache, self.chan_del_cache):
            for key in list(cache.keys()):
                cache[key] = [t for t in cache[key] if t >= cutoff]
                if not cache[key]:
                    del cache[key]

    @antispam_cleanup.before_loop
    async def before_cleanup(self):
        await self.wait_until_ready()

bot = GuardianPlus()

# ---------------- Lifecycle logs ----------------
@bot.event
async def on_connect():
    banner(f"{Fore.CYAN if COLOR_ENABLED else ''}[Guardian++] on_connect: Connecting to Discord…{Style.RESET_ALL if COLOR_ENABLED else ''}")

@bot.event
async def on_ready():
    print(f"{Fore.GREEN if COLOR_ENABLED else ''}[Guardian++] on_ready: Logged in as {bot.user} (ID: {bot.user.id}) | guilds={len(bot.guilds)}{Style.RESET_ALL if COLOR_ENABLED else ''}")

@bot.event
async def on_disconnect():
    print(f"{Fore.YELLOW if COLOR_ENABLED else ''}[Guardian++] on_disconnect: Disconnected; discord.py will auto-reconnect.{Style.RESET_ALL if COLOR_ENABLED else ''}")

@bot.event
async def on_resumed():
    print(f"{Fore.GREEN if COLOR_ENABLED else ''}[Guardian++] on_resumed: Session resumed.{Style.RESET_ALL if COLOR_ENABLED else ''}")

# ---------------- Global events (snipes & AFK pings) ----------------
@bot.event
async def on_message_delete(message: discord.Message):
    if message.guild and not message.author.bot:
        bot.snipes[(message.guild.id, message.channel.id)] = (message.author, message.content, datetime.now(timezone.utc))

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.guild and not before.author.bot:
        bot.editsnipes[(before.guild.id, before.channel.id)] = (before.author, before.content, after.content, datetime.now(timezone.utc))

@bot.event
async def on_message(message: discord.Message):
    if message.guild and message.mentions:
        pinged = [u for u in message.mentions if bot.afk.get(u.id)]
        for u in pinged:
            reason = bot.afk.get(u.id)
            try:
                await message.channel.send(embed=ok_embed("AFK", f"{u.mention} is AFK — {ITAL(reason)}", requester=message.author, thumbnail_user=u))
            except Exception:
                pass
    await bot.process_commands(message)

# ---------------- Error handlers ----------------
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
    logging.exception("App command error", exc_info=error)
    await send(embed=ok_embed("Error", f"Something went wrong: `{error.__class__.__name__}`", requester=interaction.user, thumbnail_user=interaction.user), ephemeral=True)

@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingPermissions):
        return await ctx.reply(embed=ok_embed("Missing Permissions", "You don’t have permission.", requester=ctx.author, thumbnail_user=ctx.author))
    if isinstance(error, commands.BotMissingPermissions):
        return await ctx.reply(embed=ok_embed("I Need Permissions", ", ".join(error.missing_permissions), requester=ctx.author, thumbnail_user=ctx.author))
    if isinstance(error, (commands.BadArgument, commands.UserInputError, commands.MissingRequiredArgument)):
        return await ctx.reply(embed=ok_embed("Bad Usage", str(error), requester=ctx.author, thumbnail_user=ctx.author))
    logging.exception("Command error", exc_info=error)
    await ctx.reply(embed=ok_embed("Error", f"Something went wrong: `{error.__class__.__name__}`", requester=ctx.author, thumbnail_user=ctx.author))

# ---------------- Checks ----------------
def app_mod_or_admin(interaction: discord.Interaction) -> bool:
    p = interaction.user.guild_permissions
    return p.manage_guild or p.kick_members or p.ban_members or p.moderate_members or p.administrator

def mod_or_admin():
    async def predicate(ctx: commands.Context):
        p = ctx.author.guild_permissions
        return p.manage_guild or p.kick_members or p.ban_members or p.moderate_members or p.administrator
    return commands.check(predicate)

# ---------------- Help ----------------
class HelpCog(commands.Cog):
    def __init__(self, bot: GuardianPlus):
        self.bot = bot

    def _groups(self) -> dict:
        return {
            "General": ["ping", "prefix", "help", "sync", "about", "invite", "uptime", "stats"],
            "Moderation": ["timeout/mute", "removetimeout/unmute", "kick", "ban", "unban", "jail", "unjail", "temprole", "softban"],
            "Warnings": ["warn", "removewarn", "infractions", "clearwarns"],
            "Utility": ["purge", "purgeuser", "purgecontains", "purgefiles", "purgebots", "slowmode", "lock", "unlock", "say", "announce", "poll", "nuke", "afk", "remindme", "snipe", "editsnipe"],
            "Info": ["whois", "avatar", "banner", "serverinfo", "channelinfo", "roleinfo", "emoji", "roles", "permissions"],
            "Admin Setup": ["setup", "setlog", "setjail", "setwhitelist", "setantinuke", "setinvites", "setnsfwblock"]
        }

    def help_embed(self, prefix: str, user: Optional[discord.abc.User]=None) -> discord.Embed:
        e = ok_embed("Guardian++ Help", f"Use {CODE(prefix+'<command>')} or slash {CODE('/command')}.\n{ITAL('Styling:')} use **bold**, *italics*, and __underline__.", requester=user, thumbnail_user=user)
        for name, cmds in self._groups().items():
            e.add_field(name=name, value="`" + "`, `".join(cmds) + "`", inline=False)
        e.add_field(
            name="Examples",
            value=(
                f"{CODE(prefix+'timeout @user 10m Spamming')}\n"
                f"{CODE(prefix+'warn @user Be respectful')}\n"
                f"{CODE(prefix+'setantinuke spam_threshold 6')}\n"
                f"{CODE(prefix+'setup')}  ({UNDER('wizard')})"
            ),
            inline=False
        )
        return e

    @commands.command(name="help")
    async def help_text(self, ctx: commands.Context):
        p = await self.bot.get_prefix(ctx.message)
        await ctx.reply(embed=self.help_embed(p if isinstance(p, str) else p[0], user=ctx.author))

    @app_commands.command(name="help", description="Show help for Guardian++.")
    async def help_slash(self, interaction: discord.Interaction):
        g = await self.bot.db.get_guild(interaction.guild_id)
        p = g.get("prefix", DEFAULT_PREFIX)
        await interaction.response.send_message(embed=self.help_embed(p, user=interaction.user), ephemeral=True)

# ---------------- General ----------------
class General(commands.Cog):
    def __init__(self, bot: GuardianPlus):
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        await ctx.reply(embed=ok_embed("Pong", f"Latency: {BOLD(str(round(self.bot.latency*1000))+'ms')}", requester=ctx.author, thumbnail_user=ctx.author))

    @app_commands.command(name="ping", description="Show the bot latency.")
    async def ping_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=ok_embed("Pong", f"Latency: {BOLD(str(round(self.bot.latency*1000))+'ms')}", requester=interaction.user, thumbnail_user=interaction.user), ephemeral=True)

    @commands.command(name="uptime")
    async def uptime(self, ctx: commands.Context):
        delta = datetime.now(timezone.utc) - START_TIME
        await ctx.reply(embed=ok_embed("Uptime", human_timedelta(delta), requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="stats")
    async def stats(self, ctx: commands.Context):
        users = sum(g.member_count for g in self.bot.guilds if g.member_count)
        e = ok_embed("Stats",
                     f"Guilds: {BOLD(str(len(self.bot.guilds)))}\n"
                     f"Users (approx): {BOLD(str(users))}\n"
                     f"Latency: {BOLD(str(round(self.bot.latency*1000))+'ms')}",
                     requester=ctx.author, thumbnail_user=ctx.author)
        await ctx.reply(embed=e)

    @commands.command(name="prefix")
    @commands.has_guild_permissions(manage_guild=True)
    async def prefix_set(self, ctx: commands.Context, new_prefix: str):
        await self.bot.db.update_guild(ctx.guild.id, {"prefix": new_prefix})
        await ctx.reply(embed=ok_embed("Prefix Updated", f"New prefix: {CODE(new_prefix)}", requester=ctx.author, thumbnail_user=ctx.author))

    @app_commands.command(name="prefix", description="Set the text prefix for this server.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def prefix_set_slash(self, interaction: discord.Interaction, new_prefix: str):
        await self.bot.db.update_guild(interaction.guild_id, {"prefix": new_prefix})
        await interaction.response.send_message(embed=ok_embed("Prefix Updated", f"New prefix: {CODE(new_prefix)}", requester=interaction.user, thumbnail_user=interaction.user), ephemeral=True)

    @commands.command(name="sync")
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, scope: Optional[str]=None):
        try:
            if scope == "guild":
                await bot.tree.sync(guild=ctx.guild)
            else:
                await bot.tree.sync()
            await ctx.reply(embed=ok_embed("Synced", f"Scope: {CODE(scope or 'global')}", requester=ctx.author, thumbnail_user=ctx.author))
        except Exception as e:
            await ctx.reply(embed=ok_embed("Sync Failed", str(e), requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="about")
    async def about(self, ctx: commands.Context):
        desc = f"{BOLD('Guardian++')} — Anti‑nuke & Mod bot.\n{UNDER('Author')}: Bruce Wayne\n{UNDER('GitHub')}: {GITHUB_URL}"
        await ctx.reply(embed=ok_embed("About", desc, requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="invite")
    async def invite(self, ctx: commands.Context):
        app = await self.bot.application_info()
        url = f"https://discord.com/oauth2/authorize?client_id={app.id}&permissions=8&scope=bot%20applications.commands"
        await ctx.reply(embed=ok_embed("Invite Guardian++", f"[Click here to invite]({url})", requester=ctx.author, thumbnail_user=ctx.author))

# ---------------- Moderation ----------------
class Moderation(commands.Cog):
    def __init__(self, bot: GuardianPlus):
        self.bot = bot

    @commands.command(name="timeout", aliases=["mute"])
    @commands.has_guild_permissions(moderate_members=True)
    async def timeout_cmd(self, ctx: commands.Context, member: discord.Member, duration: Optional[str]=None, *, reason: Optional[str]=None):
        secs = parse_duration(duration, 300)
        until = datetime.now(timezone.utc) + timedelta(seconds=secs)
        await member.timeout(until, reason=reason or f"Timeout by {ctx.author}")
        await ctx.reply(embed=ok_embed("Timed Out", f"{member.mention} for {BOLD(human_timedelta(timedelta(seconds=secs)))}", requester=ctx.author, thumbnail_user=ctx.author))

    @app_commands.command(name="timeout", description="Timeout/mute a member temporarily.")
    @app_commands.check(app_mod_or_admin)
    async def timeout_slash(self, interaction: discord.Interaction, member: discord.Member, duration: Optional[str]=None, reason: Optional[str]=None):
        secs = parse_duration(duration, 300)
        until = datetime.now(timezone.utc) + timedelta(seconds=secs)
        await member.timeout(until, reason=reason or f"Timeout by {interaction.user}")
        await interaction.response.send_message(embed=ok_embed("Timed Out", f"{member.mention} for {BOLD(human_timedelta(timedelta(seconds=secs)))}", requester=interaction.user, thumbnail_user=interaction.user))

    @commands.command(name="removetimeout", aliases=["unmute"])
    @commands.has_guild_permissions(moderate_members=True)
    async def removetimeout(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str]=None):
        await member.timeout(None, reason=reason or f"Remove timeout by {ctx.author}")
        await ctx.reply(embed=ok_embed("Timeout Removed", f"{member.mention} is free.", requester=ctx.author, thumbnail_user=ctx.author))

    @app_commands.command(name="removetimeout", description="Remove timeout from a member.")
    @app_commands.check(app_mod_or_admin)
    async def removetimeout_slash(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str]=None):
        await member.timeout(None, reason=reason or f"Remove timeout by {interaction.user}")
        await interaction.response.send_message(embed=ok_embed("Timeout Removed", f"{member.mention} is free.", requester=interaction.user, thumbnail_user=interaction.user))

    @commands.command(name="kick")
    @commands.has_guild_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str]=None):
        await member.kick(reason=reason or f"Kicked by {ctx.author}")
        await ctx.reply(embed=ok_embed("Kicked", f"{member}", requester=ctx.author, thumbnail_user=ctx.author))

    @app_commands.command(name="kick", description="Kick a member.")
    @app_commands.check(app_mod_or_admin)
    async def kick_slash(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str]=None):
        await member.kick(reason=reason or f"Kicked by {interaction.user}")
        await interaction.response.send_message(embed=ok_embed("Kicked", f"{member}", requester=interaction.user, thumbnail_user=interaction.user))

    @commands.command(name="ban")
    @commands.has_guild_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str]=None):
        await member.ban(reason=reason or f"Banned by {ctx.author}")
        await ctx.reply(embed=ok_embed("Banned", f"{member}", requester=ctx.author, thumbnail_user=ctx.author))

    @app_commands.command(name="ban", description="Ban a member.")
    @app_commands.check(app_mod_or_admin)
    async def ban_slash(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str]=None):
        await member.ban(reason=reason or f"Banned by {interaction.user}")
        await interaction.response.send_message(embed=ok_embed("Banned", f"{member}", requester=interaction.user, thumbnail_user=interaction.user))

    @commands.command(name="unban")
    @commands.has_guild_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user: discord.User, *, reason: Optional[str]=None):
        await ctx.guild.unban(user, reason=reason or f"Unban by {ctx.author}")
        await ctx.reply(embed=ok_embed("Unbanned", f"{user}", requester=ctx.author, thumbnail_user=ctx.author))

    @app_commands.command(name="unban", description="Unban a user.")
    @app_commands.check(app_mod_or_admin)
    async def unban_slash(self, interaction: discord.Interaction, user: discord.User, reason: Optional[str]=None):
        await interaction.guild.unban(user, reason=reason or f"Unban by {interaction.user}")
        await interaction.response.send_message(embed=ok_embed("Unbanned", f"{user}", requester=interaction.user, thumbnail_user=interaction.user))

    async def ensure_jail_role(self, guild: discord.Guild) -> discord.Role:
        g = await self.bot.db.get_guild(guild.id)
        rid = g.get("jail_role_id")
        role = guild.get_role(rid) if rid else None
        if role:
            return role
        role = await guild.create_role(name="Jail", reason="Guardian++ jail role")
        await self.bot.db.update_guild(guild.id, {"jail_role_id": role.id})
        for ch in guild.channels:
            try:
                ow = ch.overwrites or {}
                ow[role] = discord.PermissionOverwrite(
                    view_channel=False, send_messages=False, speak=False,
                    send_messages_in_threads=False, add_reactions=False
                )
                await ch.edit(overwrites=ow)
            except Exception:
                pass
        jail_ch = discord.utils.get(guild.text_channels, name="jail")
        if not jail_ch:
            jail_ch = await guild.create_text_channel("jail", reason="Guardian++ jail channel")
            await jail_ch.set_permissions(role, view_channel=True, send_messages=True)
        return role

    @commands.command(name="jail")
    @commands.has_guild_permissions(manage_roles=True, moderate_members=True)
    async def jail(self, ctx: commands.Context, member: discord.Member, duration: Optional[str]=None, *, reason: Optional[str]=None):
        secs = parse_duration(duration, 3600)
        jail_role = await self.ensure_jail_role(ctx.guild)
        roles_to_remove = [r for r in member.roles if not r.is_default() and r != jail_role]
        store = {"roles": [r.id for r in roles_to_remove], "until": (datetime.now(timezone.utc) + timedelta(seconds=secs)).timestamp()}
        g = await self.bot.db.get_guild(ctx.guild.id)
        jailed = g.get("jailed", {}); jailed[str(member.id)] = store
        await self.bot.db.update_guild(ctx.guild.id, {"jailed": jailed})
        await member.edit(roles=[r for r in member.roles if r not in roles_to_remove] + [jail_role], reason=reason or f"Jailed by {ctx.author}")
        await ctx.reply(embed=ok_embed("Jailed", f"{member.mention} for {BOLD(human_timedelta(timedelta(seconds=secs)))}", requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="unjail")
    @commands.has_guild_permissions(manage_roles=True, moderate_members=True)
    async def unjail(self, ctx: commands.Context, member: discord.Member):
        g = await self.bot.db.get_guild(ctx.guild.id)
        jailed = g.get("jailed", {})
        info = jailed.pop(str(member.id), None)
        if not info:
            return await ctx.reply(embed=ok_embed("Not Jailed", f"{member.mention} isn’t jailed.", requester=ctx.author, thumbnail_user=ctx.author))
        await self.bot.db.update_guild(ctx.guild.id, {"jailed": jailed})
        jr_id = g.get("jail_role_id")
        if jr_id:
            jr = ctx.guild.get_role(jr_id)
            if jr and jr in member.roles:
                await member.remove_roles(jr, reason="Unjail")
        role_ids = info.get("roles", [])
        roles = [ctx.guild.get_role(rid) for rid in role_ids if ctx.guild.get_role(rid)]
        if roles:
            try: await member.add_roles(*roles, reason="Restore roles after jail")
            except discord.Forbidden: pass
        await ctx.reply(embed=ok_embed("Unjailed", f"{member.mention} restored.", requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="temprole")
    @commands.has_guild_permissions(manage_roles=True)
    async def temprole(self, ctx: commands.Context, member: discord.Member, role: discord.Role, duration: Optional[str]=None, *, reason: Optional[str]=None):
        secs = parse_duration(duration, 600)
        await member.add_roles(role, reason=reason or f"Temp role by {ctx.author}")
        await ctx.reply(embed=ok_embed("Temp Role", f"Gave {role.mention} to {member.mention} for {BOLD(human_timedelta(timedelta(seconds=secs)))}", requester=ctx.author, thumbnail_user=ctx.author))
        await asyncio.sleep(secs)
        try:
            await member.remove_roles(role, reason="Temp role expired")
        except discord.Forbidden:
            pass

# ---------------- Warnings ----------------
class Warns(commands.Cog):
    def __init__(self, bot: GuardianPlus):
        self.bot = bot

    def _new_warn(self, moderator: discord.abc.User, reason: Optional[str]):
        return {"id": random.randint(100000, 999999), "moderator_id": moderator.id, "reason": reason or "No reason", "time": datetime.now(timezone.utc).isoformat()}

    async def log_and_dm(self, guild: discord.Guild, target: discord.Member, moderator: discord.abc.User, warn_id: int, reason: str):
        # DM user
        try:
            dm = await target.create_dm()
            await dm.send(embed=ok_embed("You were warned", f"Server: {BOLD(guild.name)}\nBy: {BOLD(str(moderator))}\nReason: {ITAL(reason)}\nID: {CODE(str(warn_id))}", requester=moderator, thumbnail_user=moderator))
        except Exception:
            pass
        # Log in channel
        g = await self.bot.db.get_guild(guild.id)
        ch_id = g.get("log_channel_id")
        ch = guild.get_channel(ch_id) if ch_id else None
        if isinstance(ch, discord.TextChannel):
            await ch.send(embed=ok_embed("Warn Issued", f"{target.mention} warned by {BOLD(str(moderator))}\nReason: {ITAL(reason)}\nID: {CODE(str(warn_id))}", requester=moderator, thumbnail_user=target))

    @commands.command(name="warn")
    @commands.has_guild_permissions(moderate_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str]=None):
        warn = self._new_warn(ctx.author, reason)
        await self.bot.db.add_warn(ctx.guild.id, member.id, warn)
        await self.log_and_dm(ctx.guild, member, ctx.author, warn['id'], warn['reason'])
        await ctx.reply(embed=ok_embed("Warned", f"{member.mention} warned {CODE('#'+str(warn['id']))}\nReason: {ITAL(warn['reason'])}", requester=ctx.author, thumbnail_user=member))

    @app_commands.command(name="warn", description="Issue a warning to a member (DM + log).")
    @app_commands.check(app_mod_or_admin)
    async def warn_slash(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str]=None):
        warn = self._new_warn(interaction.user, reason)
        await self.bot.db.add_warn(interaction.guild_id, member.id, warn)
        await self.log_and_dm(interaction.guild, member, interaction.user, warn['id'], warn['reason'])
        await interaction.response.send_message(embed=ok_embed("Warned", f"{member.mention} warned {CODE('#'+str(warn['id']))}\nReason: {ITAL(warn['reason'])}", requester=interaction.user, thumbnail_user=member))

    @commands.command(name="removewarn")
    @commands.has_guild_permissions(moderate_members=True)
    async def removewarn(self, ctx: commands.Context, member: discord.Member, warn_id: int):
        ok = await self.bot.db.remove_warn(ctx.guild.id, member.id, warn_id)
        await ctx.reply(embed=ok_embed("Removed Warn" if ok else "Not Found", f"{member.mention} warn {CODE('#'+str(warn_id))} {'removed' if ok else 'not found'}.", requester=ctx.author, thumbnail_user=member))

    @app_commands.command(name="removewarn", description="Remove a warning by ID from a member.")
    @app_commands.check(app_mod_or_admin)
    async def removewarn_slash(self, interaction: discord.Interaction, member: discord.Member, warn_id: int):
        ok = await self.bot.db.remove_warn(interaction.guild_id, member.id, warn_id)
        await interaction.response.send_message(embed=ok_embed("Remove Warn", f"{member.mention} warn {CODE('#'+str(warn_id))} {'removed' if ok else 'not found'}.", requester=interaction.user, thumbnail_user=member))

    @commands.command(name="infractions")
    async def infractions(self, ctx: commands.Context, member: Optional[discord.Member]=None):
        member = member or ctx.author
        warns = await self.bot.db.get_warns(ctx.guild.id, member.id)
        if not warns:
            return await ctx.reply(embed=ok_embed("Infractions", f"{member.mention} has {BOLD('0')} warnings.", requester=ctx.author, thumbnail_user=member))
        lines = [f"{CODE('#'+str(w['id']))} • {ITAL(w['reason'])} • <@{w['moderator_id']}> • <t:{int(datetime.fromisoformat(w['time']).timestamp())}:R>" for w in warns]
        await ctx.reply(embed=ok_embed(f"Infractions for {member}", "\n".join(lines[:20]), requester=ctx.author, thumbnail_user=member))

    @commands.command(name="clearwarns")
    @commands.has_guild_permissions(moderate_members=True)
    async def clearwarns(self, ctx: commands.Context, member: discord.Member):
        await self.bot.db.clear_warns(ctx.guild.id, member.id)
        await ctx.reply(embed=ok_embed("Cleared Warns", f"All warnings cleared for {member.mention}", requester=ctx.author, thumbnail_user=member))

# ---------------- Anti-Nuke ----------------
class AntiNuke(commands.Cog):
    def __init__(self, bot: GuardianPlus):
        self.bot = bot

    async def get_settings(self, guild_id: int) -> dict:
        g = await self.bot.db.get_guild(guild_id)
        s = g.get("antinuke", {})
        out = {**ANTI_DEFAULTS, **s}
        out.setdefault("whitelist_ids", [])
        out["log_channel_id"] = g.get("log_channel_id")
        return out

    def _log_channel(self, guild: discord.Guild, settings: dict) -> Optional[discord.TextChannel]:
        ch_id = settings.get("log_channel_id")
        if ch_id:
            ch = guild.get_channel(ch_id)
            if isinstance(ch, discord.TextChannel): return ch
        for name in ("mod-log", "logs", "guardian-log"):
            ch = discord.utils.get(guild.text_channels, name=name)
            if ch: return ch
        return None

    async def _punish(self, guild: discord.Guild, offender: discord.Member, settings: dict, reason: str, actor: Optional[discord.Member]=None):
        if offender is None:
            return
        secs = int(settings.get("timeout_seconds", 60))
        try:
            until = datetime.now(timezone.utc) + timedelta(seconds=secs)
            await offender.timeout(until, reason=f"Anti-Nuke: {reason}")
        except discord.Forbidden:
            pass
        if settings.get("auto_revoke_dangerous_perms", True):
            try:
                for role in offender.roles:
                    if role.is_default(): continue
                    p = role.permissions
                    if p.administrator or p.manage_guild or p.manage_roles:
                        await offender.remove_roles(role, reason="Guardian++ revoke dangerous perms")
            except discord.Forbidden:
                pass
        ch = self._log_channel(guild, settings)
        if ch:
            await ch.send(embed=ok_embed("Anti-Nuke Triggered", f"Offender: {offender.mention}\nReason: {ITAL(reason)}\nAction: Timeout {CODE(str(secs)+'s')}", requester=actor or offender, thumbnail_user=offender))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        settings = await self.get_settings(message.guild.id)

        if settings.get("block_invites", True) and INVITE_REGEX.search(message.content):
            try: await message.delete()
            except discord.Forbidden: pass
            ch = self._log_channel(message.guild, settings)
            if ch: await ch.send(embed=ok_embed("Invite Blocked", f"{message.author.mention} in {message.channel.mention}", requester=message.author, thumbnail_user=message.author))
            return

        if settings.get("block_nsfw_in_sfw_channels", True) and message.attachments and not getattr(message.channel, "is_nsfw", lambda: False)():
            is_img = any(att.content_type and att.content_type.startswith("image/") for att in message.attachments)
            if is_img:
                try: await message.delete()
                except discord.Forbidden: pass
                ch = self._log_channel(message.guild, settings)
                if ch: await ch.send(embed=ok_embed("Image Blocked", f"{message.author.mention} in {message.channel.mention}", requester=message.author, thumbnail_user=message.author))

        thr = int(settings.get("spam_threshold", 7))
        win = int(settings.get("spam_window", 5))
        key = (message.guild.id, message.author.id)
        now = datetime.now(timezone.utc)
        arr = bot.spam_cache.setdefault(key, [])
        arr.append(now)
        bot.spam_cache[key] = [t for t in arr if (now - t).total_seconds() <= win]
        if len(bot.spam_cache[key]) >= thr:
            try: await message.delete()
            except discord.Forbidden: pass
            await self._punish(message.guild, message.author, settings, f"Spam: {len(bot.spam_cache[key])}/{thr} in {win}s", actor=message.author)
            bot.spam_cache[key].clear()

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        settings = await self.get_settings(guild.id)
        thr = int(settings.get("channel_delete_threshold", 3))
        win = int(settings.get("channel_delete_window", 15))
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id:
                    actor = guild.get_member(entry.user.id)
                    if not actor: return
                    key = (guild.id, actor.id)
                    now = datetime.now(timezone.utc)
                    arr = bot.chan_del_cache.setdefault(key, [])
                    arr.append(now)
                    bot.chan_del_cache[key] = [t for t in arr if (now - t).total_seconds() <= win]
                    if len(bot.chan_del_cache[key]) >= thr:
                        g = await self.bot.db.get_guild(guild.id)
                        wl = set(g.get("whitelist_ids", []))
                        if actor.id not in wl:
                            await self._punish(guild, actor, settings, f"Mass channel deletions ({len(bot.chan_del_cache[key])}/{thr} in {win}s)", actor=actor)
                            bot.chan_del_cache[key].clear()
                    return
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        guild = after.guild
        settings = await self.get_settings(guild.id)
        if after.permissions.value != before.permissions.value:
            newly = discord.Permissions(after.permissions.value & ~before.permissions.value)
            if (newly.administrator or newly.manage_guild or newly.manage_roles or
                newly.manage_channels or newly.kick_members or newly.ban_members):
                try:
                    async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.role_update):
                        if entry.target.id == after.id:
                            actor = guild.get_member(entry.user.id)
                            g = await self.bot.db.get_guild(guild.id)
                            wl = set(g.get("whitelist_ids", []))
                            if actor and actor.id not in wl:
                                await self._punish(guild, actor, settings, f"Dangerous permission grant on role {BOLD(after.name)}", actor=actor)
                                if settings.get("auto_revoke_dangerous_perms", True):
                                    await after.edit(permissions=before.permissions, reason="Guardian++ revert dangerous perms")
                            return
                except discord.Forbidden:
                    pass

# ---------------- Utility ----------------
class Utility(commands.Cog):
    def __init__(self, bot: GuardianPlus):
        self.bot = bot

    @commands.command(name="say")
    @commands.has_guild_permissions(manage_messages=True)
    async def say(self, ctx: commands.Context, *, text: str):
        await ctx.send(embed=ok_embed("Say", text, requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="announce")
    @commands.has_guild_permissions(manage_guild=True)
    async def announce(self, ctx: commands.Context, channel: Optional[discord.TextChannel], *, text: str):
        ch = channel or ctx.channel
        await ch.send(embed=ok_embed("Announcement", text, requester=ctx.author, thumbnail_user=ctx.author))
        if ch.id != ctx.channel.id:
            await ctx.reply(embed=ok_embed("Announced", f"Sent to {ch.mention}", requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="poll")
    async def poll(self, ctx: commands.Context, question: str, *options: str):
        if not options or len(options) > 10:
            return await ctx.reply(embed=ok_embed("Usage", "poll <question> <option1> <option2> ... (max 10)", requester=ctx.author, thumbnail_user=ctx.author))
        e = ok_embed("Poll", f"{BOLD(question)}\n\n" + "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)]), requester=ctx.author, thumbnail_user=ctx.author)
        msg = await ctx.send(embed=e)
        emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        for i in range(len(options)):
            await msg.add_reaction(emojis[i])

    @commands.command(name="purge")
    @commands.has_guild_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int):
        await ctx.channel.purge(limit=amount+1)
        msg = await ctx.send(embed=ok_embed("Purged", f"Deleted {BOLD(str(amount))} messages.", requester=ctx.author, thumbnail_user=ctx.author))
        await asyncio.sleep(3); await msg.delete()

    @commands.command(name="purgeuser")
    @commands.has_guild_permissions(manage_messages=True)
    async def purgeuser(self, ctx: commands.Context, member: discord.Member, amount: int=50):
        def is_user(m): return m.author.id == member.id
        deleted = await ctx.channel.purge(limit=amount, check=is_user, before=None)
        await ctx.send(embed=ok_embed("Purged User", f"Deleted {BOLD(str(len(deleted)))} messages from {member.mention}.", requester=ctx.author, thumbnail_user=ctx.author), delete_after=3)

    @commands.command(name="purgecontains")
    @commands.has_guild_permissions(manage_messages=True)
    async def purgecontains(self, ctx: commands.Context, keyword: str, amount: int=100):
        def has_kw(m): return keyword.lower() in (m.content or "").lower()
        deleted = await ctx.channel.purge(limit=amount, check=has_kw)
        await ctx.send(embed=ok_embed("Purged Contains", f"Deleted {BOLD(str(len(deleted)))} messages containing {CODE(keyword)}.", requester=ctx.author, thumbnail_user=ctx.author), delete_after=3)

    @commands.command(name="purgefiles")
    @commands.has_guild_permissions(manage_messages=True)
    async def purgefiles(self, ctx: commands.Context, amount: int=100):
        def has_file(m): return any(a.size for a in m.attachments)
        deleted = await ctx.channel.purge(limit=amount, check=has_file)
        await ctx.send(embed=ok_embed("Purged Files", f"Deleted {BOLD(str(len(deleted)))} messages with attachments.", requester=ctx.author, thumbnail_user=ctx.author), delete_after=3)

    @commands.command(name="purgebots")
    @commands.has_guild_permissions(manage_messages=True)
    async def purgebots(self, ctx: commands.Context, amount: int=100):
        def is_bot(m): return m.author.bot
        deleted = await ctx.channel.purge(limit=amount, check=is_bot)
        await ctx.send(embed=ok_embed("Purged Bots", f"Deleted {BOLD(str(len(deleted)))} bot messages.", requester=ctx.author, thumbnail_user=ctx.author), delete_after=3)

    @commands.command(name="slowmode")
    @commands.has_guild_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, seconds: int):
        await ctx.channel.edit(slowmode_delay=max(0, min(seconds, 21600)))
        await ctx.reply(embed=ok_embed("Slowmode", f"Set to {CODE(str(seconds)+'s')}", requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="lock")
    @commands.has_guild_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context):
        ow = ctx.channel.overwrites_for(ctx.guild.default_role)
        ow.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=ow)
        await ctx.reply(embed=ok_embed("Locked", f"{ctx.channel.mention}", requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="unlock")
    @commands.has_guild_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context):
        ow = ctx.channel.overwrites_for(ctx.guild.default_role)
        ow.send_messages = None
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=ow)
        await ctx.reply(embed=ok_embed("Unlocked", f"{ctx.channel.mention}", requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="nuke")
    @commands.has_guild_permissions(manage_channels=True)
    async def nuke(self, ctx: commands.Context):
        pos = ctx.channel.position
        name = ctx.channel.name
        topic = ctx.channel.topic
        cate = ctx.channel.category
        await ctx.channel.delete(reason=f"Nuke by {ctx.author}")
        ch = await ctx.guild.create_text_channel(name=name, topic=topic, category=cate, position=pos, reason="Nuked channel")
        await ch.send(embed=ok_embed("Nuked", f"Channel cleaned.", requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="snipe")
    async def snipe(self, ctx: commands.Context):
        key = (ctx.guild.id, ctx.channel.id)
        sn = bot.snipes.get(key)
        if not sn:
            return await ctx.reply(embed=ok_embed("Snipe", "Nothing to snipe yet.", requester=ctx.author, thumbnail_user=ctx.author))
        author, content, t = sn
        await ctx.reply(embed=ok_embed(f"Sniped {author}", content or "*<no content>*", requester=ctx.author, thumbnail_user=author))

    @commands.command(name="editsnipe")
    async def editsnipe(self, ctx: commands.Context):
        key = (ctx.guild.id, ctx.channel.id)
        sn = bot.editsnipes.get(key)
        if not sn:
            return await ctx.reply(embed=ok_embed("Edit Snipe", "Nothing to snipe yet.", requester=ctx.author, thumbnail_user=ctx.author))
        author, before, after, t = sn
        desc = f"{UNDER('Before')}: {before or '*<no content>*'}\n{UNDER('After')}: {after or '*<no content>*'}"
        await ctx.reply(embed=ok_embed(f"Edited by {author}", desc, requester=ctx.author, thumbnail_user=author))

    @commands.command(name="afk")
    async def afk(self, ctx: commands.Context, *, reason: str="AFK"):
        bot.afk[ctx.author.id] = reason
        await ctx.reply(embed=ok_embed("AFK Set", f"{ctx.author.mention} is AFK — {ITAL(reason)}", requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="remindme")
    async def remindme(self, ctx: commands.Context, duration: str, *, text: str):
        secs = parse_duration(duration, 300)
        await ctx.reply(embed=ok_embed("Reminder Set", f"In {BOLD(human_timedelta(timedelta(seconds=secs)))}: {text}", requester=ctx.author, thumbnail_user=ctx.author))
        await asyncio.sleep(secs)
        try:
            await ctx.author.send(embed=ok_embed("Reminder", text, requester=ctx.author, thumbnail_user=ctx.author))
        except Exception:
            pass

    @commands.command(name="softban")
    @commands.has_guild_permissions(ban_members=True)
    async def softban(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str]=None):
        await member.ban(reason=reason or f"Softban by {ctx.author}", delete_message_days=1)
        await ctx.guild.unban(member, reason="Softban unban")
        await ctx.reply(embed=ok_embed("Softbanned", f"{member}", requester=ctx.author, thumbnail_user=ctx.author))

# ---------------- Info ----------------
class Info(commands.Cog):
    def __init__(self, bot: GuardianPlus):
        self.bot = bot

    @commands.command(name="whois")
    async def whois(self, ctx: commands.Context, member: Optional[discord.Member]=None):
        m = member or ctx.author
        e = ok_embed(f"User Info — {m}", f"ID: {CODE(str(m.id))}\nJoined: <t:{int(m.joined_at.timestamp())}:R>\nCreated: <t:{int(m.created_at.timestamp())}:R>", requester=ctx.author, thumbnail_user=m)
        e.add_field(name="Top Role", value=str(m.top_role), inline=True)
        e.add_field(name="Bot?", value=str(m.bot), inline=True)
        await ctx.reply(embed=e)

    @commands.command(name="avatar")
    async def avatar(self, ctx: commands.Context, member: Optional[discord.Member]=None):
        m = member or ctx.author
        url = avatar_url(m)
        e = ok_embed(f"Avatar — {m}", f"[Open avatar]({url})", requester=ctx.author, thumbnail_user=m)
        if url: e.set_image(url=url)
        await ctx.reply(embed=e)

    @commands.command(name="banner")
    async def banner(self, ctx: commands.Context, member: Optional[discord.Member]=None):
        m = member or ctx.author
        u = await ctx.guild.fetch_member(m.id)
        user = await bot.fetch_user(u.id)
        if user.banner:
            url = user.banner.url
            e = ok_embed(f"Banner — {m}", f"[Open banner]({url})", requester=ctx.author, thumbnail_user=m)
            e.set_image(url=url)
            await ctx.reply(embed=e)
        else:
            await ctx.reply(embed=ok_embed("Banner", "No banner set.", requester=ctx.author, thumbnail_user=m))

    @commands.command(name="serverinfo")
    async def serverinfo(self, ctx: commands.Context):
        g = ctx.guild
        e = ok_embed(f"Server Info — {g.name}", f"ID: {CODE(str(g.id))}\nMembers: {BOLD(str(g.member_count))}\nCreated: <t:{int(g.created_at.timestamp())}:R>", requester=ctx.author, thumbnail_user=ctx.author)
        e.add_field(name="Owner", value=str(g.owner), inline=True)
        e.add_field(name="Channels", value=str(len(g.channels)), inline=True)
        e.add_field(name="Roles", value=str(len(g.roles)), inline=True)
        await ctx.reply(embed=e)

    @commands.command(name="channelinfo")
    async def channelinfo(self, ctx: commands.Context, channel: Optional[discord.TextChannel]=None):
        ch = channel or ctx.channel
        e = ok_embed(f"Channel Info — #{ch.name}", f"ID: {CODE(str(ch.id))}\nCreated: <t:{int(ch.created_at.timestamp())}:R>", requester=ctx.author, thumbnail_user=ctx.author)
        await ctx.reply(embed=e)

    @commands.command(name="roleinfo")
    async def roleinfo(self, ctx: commands.Context, role: discord.Role):
        e = ok_embed(f"Role Info — {role.name}", f"ID: {CODE(str(role.id))}\nColor: {CODE(str(role.color))}", requester=ctx.author, thumbnail_user=ctx.author)
        e.add_field(name="Members", value=str(len(role.members)), inline=True)
        e.add_field(name="Position", value=str(role.position), inline=True)
        await ctx.reply(embed=e)

    @commands.command(name="emoji")
    async def emoji(self, ctx: commands.Context):
        ems = ", ".join([str(e) for e in ctx.guild.emojis[:50]]) or "*None*"
        await ctx.reply(embed=ok_embed("Emojis", ems, requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="roles")
    async def roles(self, ctx: commands.Context):
        txt = ", ".join([r.name for r in ctx.guild.roles[:50]]) or "*None*"
        await ctx.reply(embed=ok_embed("Roles", txt, requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="permissions")
    async def permissions(self, ctx: commands.Context, member: Optional[discord.Member]=None):
        m = member or ctx.author
        perms = [name.replace('_',' ').title() for name, val in m.guild_permissions if val]
        await ctx.reply(embed=ok_embed(f"Permissions — {m}", ", ".join(perms) or "*None*", requester=ctx.author, thumbnail_user=m))

# ---------------- Setup Wizard & setters ----------------
class SetupCog(commands.Cog):
    def __init__(self, bot: GuardianPlus):
        self.bot = bot

    @commands.command(name="setup")
    @commands.has_guild_permissions(manage_guild=True)
    async def setup(self, ctx: commands.Context):
        await ctx.reply(embed=ok_embed("Setup Wizard", "Answer a few questions. Type `cancel` to abort.", requester=ctx.author, thumbnail_user=ctx.author))

        def check(m: discord.Message):
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

        gdata = await self.bot.db.get_guild(ctx.guild.id)
        ant = {**ANTI_DEFAULTS, **gdata.get("antinuke", {})}

        await ctx.send(embed=ok_embed("Step 1/6 — Log Channel", "Mention a text channel or type `auto`.", requester=ctx.author, thumbnail_user=ctx.author))
        try: msg = await self.bot.wait_for("message", timeout=120, check=check)
        except asyncio.TimeoutError:
            return await ctx.send(embed=ok_embed("Setup Cancelled", "Timed out.", requester=ctx.author, thumbnail_user=ctx.author))
        if msg.content.lower() == "cancel": return await ctx.send(embed=ok_embed("Setup Cancelled", "You cancelled the wizard.", requester=ctx.author, thumbnail_user=ctx.author))
        if msg.content.lower() == "auto":
            ch = discord.utils.get(ctx.guild.text_channels, name="guardian-log") \
                 or discord.utils.get(ctx.guild.text_channels, name="mod-log") \
                 or await ctx.guild.create_text_channel("guardian-log", reason="Setup wizard")
            log_ch_id = ch.id
        else:
            if msg.channel_mentions:
                log_ch_id = msg.channel_mentions[0].id
            else:
                return await ctx.send(embed=ok_embed("Setup Cancelled", "No channel mentioned.", requester=ctx.author, thumbnail_user=ctx.author))

        await ctx.send(embed=ok_embed("Step 2/6 — Jail Role", "Mention a role or type `auto`.", requester=ctx.author, thumbnail_user=ctx.author))
        try: msg = await self.bot.wait_for("message", timeout=120, check=check)
        except asyncio.TimeoutError:
            return await ctx.send(embed=ok_embed("Setup Cancelled", "Timed out.", requester=ctx.author, thumbnail_user=ctx.author))
        if msg.content.lower() == "cancel": return await ctx.send(embed=ok_embed("Setup Cancelled", "You cancelled the wizard.", requester=ctx.author, thumbnail_user=ctx.author))
        if msg.content.lower() == "auto":
            role = discord.utils.get(ctx.guild.roles, name="Jail") or await ctx.guild.create_role(name="Jail", reason="Setup wizard")
            jail_role_id = role.id
            for ch in ctx.guild.channels:
                try:
                    ow = ch.overwrites or {}
                    ow[role] = discord.PermissionOverwrite(
                        view_channel=False, send_messages=False, speak=False,
                        send_messages_in_threads=False, add_reactions=False
                    )
                    await ch.edit(overwrites=ow)
                except Exception:
                    pass
            jail_ch = discord.utils.get(ctx.guild.text_channels, name="jail")
            if not jail_ch:
                jail_ch = await ctx.guild.create_text_channel("jail", reason="Setup wizard")
                await jail_ch.set_permissions(role, view_channel=True, send_messages=True)
        else:
            if msg.raw_role_mentions:
                jail_role_id = msg.raw_role_mentions[0]
            else:
                return await ctx.send(embed=ok_embed("Setup Cancelled", "No role mentioned.", requester=ctx.author, thumbnail_user=ctx.author))

        await ctx.send(embed=ok_embed("Step 3/6 — Spam Threshold", "Default 7. Send a number.", requester=ctx.author, thumbnail_user=ctx.author))
        try: msg = await self.bot.wait_for("message", timeout=90, check=check)
        except asyncio.TimeoutError:
            return await ctx.send(embed=ok_embed("Setup Cancelled", "Timed out.", requester=ctx.author, thumbnail_user=ctx.author))
        if msg.content.lower() == "cancel": return await ctx.send(embed=ok_embed("Setup Cancelled", "You cancelled the wizard.", requester=ctx.author, thumbnail_user=ctx.author))
        try: ant["spam_threshold"] = int(msg.content)
        except ValueError: pass

        await ctx.send(embed=ok_embed("Step 4/6 — Spam Window (seconds)", "Default 5. Send a number.", requester=ctx.author, thumbnail_user=ctx.author))
        try: msg = await self.bot.wait_for("message", timeout=90, check=check)
        except asyncio.TimeoutError:
            return await ctx.send(embed=ok_embed("Setup Cancelled", "Timed out.", requester=ctx.author, thumbnail_user=ctx.author))
        if msg.content.lower() == "cancel": return await ctx.send(embed=ok_embed("Setup Cancelled", "You cancelled the wizard.", requester=ctx.author, thumbnail_user=ctx.author))
        try: ant["spam_window"] = int(msg.content)
        except ValueError: pass

        await ctx.send(embed=ok_embed("Step 5/6 — Channel Delete Threshold", "Default 3. Send a number.", requester=ctx.author, thumbnail_user=ctx.author))
        try: msg = await self.bot.wait_for("message", timeout=90, check=check)
        except asyncio.TimeoutError:
            return await ctx.send(embed=ok_embed("Setup Cancelled", "Timed out.", requester=ctx.author, thumbnail_user=ctx.author))
        if msg.content.lower() == "cancel": return await ctx.send(embed=ok_embed("Setup Cancelled", "You cancelled the wizard.", requester=ctx.author, thumbnail_user=ctx.author))
        try: ant["channel_delete_threshold"] = int(msg.content)
        except ValueError: pass

        await ctx.send(embed=ok_embed("Step 6/6 — Channel Delete Window (seconds)", "Default 15. Send a number.", requester=ctx.author, thumbnail_user=ctx.author))
        try: msg = await self.bot.wait_for("message", timeout=90, check=check)
        except asyncio.TimeoutError:
            return await ctx.send(embed=ok_embed("Setup Cancelled", "Timed out.", requester=ctx.author, thumbnail_user=ctx.author))
        if msg.content.lower() == "cancel": return await ctx.send(embed=ok_embed("Setup Cancelled", "You cancelled the wizard.", requester=ctx.author, thumbnail_user=ctx.author))
        try: ant["channel_delete_window"] = int(msg.content)
        except ValueError: pass

        gdata["log_channel_id"] = log_ch_id
        gdata["jail_role_id"] = jail_role_id
        gdata["antinuke"] = ant
        await self.bot.db.set_guild(ctx.guild.id, gdata)
        await ctx.send(embed=ok_embed("Setup Complete", "All set! Use -help for commands.", requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="setlog")
    @commands.has_guild_permissions(manage_guild=True)
    async def setlog(self, ctx: commands.Context, channel: discord.TextChannel):
        await self.bot.db.update_guild(ctx.guild.id, {"log_channel_id": channel.id})
        await ctx.reply(embed=ok_embed("Logging Channel", f"Set to {channel.mention}", requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="setjail")
    @commands.has_guild_permissions(manage_roles=True)
    async def setjail(self, ctx: commands.Context, role: discord.Role):
        await self.bot.db.update_guild(ctx.guild.id, {"jail_role_id": role.id})
        await ctx.reply(embed=ok_embed("Jail Role", f"Set to {role.mention}", requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="setwhitelist")
    @commands.has_guild_permissions(manage_guild=True)
    async def setwhitelist(self, ctx: commands.Context, action: str, member: discord.Member):
        g = await self.bot.db.get_guild(ctx.guild.id)
        wl = set(g.get("whitelist_ids", []))
        if action.lower() == "add": wl.add(member.id)
        elif action.lower() == "remove": wl.discard(member.id)
        else:
            return await ctx.reply(embed=ok_embed("Usage", "-setwhitelist add @user OR -setwhitelist remove @user", requester=ctx.author, thumbnail_user=ctx.author))
        await self.bot.db.update_guild(ctx.guild.id, {"whitelist_ids": list(wl)})
        await ctx.reply(embed=ok_embed("Whitelist Updated", f"{action.title()} {member}", requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="setantinuke")
    @commands.has_guild_permissions(manage_guild=True)
    async def setantinuke(self, ctx: commands.Context, key: str, value: str):
        numeric = {"timeout_seconds", "channel_delete_threshold", "channel_delete_window", "spam_threshold", "spam_window"}
        boolean = {"auto_revoke_dangerous_perms", "block_invites", "block_nsfw_in_sfw_channels"}
        patch = {}
        if key in numeric:
            patch[key] = int(value)
        elif key in boolean:
            patch[key] = value.lower() in ("true","1","on","yes","y")
        else:
            return await ctx.reply(embed=ok_embed("Unknown Key", f"{CODE(key)} not recognized.", requester=ctx.author, thumbnail_user=ctx.author))
        g = await self.bot.db.get_guild(ctx.guild.id)
        s = g.get("antinuke", {}); s.update(patch)
        await self.bot.db.update_guild(ctx.guild.id, {"antinuke": s})
        await ctx.reply(embed=ok_embed("Anti-Nuke Updated", f"{CODE(key)} → {CODE(str(patch[key]))}", requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="setinvites")
    @commands.has_guild_permissions(manage_guild=True)
    async def setinvites(self, ctx: commands.Context, flag: str):
        val = flag.lower() in ("on","true","1","yes","y")
        g = await self.bot.db.get_guild(ctx.guild.id)
        s = g.get("antinuke", {}); s["block_invites"] = val
        await self.bot.db.update_guild(ctx.guild.id, {"antinuke": s})
        await ctx.reply(embed=ok_embed("Invite Filter", f"Set to {CODE(str(val))}", requester=ctx.author, thumbnail_user=ctx.author))

    @commands.command(name="setnsfwblock")
    @commands.has_guild_permissions(manage_guild=True)
    async def setnsfwblock(self, ctx: commands.Context, flag: str):
        val = flag.lower() in ("on","true","1","yes","y")
        g = await self.bot.db.get_guild(ctx.guild.id)
        s = g.get("antinuke", {}); s["block_nsfw_in_sfw_channels"] = val
        await self.bot.db.update_guild(ctx.guild.id, {"antinuke": s})
        await ctx.reply(embed=ok_embed("NSFW Image Block", f"Set to {CODE(str(val))}", requester=ctx.author, thumbnail_user=ctx.author))

    @app_commands.command(name="setup", description="Quick setup for Guardian++.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_slash(self, interaction: discord.Interaction):
        g = await self.bot.db.get_guild(interaction.guild_id)
        base = {**{"log_channel_id": None, "jail_role_id": None, "antinuke": {}}, **g}
        base["antinuke"] = {**ANTI_DEFAULTS, **base.get("antinuke", {})}
        await self.bot.db.set_guild(interaction.guild_id, base)
        await interaction.response.send_message(
            embed=ok_embed("Setup (Quick)", "Use `/prefix`, `/help`, and setters like `-setlog`, `-setjail`, `-setantinuke`. For full wizard, use `-setup`.", requester=interaction.user, thumbnail_user=interaction.user),
            ephemeral=True
        )

# ---------------- Main run ----------------
if __name__ == "__main__":
    try:
        banner()
        bot.run(TOKEN, log_handler=None)
    except KeyboardInterrupt:
        print(f"{Fore.RED if COLOR_ENABLED else ''}\n[Guardian++] Shutting down (KeyboardInterrupt).{Style.RESET_ALL if COLOR_ENABLED else ''}")
    except Exception as e:
        print(f"{Fore.RED if COLOR_ENABLED else ''}[Guardian++] Fatal error: {e}{Style.RESET_ALL if COLOR_ENABLED else ''}")
        raise
