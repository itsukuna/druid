from discord.ext import commands
from discord.ui import View, Button, Modal, InputText

import discord
import logging
import os
import json
import asyncio

logger = logging.getLogger('discord')

config_dir = '.config'
config_path = os.path.join(config_dir, "vc_setup_config.json")


class TempVoice(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.temp_channels = self.load_temp_vc()
        self.category_name, self.vc_name, self.active_channels, self.rules_channel = self.load_config_settings()

    def load_config_settings(self) -> tuple[str, str, str, str]:
        if os.path.exists(config_path):
            with open(config_path, "r") as config_file:
                config_data = json.load(config_file)
                lobby_category = config_data.get("lobby_category", "voice lobby")
                start_vc = next(
                    (ch["name"] for ch in config_data.get("channels", []) if ch["name"] == "start vc"), "start vc")
                active_channels_cat = config_data.get("active_category", "active channels")
                rules_channel = next(
                    (ch["name"] for ch in config_data.get("channels", []) if ch["name"] == "rules-and-commands"), 
                    "rules-and-commands"
                )
                return lobby_category, start_vc, active_channels_cat, rules_channel
        return "voice lobby", "start vc", "active channels", "rules-and-commands"
    
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
                await member.move_to(temp_channel)
            except Exception as e:
                logger.error(f'Error creating voice channel: {e}')

        if before.channel and before.channel.id in self.temp_channels.get(str(guild.id), []):
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                    self.temp_channels[str(guild.id)].remove(before.channel.id)
                    self.save_vc()
                except Exception as e:
                    logger.error(f'Error deleting voice channel: {e}')

    async def verify_channel_names(self, guild):
        if os.path.exists(config_path):
            with open(config_path, "r") as config_file:
                config_data = json.load(config_file)

            # Verify or create lobby category
            lobby_category = discord.utils.get(guild.categories, name=config_data["lobby_category"])
            if not lobby_category:
                lobby_category = await guild.create_category(config_data["lobby_category"])
                await asyncio.sleep(.5)

            # Verify channels in the lobby category
            for channel_info in config_data["channels"]:
                expected_name = channel_info["name"]
                channel_type = channel_info.get("type", "voice")
                channel = discord.utils.get(lobby_category.channels, name=expected_name)

                if not channel:
                    try:
                        if channel_type == "text":
                            await guild.create_text_channel(expected_name, category=lobby_category)
                        else:
                            await guild.create_voice_channel(expected_name, category=lobby_category)
                        await asyncio.sleep(.5)
                    except discord.Forbidden:
                        logger.error(f"Bot lacks permissions to create {expected_name} channel.")
                    except Exception as e:
                        logger.error(f"Error creating {expected_name} channel: {e}")

            # Verify or create active channels category
            active_category = discord.utils.get(guild.categories, name=config_data["active_category"])
            if not active_category:
                active_category = await guild.create_category(config_data["active_category"])
                await asyncio.sleep(.5)

            self.active_channels = active_category.name
            rules_channel = discord.utils.get(guild.text_channels, name=self.rules_channel)
            if not rules_channel:
                try:
                    rules_channel = await guild.create_text_channel(self.rules_channel)
                except Exception as e:
                    logger.error(f"Error creating rules channel: {e}")
                    return

    voice = discord.SlashCommandGroup(name="voice", description="commands related to TempVoice")

    @voice.command(name="clean", description="Clean temporary voice channels")
    @commands.guild_only()
    async def clean(self, ctx):
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
                        await asyncio.sleep(.5)
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

    @voice.command(name="setup", description= "Creates a default configuration for tempvoice")
    async def setup(self, ctx,):
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
            await ctx.respond("Configuration already exists.", ephemeral=True)

    @voice.command(name="reset", description="Resets the config file and removes channels")
    async def reset(self, ctx):
        await ctx.defer(ephemeral=True)
        if os.path.exists(config_path):
            with open(config_path, "r") as config_file:
                config_data = json.load(config_file)

            guild = ctx.guild
            lobby_category_name = config_data.get("lobby_category", "voice lobby")
            active_category_name = config_data.get("active_category", "active channels")
            channel_names = [ch["name"] for ch in config_data.get("channels", [])]

            # Remove channels in the lobby category
            lobby_category = discord.utils.get(guild.categories, name=lobby_category_name)
            if lobby_category:
                for channel in lobby_category.channels:
                    if channel.name in channel_names:
                        try:
                            await channel.delete()
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            logger.error(f"Failed to delete channel {channel.name}: {e}")

                try:
                    await lobby_category.delete()
                except Exception as e:
                    logger.error(f"Failed to delete category {lobby_category.name}: {e}")

            # Remove active category
            active_category = discord.utils.get(guild.categories, name=active_category_name)
            if active_category:
                for channel in active_category.channels:
                    try:
                        await channel.delete()
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.error(f"Failed to delete channel {channel.name}: {e}")

                try:
                    await active_category.delete()
                except Exception as e:
                    logger.error(f"Failed to delete category {active_category.name}: {e}")

            # Remove configuration file
            try:
                os.remove(config_path)
                logger.info("Configuration file removed successfully.")
            except Exception as e:
                logger.error(f"Failed to delete configuration file: {e}")
                await ctx.respond("Failed to remove the configuration file. Check the logs for more details.", ephemeral=True)
                return

            await ctx.respond("Configuration and associated channels have been reset successfully.", ephemeral=True)
        else:
            await ctx.respond("No configuration file found to reset.", ephemeral=True)

    @voice.command(name="rename", description="Rename your temporary voice channel")
    @commands.guild_only()
    async def rename(self, ctx: discord.ApplicationContext, new_name: str):
        if len(new_name) > 100:
            await ctx.respond("Channel name must be 100 characters or fewer.", ephemeral=True)
            return

        member = ctx.author
        guild = ctx.guild
        user_channels = [
            guild.get_channel(vc_id) for vc_id in self.temp_channels.get(str(guild.id), [])
            if guild.get_channel(vc_id) and guild.get_channel(vc_id).members and member in guild.get_channel(vc_id).members
        ]

        if not user_channels:
            await ctx.respond("You don't own a temporary voice channel.", ephemeral=True)
            return

        temp_channel = user_channels[0]
        try:
            await temp_channel.edit(name=new_name)
            await ctx.respond(f"Channel renamed to '{new_name}'.", ephemeral=True)
            logger.info(f"{member} renamed their temporary channel to {new_name}")
        except discord.HTTPException as e:
            logger.error(f"Failed to rename channel: {e}")
            await ctx.respond("Failed to rename the channel. Please try again later.", ephemeral=True)


def setup(bot):
    bot.add_cog(TempVoice(bot))
