from discord.ext import commands
import discord
import logging
import os
import json
import asyncio

logger = logging.getLogger('discord')
category_name = os.getenv('category')
vc_name = os.getenv('start_vc')


class VoiceChannelManager(commands.Cog):
    """
    A Discord Cog to manage temporary voice channels.
    Automatically creates and deletes voice channels based on member activity.
    """

    def __init__(self, bot) -> None:
        self.bot = bot
        self.temp_channels = self.load_temp_vc()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f'{self.__class__.__name__} is ready.')

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """
        Handles the creation and deletion of temporary voice channels based on voice state updates.
        """
        guild = member.guild
        lobby = discord.utils.get(guild.voice_channels, name=vc_name)
        category = discord.utils.get(guild.categories, name=category_name)

        if after.channel == lobby and before.channel != lobby:
            try:
                temp_channel = await guild.create_voice_channel(
                    name=f"{member.display_name}'s Channel",
                    category=category
                )
                if str(guild.id) not in self.temp_channels:
                    self.temp_channels[str(guild.id)] = []
                self.temp_channels[str(guild.id)].append(temp_channel.id)
                self.save_vc()
                logger.info(f'created vc: {temp_channel.name}')
                await member.move_to(temp_channel)
            except Exception as e:
                logger.error(f'channel creation error: {e}')

        if before.channel and before.channel.id in self.temp_channels.get(str(guild.id), []):
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                    logger.info(f'removed vc: {before.channel}')
                    self.temp_channels[str(guild.id)].remove(before.channel.id)
                    self.save_vc()
                except Exception as e:
                    logger.error(f'channel deletion error: {e}')

    def load_temp_vc(self):
        """
        Loads saved temporary voice channels from a configuration file.
        If the file does not exist or is invalid, an empty dictionary is returned.

        Returns:
            dict: A dictionary where the keys are guild IDs (as strings) and 
                values are lists of temporary voice channel IDs.
        """
        config_dir = '.config'

        # Ensure the config directory exists
        if not os.path.exists(config_dir):
            os.mkdir(config_dir)

        self.temp_vc_file = os.path.join(config_dir, 'temp_vc.json')

        # Check if the configuration file exists
        if os.path.exists(self.temp_vc_file):
            try:
                # Open and load the temp VC data from the JSON file
                with open(self.temp_vc_file, 'r') as vc_file:
                    data = json.load(vc_file)

                    # Validate that the data is in the expected format
                    if isinstance(data, dict):
                        # Ensure that each value in the dictionary is a list
                        for guild_id, vc_ids in data.items():
                            if not isinstance(vc_ids, list):
                                logger.error(f"""Invalid data format for guild {
                                             guild_id}. Expected a list of voice channel IDs.""")
                                return {}
                        return data
                    else:
                        logger.error(f"""Unexpected data format in {
                                     self.temp_vc_file}. Expected a dictionary.""")
                        return {}

            # Handle JSON decoding errors
            except json.JSONDecodeError:
                logger.error(f"Failed to load JSON from {self.temp_vc_file}")
                return {}

        # Return an empty dictionary if no file exists
        return {}

    def save_vc(self):
        """
        Saves the current state of temporary voice channels to a configuration file,
        where guild ID is the key and the values are lists of temporary voice channel IDs.
        """
        with open(self.temp_vc_file, 'w') as vc_file:
            json.dump(self.temp_channels, vc_file, indent=4)

        logger.info(f'Saved temporary voice channels to {self.temp_vc_file}')

    @commands.slash_command()
    @commands.guild_only()
    async def clean_temp_vc(self, ctx):
        """
        Cleans residual temporary voice channels for the current guild.
        """
        guild = ctx.guild

        logger.info(f"Cleaning temporary VCs for server: {guild.name}")
        await ctx.respond(f"Cleaning temporary VCs for server: {guild.name}")

        # Check if the guild has any saved temporary channels
        if str(guild.id) in self.temp_channels:
            # Get the list of temporary channel IDs for this guild
            temp_channel_ids = self.temp_channels[str(guild.id)]

            for vc_id in temp_channel_ids.copy():  # Iterate over a copy to safely modify the list
                voice_channel = guild.get_channel(vc_id)

                # If the voice channel exists and is empty, delete it
                if voice_channel and len(voice_channel.members) == 0:
                    try:
                        await voice_channel.delete()
                        logger.info(f"""Deleted empty temporary channel: {
                                    voice_channel.name}""")
                        # Remove from the list after deletion
                        temp_channel_ids.remove(vc_id)
                        await asyncio.sleep(1)  # Prevent hitting rate limits
                    except discord.HTTPException as e:
                        logger.error(f"""Error deleting channel {
                                     voice_channel.name}: {e}""")
                elif not voice_channel:
                    logger.warning(f"""Channel with ID {
                                   vc_id} not found in the guild.""")
                    # Remove non-existent channel from list
                    temp_channel_ids.remove(vc_id)

            # Update the saved state of temporary channels for this guild
            if not temp_channel_ids:  # If the list is now empty, remove the guild entry
                del self.temp_channels[str(guild.id)]
            else:
                self.temp_channels[str(guild.id)] = temp_channel_ids

            self.save_vc()  # Save updated state to file
            logger.info(f"Finished cleaning temporary VCs for {guild.name}.")

        else:
            logger.info(
                f"No temporary voice channels found for guild {guild.name}.")
            await ctx.respond(f"No temporary voice channels found for {guild.name}.")


def setup(bot):
    bot.add_cog(VoiceChannelManager(bot))
