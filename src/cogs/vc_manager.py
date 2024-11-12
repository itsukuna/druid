from discord.ext import commands
import discord
import logging
import os
import json
import asyncio

logger = logging.getLogger('discord')

config_dir = '.config'
config_path = os.path.join(config_dir, "vc_setup_config.json")

class VoiceChannelManager(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.temp_channels = self.load_temp_vc()
        self.category_name, self.vc_name, self.active_channels = self.load_config_settings()

    def load_config_settings(self) -> tuple[str, str, str]:
        if os.path.exists(config_path):
            with open(config_path, "r") as config_file:
                config_data = json.load(config_file)
                lobby_category = config_data.get("lobby_category", "voice lobby")
                start_vc = next((ch["name"] for ch in config_data.get("channels", []) if ch["name"] == "start vc"), "start vc")
                active_channels_cat = config_data.get("active_category", "active channels")
                return lobby_category, start_vc, active_channels_cat
        return "voice lobby", "start vc", "active channels" 

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f'{self.__class__.__name__} is ready.')
        for guild in self.bot.guilds:
            await self.verify_channel_names(guild)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        lobby = discord.utils.get(guild.voice_channels, name=self.vc_name)
        active_category = discord.utils.get(guild.categories, name=self.active_channels)

        if after.channel == lobby and before.channel != lobby:
            try:
                temp_channel = await guild.create_voice_channel(
                    name=f"{member.display_name}'s Channel",
                    category=active_category
                )
                self.temp_channels.setdefault(str(guild.id), []).append(temp_channel.id)
                self.save_vc()
                logger.info(f'Created temporary VC: {temp_channel.name}')
                await member.move_to(temp_channel)
            except Exception as e:
                logger.error(f'Error creating voice channel: {e}')

        if before.channel and before.channel.id in self.temp_channels.get(str(guild.id), []):
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                    logger.info(f'Removed temporary VC: {before.channel}')
                    self.temp_channels[str(guild.id)].remove(before.channel.id)
                    self.save_vc()
                except Exception as e:
                    logger.error(f'Error deleting voice channel: {e}')

    def load_temp_vc(self) -> dict:
        os.makedirs(config_dir, exist_ok=True)
        self.temp_vc_file = os.path.join(config_dir, 'temp_vc.json')

        if os.path.exists(self.temp_vc_file):
            try:
                with open(self.temp_vc_file, 'r') as vc_file:
                    data = json.load(vc_file)
                    return {k: v for k, v in data.items() if isinstance(v, list)}
            except json.JSONDecodeError:
                logger.error(f"Failed to load JSON from {self.temp_vc_file}")
        return {}

    def save_vc(self):
        with open(self.temp_vc_file, 'w') as vc_file:
            json.dump(self.temp_channels, vc_file, indent=4)
        logger.info(f'Saved temporary voice channels to {self.temp_vc_file}')

    @commands.slash_command()
    @commands.guild_only()
    async def clean_temp_vc(self, ctx):
        await ctx.defer()
        guild = ctx.guild
        logger.info(f"Cleaning temporary voice channels for server: {guild.name}")

        if str(guild.id) in self.temp_channels:
            temp_channel_ids = self.temp_channels[str(guild.id)]

            for vc_id in temp_channel_ids[:]:
                voice_channel = guild.get_channel(vc_id)

                if voice_channel and len(voice_channel.members) == 0:
                    try:
                        await voice_channel.delete()
                        temp_channel_ids.remove(vc_id)
                        await asyncio.sleep(1)
                    except discord.HTTPException as e:
                        logger.error(f"Error deleting channel {voice_channel.name}: {e}")
                elif not voice_channel:
                    temp_channel_ids.remove(vc_id)

            if not temp_channel_ids:
                del self.temp_channels[str(guild.id)]
            self.save_vc()
            await ctx.respond("Temporary VCs cleaned.", ephemeral=True)
        else:
            await ctx.respond("No temporary VCs to clean.", ephemeral=True)

    @commands.slash_command()
    async def setup_vc(self, ctx):
        if not os.path.exists(config_path):
            config_data = {
                "lobby_category": "voice lobby",
                "channels": [
                    {
                        "name": "rules-and-commands",
                        "type": "text"
                    },
                    {
                        "name": "start vc",
                        "type": "voice"
                    }
                ],
                "active_category": "active channels"
            }


            with open(config_path, "w") as config_file:
                json.dump(config_data, config_file, indent=4)
            
            await ctx.respond("Default voice channel configuration has been created. Setting up channels...", ephemeral=True)
            await self.verify_channel_names(ctx.guild)
        else:
            await ctx.respond("Configuration already exists. Use `/clean_temp_vc` if you need to reset.", ephemeral=True)
            
    async def verify_channel_names(self, guild):
        if os.path.exists(config_path):
            with open(config_path, "r") as config_file:
                config_data = json.load(config_file)

            # Verify or create lobby category
            lobby_category = discord.utils.get(guild.categories, name=config_data["lobby_category"])
            if not lobby_category:
                lobby_category = await guild.create_category(config_data["lobby_category"])
                await asyncio.sleep(1)

            # Verify channels in the lobby category
            for channel_info in config_data["channels"]:
                expected_name = channel_info["name"]
                channel_type = channel_info.get("type", "voice")
                channel = discord.utils.get(lobby_category.channels, name=expected_name)
                
                if not channel:
                    if channel_type == "text":
                        await guild.create_text_channel(expected_name, category=lobby_category)
                    else:
                        await guild.create_voice_channel(expected_name, category=lobby_category)
                    await asyncio.sleep(.5)  
                elif channel.name != expected_name:
                    # Rename channel if it doesn’t match the expected name
                    await channel.edit(name=expected_name)
                    await asyncio.sleep(.5)

            # Verify or create active channels category
            active_category = discord.utils.get(guild.categories, name=config_data["active_category"])
            if not active_category:
                active_category = await guild.create_category(config_data["active_category"])
                await asyncio.sleep(.5)

            self.active_channels = active_category.name  # Update to track the active category

def setup(bot):
    bot.add_cog(VoiceChannelManager(bot))
