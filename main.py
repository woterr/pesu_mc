import os
from dotenv import load_dotenv

import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone

from utils import (
    is_admin,
    get_player_count,
    start_vm,
    stop_vm,
    stop_mc_server,
    get_vm_status,
    format_duration,
    STATS_DB_PATH,
    POLL_INTERVAL,
)
from webserver import run_webserver
from stats.db import init_db
from stats.poller import poll_stats
from stats.graphs import plot_metric
from stats.player_store import upsert_player, get_player_by_name

import threading

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

MC_STATS_URL = os.getenv("MC_STATS_URL")
MC_STATS_TOKEN = os.getenv("MC_STATS_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents)
empty_time = None
trigger_shutdown = False

# stats db conn
db_conn = init_db(STATS_DB_PATH)


CLOCK = "<a:Minecraft_clock:1462830831092498671>"
PARROT = "<a:dancing_parrot:1462833253692997797>"
CHEST = "<a:MinecraftChestOpening:1462837623625355430>"
TNT = "<a:TNT:1462841582376980586>"
FLAME = "<a:animated_flame:1462846702191907013>"
SAD = "<:jeb_screm:1462848647149519145>"


def embed_starting():
    """
    STACK: Discord information
    Send an `Embed` acknowledgment when the server is starting.

    Returns:
        Embed (Discord obj)
    """
    return (
        discord.Embed(
            title=f"{CLOCK} Starting PESU Minecraft Server",
            description=(
                "Your beloved server is booting up!\n\n"
                f"This may take a while {PARROT}"
            ),
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )
        .set_footer(text="Xymic")
        .set_thumbnail(
            url="https://images-ext-1.discordapp.net/external/7nIEsery5zNVdedxw1ZE4KbpDsdbynTfKfBiVvBxH4k/%3Fsize%3D4096/https/cdn.discordapp.com/icons/1406919525831540817/0c5be54039c065ad713c2e60cdcf1d3d.png?format=webp&quality=lossless&width=579&height=579"
        )
    )


def embed_started():
    """
    STACK: Discord information
    Send an `Embed` acknowledgment when the server has started.

    Returns:
        Embed (Discord obj)
    """
    return discord.Embed(
        title="✅ Server Online",
        description=(f"Get in losers - the server is going live! {CHEST}"),
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc),
    ).set_footer(text="Xymic")


def embed_manual_stop():
    """
    STACK: Discord information
    Send an `Embed` acknowledgment when the server is shutting down.

    Returns:
        Embed (Discord obj)
    """
    return discord.Embed(
        title=f"{TNT} Server Shutdown Requested",
        description=("The Minecraft server is now shutting down.\n"),
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc),
    ).set_footer(text="Xymic")


def embed_auto_shutdown():
    """
    STACK: Discord information
    Send an `Embed` acknowledgment when the server stops automatically.

    Returns:
        Embed (Discord obj)
    """
    return discord.Embed(
        title=f"{SAD} Server Idle",
        description=(
            "The server has been empty for **1 minute**.\n"
            "Initiating automatic shutdown sequence…"
        ),
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc),
    ).set_footer(text="Xymic")


def embed_stopped():
    """
    STACK: Discord information
    Send an `Embed` acknowledgment when the server has shut down.

    Returns:
        Embed (Discord obj)
    """
    return (
        discord.Embed(
            title="❌ Server Stopped",
            description=(
                "The Minecraft server has been stopped successfully.\n\n"
                f"{FLAME} The VM is now powering off to save resources."
            ),
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )
        .set_footer(text="Xymic")
        .set_thumbnail(
            url="https://images-ext-1.discordapp.net/external/7nIEsery5zNVdedxw1ZE4KbpDsdbynTfKfBiVvBxH4k/%3Fsize%3D4096/https/cdn.discordapp.com/icons/1406919525831540817/0c5be54039c065ad713c2e60cdcf1d3d.png?format=webp&quality=lossless&width=579&height=579"
        )
    )


def embed_no_permission():
    """
    STACK: Discord permissions
    Send an `Embed` acknowledgment when the user doesn't have permissions to run the command.

    Returns:
        Embed (Discord obj)
    """
    return discord.Embed(
        title="🚫 Permission Denied",
        description=(
            "You don’t have permission to use this command.\n\n"
            "🔐 This action is restricted to server admins only."
        ),
        color=discord.Color.dark_red(),
        timestamp=datetime.now(timezone.utc),
    ).set_footer(text="Xymic")


def embed_vm_stop():
    """
    STACK: VM control
    Send an `Embed` acknowledgment when the Google VM stops.

    Returns:
        Embed (Discord obj)
    """
    return discord.Embed(
        title="The VM has been stopped.",
        color=discord.Color.red(),
        timestamp=datetime.now(timezone.utc),
    ).set_footer(text="Xymic")


@bot.event
async def on_ready():
    """
    STACK: Discord Bot
    Login acknowledgement and start timers for `check_server` and `poll_mc_stats`
    """
    print(f"Logged in as {bot.user}")
    check_server.start()
    poll_mc_stats.start()


@bot.command()
async def start(ctx):
    """
    STACK: Server control
    Start the server.
    """
    if not is_admin(ctx):
        await ctx.reply(embed=embed_no_permission())
        return
    await ctx.reply(embed=embed_starting())
    await start_vm()
    await ctx.reply(embed=embed_started())


@bot.command()
async def stop(ctx):
    """
    STACK: Server control
    Stop the server.
    """
    if not is_admin(ctx):
        await ctx.reply(embed=embed_no_permission())
        return
    await ctx.reply(embed=embed_manual_stop())
    await shutdown_server(manual=True)


@tasks.loop(seconds=POLL_INTERVAL)
async def check_server():
    """
    STACK: Server control
    Poll to check if server has no members for longer than a minute and shutdown accordingly.
    """
    global empty_time, trigger_shutdown
    status = await get_vm_status()

    if status == "RUNNING":
        player_count = await get_player_count()
        if player_count is None:
            return

        print(f"Players online: {player_count}")
        if player_count == 0:
            if empty_time is None:
                empty_time = datetime.now()
            else:
                elapsed = (datetime.now() - empty_time).total_seconds()
                if elapsed >= 60 and not trigger_shutdown:
                    trigger_shutdown = True
                    await shutdown_server()
        else:
            empty_time = None
            trigger_shutdown = False
    else:
        print("Server is off")


@tasks.loop(seconds=POLL_INTERVAL)
async def poll_mc_stats():
    """
    STACK: Stats
    Poll to push instantaneous server stats to SQLite DB.
    """

    await poll_stats(db_conn, MC_STATS_URL, MC_STATS_TOKEN)


@bot.command()
async def stats(ctx, mode=None, player=None):
    """
    STACK: Stats
    Bot command definition for `stats`.
    - If no mode is passed (or unknown mode), return syntax.
    - If the mode is `server`, call stats_server
    - If the mode is player, call stats_player

    Args:
        ctx: Message object
        mode: Whether to get server information or induvidual player information
        player: The player for which information is to be retreived.
    """
    if mode is None:
        await ctx.reply("Usage: `$stats server` or `$stats player <name>`")
        return

    if mode.lower() == "server":
        await stats_server(ctx)
    elif mode.lower() == "player":
        if not player:
            await ctx.reply("Usage: `$stats player <username>`")
            return
        await stats_player(ctx, player)
    else:
        await ctx.reply("Unknown option. Use `server` or `player`.")


@bot.command()
async def graph(ctx, metric=None, minutes=60):
    """
    STACK: Stats
    Bot command definition for `graph`. Parses user command and returns
    matplotlib graph as a file attachment and deletes the file once sent to the user.

    Args:
        ctx: Message object
        metric: CPU, RAM, CHUNKS, JOINS, DEATHS or PLAYERS
        minutes: The amount of time to get datapoints for relative to current time.
                Ex: 60mins = data points from 60 minutes ago to now.
    """
    if not metric:
        await ctx.reply(
            "Usage: `$graph <metric> [minutes]`\n"
            "Examples:\n"
            "`$graph player_count`\n"
            "`$graph cpu_load 30`"
        )
        return

    metric_map = {
        "players": ("player_count", "Players Online", 1),
        "cpu": ("cpu_load", "CPU Load (%)", 100),
        "ram": ("ram_used_mb", "RAM Used (MB)", 1),
        "chunks": ("loaded_chunks", "Loaded Chunks", 1),
        "joins": ("total_joins", "Total Joins", 1),
        "deaths": ("total_deaths", "Total Deaths", 1),
    }

    if metric not in metric_map:
        await ctx.reply(f"Unknown metric.\nAvailable: {', '.join(metric_map.keys())}")
        return

    col, label, scale = metric_map[metric]

    path = plot_metric(
        db_conn,
        col,
        minutes=minutes,
        ylabel=label,
        multiply=scale,
    )

    if not path:
        await ctx.reply("No data available for that time range.")
        return

    file = discord.File(path)
    await ctx.reply(file=file)

    try:
        os.remove(path)
    except Exception as e:
        print(f"[WARN] Failed to delete graph file {path}: {e}")


async def stats_server(ctx):
    """
    STACK: Stats
    Fetches the server statistics from SQLite DB. Constructs discord embed and
    returns to message as reply.

    Args:
        ctx: Message object
    """
    cur = db_conn.cursor()

    # check if server is offline
    cur.execute("SELECT online, timestamp FROM metrics ORDER BY timestamp DESC LIMIT 1")
    latest = cur.fetchone()

    if not latest:
        await ctx.reply("No server data available yet.")
        return

    if latest[0] == 0:
        await ctx.reply("⚠️ Server is currently **offline**.")
        return

    cur.execute(
        """
        SELECT
            player_count,
            cpu_load,
            ram_used_mb,
            ram_max_mb,
            threads,
            loaded_chunks,
            total_joins,
            total_deaths,
            uptime_ms,
            total_runtime_ms,
            total_runtime_hms
        FROM metrics
        WHERE online = 1
        ORDER BY timestamp DESC
        LIMIT 1
    """  # sql query
    )
    row = cur.fetchone()

    if not row:
        await ctx.reply("No server data available.")
        return

    embed = discord.Embed(
        title="Minecraft Server Stats",
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc),
    )

    embed.add_field(name="Players Online", value=row[0], inline=True)
    embed.add_field(name="CPU Load", value=f"{row[1] * 100:.2f}%", inline=True)
    embed.add_field(name="RAM Used", value=f"{row[2]} / {row[3]} MB", inline=True)
    embed.add_field(name="Threads", value=row[4], inline=True)
    embed.add_field(name="Loaded Chunks", value=row[5], inline=True)
    embed.add_field(name="Total Joins", value=row[6], inline=True)
    embed.add_field(name="Total Deaths", value=row[7], inline=True)
    embed.add_field(name="Uptime (current)", value=format_duration(row[8]), inline=True)
    embed.add_field(
        name="Total Runtime", value=row[10], inline=False
    )  # 9 is runtime in ms, 10 is h/s
    await ctx.reply(embed=embed)


async def stats_player(ctx, username):
    """
    STACK: Stats
    Fetches induvidual player statistics based on username. Constructs
    a discord embed and replies to message object. If the server is
    online, a live fetch is attempted, else a DB fetch is attempted.

    Args:
        ctx: Message object
        username: Username of the player in the server.
    """
    import aiohttp

    data = None
    server_online = True

    # try live fetch
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{MC_STATS_URL}?name={username}",
                headers={"X-Stats-Token": MC_STATS_TOKEN},
                timeout=2,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    upsert_player(db_conn, data)
                else:
                    server_online = False
    except Exception:
        server_online = False
    if data:
        upsert_player(db_conn, data)

    # if server offline, fallback to DB
    if not data:
        row = get_player_by_name(db_conn, username)
        if not row:
            await ctx.reply("No stored data found for this player.")
            return

        (
            uuid,
            name,
            total_joins,
            total_deaths,
            total_playtime_ms,
            player_kills,
            mob_kills,
            messages_sent,
            advancement_count,
            first_join_ts,
            last_join_ts,
            last_seen_ts,
            last_updated_ts,
        ) = row

        data = {
            "uuid": uuid,
            "name": name,
            "total_joins": total_joins,
            "total_deaths": total_deaths,
            "total_playtime_ms": total_playtime_ms,
            "player_kills": player_kills,
            "mob_kills": mob_kills,
            "messages_sent": messages_sent,
            "advancement_count": advancement_count,
            "first_join_ts": first_join_ts,
            "last_join_ts": last_join_ts,
            "last_seen_ts": last_seen_ts,
            "online": False,
        }

        await ctx.reply("⚠️ Server is offline. Showing last known data.")

    embed = discord.Embed(
        title=f"Player Stats – {data['name']}",
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc),
    )

    embed.add_field(
        name="Playtime",
        value=format_duration(data["total_playtime_ms"]),
        inline=True,
    )
    embed.add_field(name="Total Joins", value=data["total_joins"], inline=True)
    embed.add_field(name="Deaths", value=data["total_deaths"], inline=True)
    embed.add_field(name="Player Kills", value=data["player_kills"], inline=True)
    embed.add_field(name="Mob Kills", value=data["mob_kills"], inline=True)
    embed.add_field(name="Messages Sent", value=data["messages_sent"], inline=True)
    embed.add_field(name="Advancements", value=data["advancement_count"], inline=True)
    embed.add_field(
        name="First Join",
        value=f"<t:{data['first_join_ts'] // 1000}:R>",
        inline=True,
    )
    embed.add_field(
        name="Last Seen",
        value=f"<t:{data['last_seen_ts'] // 1000}:R>",
        inline=True,
    )

    await ctx.reply(embed=embed)


async def shutdown_server(manual=False):
    """
    STACK: Server control
    Shuts down the minecraft server.

    Args:
        manual: Whether the shutdown was manual or automatic (by polling).
    """
    channel = discord.utils.get(bot.get_all_channels(), name="minecraft-chat")
    if channel:
        if manual:
            await channel.send(embed=embed_manual_stop())
        else:
            await channel.send(embed=embed_auto_shutdown())
        await stop_mc_server()
        await channel.send(embed=embed_stopped())
        await stop_vm()
        await channel.send(embed=embed_vm_stop())


threading.Thread(target=run_webserver, daemon=True).start()

bot.run(BOT_TOKEN)
