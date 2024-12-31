from discord.ext import commands
import logging
import discord

logger = logging.getLogger("discord")

class Default(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f'{self.__class__.__name__} is ready.')

    @commands.slash_command(name='ping')
    async def ping(self, ctx):
        try:
            await ctx.respond(f'Pong {round(self.bot.latency * 100)}ms!')
        except Exception as e:
            logger.info(f'command execution error: {e}')

    @commands.slash_command(name='help', description='List all commands and their usage.')
    async def help(self, ctx):
        embed = discord.Embed(
            title="Help - List of Commands",
            description="Here are the available commands and their usage:",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="/ping",
            value="Check the bot's latency.",
            inline=False,
        )
        embed.add_field(
            name="/voice setup",
            value="Creates a default configuration for temporary voice channels.",
            inline=False,
        )
        embed.add_field(
            name="/voice reset",
            value="Reset the configuration for your server.",
            inline=False,
        )
        embed.add_field(
            name="/voice cleanup",
            value="Cleanup temporary voice channels for your server.",
            inline=False,
        )
        embed.add_field(
            name="/voice rename <new_name>",
            value="Rename your temporary voice channel.",
            inline=False,
        )
        embed.add_field(
            name="/voice limit <number>",
            value="Set a user limit for your temporary voice channel.",
            inline=False,
        )
        embed.add_field(
            name="/voice privacy <public/private>",
            value="Make your temporary voice channel public or private.",
            inline=False,
        )
        embed.add_field(
            name="/voice kick <user>",
            value="Kick a user from your temporary voice channel.",
            inline=False,
        )
        embed.add_field(
            name="/voice ban <user>",
            value="Ban a user from your temporary voice channel.",
            inline=False,
        )
        embed.add_field(
            name="/voice unban <user>",
            value="Unban a user from your temporary voice channel.",
            inline=False,
        )
        embed.add_field(
            name="/voice invite",
            value="Generate an invite link for your temporary voice channel.",
            inline=False,
        )
        embed.add_field(
            name="/automod add_bad_word <word>",
            value="Add a word to the bad words list.",
            inline=False,
        )
        embed.add_field(
            name="/automod remove_bad_word <word>",
            value="Remove a word from the bad words list.",
            inline=False,
        )
        embed.add_field(
            name="/automod list_bad_words",
            value="List all bad words.",
            inline=False,
        )
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(Default(bot))