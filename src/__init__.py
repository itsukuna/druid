import discord
import os
import logging

from discord.ext import commands

# Fetch bot token from environment
token = os.getenv("discord_token")
if not token:
    raise ValueError("No 'discord_token' environment variable found.")

logger = logging.getLogger("discord")

# Set up intents
intents = discord.Intents.all()
intents.members = True
intents.voice_states = True

bot = discord.Bot(intents=intents)


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Over Server"))
    logger.info(f"We have logged in as {bot.user}")
    logger.info('Loading extensions:')


@bot.event
async def on_disconnect():
    logger.info(f"{bot.user} has disconnected from Discord.")


def load_cogs():
    """
    Dynamically load all cogs from the src/cogs directory.
    """
    cogs = [f"src.cogs.{filename[:-3]}" for filename in os.listdir(
        "./src/cogs") if filename.endswith(".py")]
    for cog in cogs:
        try:
            bot.load_extension(cog)
        except Exception as e:
            logger.error(f"Failed to load extension {cog}. Error: {e}")


def run_bot():
    logger.info("Discord bot booting")
    load_cogs()
    bot.run(token)
