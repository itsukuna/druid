from discord.ext import commands
import discord
import logging
import re
from database import AutoModDB

logger = logging.getLogger("discord")


class AutoModeration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = AutoModDB()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"{self.__class__.__name__} is ready.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if (
            message.author.bot
            or message.author.guild_permissions.manage_messages
            or message.author.guild_permissions.administrator
        ):
            return

        bad_words = self.db.get_bad_words(message.guild.id)
        if any(
            re.search(rf"\b{word}\b", message.content, re.IGNORECASE)
            for word in bad_words
        ):
            await message.delete()
            embed = discord.Embed(
                title="Message Deleted",
                description=f"{message.author.mention}, your message contained inappropriate content and was removed.",
                color=discord.Color.red(),
            )
            await message.channel.send(embed=embed)
            logger.info(
                f"Deleted inappropriate message from {message.author} in guild {message.guild.id}"
            )

    automod = discord.SlashCommandGroup(
        name="automod", description="Commands for managing auto moderation."
    )

    @automod.command(
        name="add_bad_word", description="Add a word to the bad words list."
    )
    @commands.has_permissions(manage_channels=True)
    async def add_bad_word(self, ctx, word: str):
        self.db.add_bad_word(ctx.guild.id, word)
        await ctx.respond(f"Added `{word}` to the bad words list.", ephemeral=True)
        logger.info(f"Added `{word}` to the bad words list in guild {ctx.guild.id}")

    @automod.command(
        name="remove_bad_word", description="Remove a word from the bad words list."
    )
    @commands.has_permissions(manage_channels=True)
    async def remove_bad_word(self, ctx, word: str):
        self.db.remove_bad_word(ctx.guild.id, word)
        await ctx.respond(f"Removed `{word}` from the bad words list.", ephemeral=True)
        logger.info(f"Removed `{word}` from the bad words list in guild {ctx.guild.id}")

    @automod.command(name="list_bad_words", description="List all bad words.")
    async def list_bad_words(self, ctx):
        bad_words = self.db.get_bad_words(ctx.guild.id)
        await ctx.respond(f"Bad words list: {', '.join(bad_words)}", ephemeral=True)
        logger.info(f"Listed bad words in guild {ctx.guild.id}")


def setup(bot):
    bot.add_cog(AutoModeration(bot))
