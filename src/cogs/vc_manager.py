from discord.ext import commands

import discord
import logging
import os

logger = logging.getLogger('discord')
category_name = os.getenv('category')
vc_name = os.getenv('start_vc')


class VoiceChannelManager(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.temp_channels = {}

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f'{self.__class__.__name__} is ready.')

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        lobby = discord.utils.get(guild.voice_channels, name=vc_name)
        category = discord.utils.get(guild.categories, name=category_name)

        if after.channel == lobby and before.channel != lobby:
            try:
                temp_channel = await guild.create_voice_channel(name=f"{member.display_name}'s Channel", category=category)
                self.temp_channels[temp_channel.id] = temp_channel
                logger.info(f'created vc: {temp_channel}')
                await member.move_to(temp_channel)
            except Exception as e:
                logger.error(f'channel creation error: {e}')

        if before.channel and before.channel.id in self.temp_channels:
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                    logger.info(f'removed vc: {before.channel}')
                    del self.temp_channels[before.channel.id]
                except Exception as e:
                    logger.error(f'channel deletion error: {e}')


def setup(bot):
    bot.add_cog(VoiceChannelManager(bot))
