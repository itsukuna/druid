import discord
import os
import logging

from discord.ext import commands

token = os.getenv("discord_token")

logger = logging.getLogger("discord")

intents = discord.Intents.all()
intents.members = True
intents.voice_states = True

bot = discord.Bot(intents=intents)


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Over Server"))
    logger.info(f"We have logged in as {bot.user}")
    logger.info('Loading extensions:')


def load_cogs():
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
