from discord.ext import commands
import logging

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
            await ctx.send(f'Pong {round(self.bot.latency * 100)}ms!')
        except Exception as e:
            logger.info(f'command execution error: {e}')


def setup(bot):
    bot.add_cog(Default(bot))