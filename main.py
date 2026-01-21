import os
from dotenv import load_dotenv

import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone

from utils import is_admin, get_player_count, start_vm, stop_vm, stop_mc_server, get_vm_status
from webserver import run_webserver

import threading

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)
empty_time = None
trigger_shutdown = False

VOTE_EMOJI = "👍"
REQUIRED_VOTES = 4

active_vote_message_id = None
current_votes = set()


CLOCK = "<a:Minecraft_clock:1462830831092498671>"
PARROT = "<a:dancing_parrot:1462833253692997797>"
CHEST = "<a:MinecraftChestOpening:1462837623625355430>"
TNT = "<a:TNT:1462841582376980586>"
FLAME = "<a:animated_flame:1462846702191907013>"
SAD = "<:jeb_screm:1462848647149519145>"

def embed_starting():
    return discord.Embed(
        title=f"{CLOCK} Starting PESU Minecraft Server",
        description=(
            "Your beloved server is booting up!\n\n"
            f"This may take a while {PARROT}"
        ),
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc)
    ).set_footer(text="Xymic")\
     .set_thumbnail(url="https://images-ext-1.discordapp.net/external/7nIEsery5zNVdedxw1ZE4KbpDsdbynTfKfBiVvBxH4k/%3Fsize%3D4096/https/cdn.discordapp.com/icons/1406919525831540817/0c5be54039c065ad713c2e60cdcf1d3d.png?format=webp&quality=lossless&width=579&height=579")

def embed_started():
    return discord.Embed(
        title="✅ Server Online",
        description=(
            
            f"Get in losers - the server is going live! {CHEST}"
        ),
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc)
    ).set_footer(text="Xymic")

def embed_manual_stop():
    return discord.Embed(
        title=f"{TNT} Server Shutdown Requested",
        description=(
            "The Minecraft server is now shutting down.\n"
        ),
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc)
    ).set_footer(text="Xymic")

def embed_auto_shutdown():
    return discord.Embed(
        title=f"{SAD} Server Idle",
        description=(
            "The server has been empty for **1 minute**.\n"
            "Initiating automatic shutdown sequence…"
        ),
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    ).set_footer(text="Xymic")

def embed_stopped():
    return discord.Embed(
        title="❌ Server Stopped",
        description=(
            "The Minecraft server has been stopped successfully.\n\n"
            f"{FLAME} The VM is now powering off to save resources."
        ),
        color=discord.Color.red(),
        timestamp=datetime.now(timezone.utc)
    ).set_footer(text="Xymic")\
     .set_thumbnail(url="https://images-ext-1.discordapp.net/external/7nIEsery5zNVdedxw1ZE4KbpDsdbynTfKfBiVvBxH4k/%3Fsize%3D4096/https/cdn.discordapp.com/icons/1406919525831540817/0c5be54039c065ad713c2e60cdcf1d3d.png?format=webp&quality=lossless&width=579&height=579")

def embed_no_permission():
    return discord.Embed(
        title="🚫 Permission Denied",
        description=(
            "You don’t have permission to use this command.\n\n"
            "🔐 This action is restricted to server admins only."
        ),
        color=discord.Color.dark_red(),
        timestamp=datetime.now(timezone.utc)
    ).set_footer(text="Xymic")

def embed_vote_start():
    return discord.Embed(
        title="🗳️ Vote to Start Server",
        description=(
            f"React with {VOTE_EMOJI} to start the Minecraft server.\n\n"
            f"Votes needed: **{REQUIRED_VOTES+1}**"
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    ).set_footer(text="Xymic")


def embed_vm_stop():
    return discord.Embed(
        title="The VM has been stopped.",
        color=discord.Color.red(),
        timestamp=datetime.now(timezone.utc)
).set_footer(text="Xymic")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    check_server.start()

@bot.event
async def on_reaction_add(reaction, user):
    global current_votes, active_vote_message_id

    if user.bot:
        return
    if active_vote_message_id is None:
        return
    if reaction.message.id != active_vote_message_id:
        return
    if str(reaction.emoji) != VOTE_EMOJI:
        return
    if user.id in current_votes:
        return

    current_votes.add(user.id)

    print(f"Votes: {len(current_votes)}/{REQUIRED_VOTES}")

    if len(current_votes) >= REQUIRED_VOTES:
        channel = reaction.message.channel
        active_vote_message_id = None
        current_votes.clear()

        await channel.send(embed=embed_starting())
        await start_vm()
        await channel.send(embed=embed_started())


@bot.command()
async def start(ctx):
    global active_vote_message_id, current_votes
    if is_admin(ctx):
        await ctx.reply(embed=embed_starting())
        await start_vm()
        await ctx.reply(embed=embed_started())
        return
    
    else:
        current_votes = set()
        vote_message = await ctx.reply(embed=embed_vote_start())
        active_vote_message_id = vote_message.id
        await vote_message.add_reaction(VOTE_EMOJI)

@bot.command()
async def stop(ctx):
    if not is_admin(ctx):
        await ctx.reply(embed=embed_no_permission())
        return
    await ctx.reply(embed=embed_manual_stop())
    await shutdown_server(manual=True)
    

@tasks.loop(seconds=10)
async def check_server():
    global empty_time, trigger_shutdown
    status = await get_vm_status()    

    if status == "RUNNING":
        player_count = await get_player_count()
        if player_count is None:
            return 

        print(f'Players online: {player_count}')
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


async def shutdown_server(manual=False):
    channel = discord.utils.get(bot.get_all_channels(), name='minecraft-chat')
    if channel:
        if manual:
            pass
            # await channel.send(embed=embed_manual_stop())
        else:
            await channel.send(embed=embed_auto_shutdown())
        await stop_mc_server()
        await channel.send(embed=embed_stopped())
        await stop_vm()
        await channel.send(embed=embed_vm_stop())



threading.Thread(target=run_webserver).start()

bot.run(BOT_TOKEN)
