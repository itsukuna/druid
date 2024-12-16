from discord.ext import commands
from discord.ui import View
from discord import Option
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

    voice = discord.SlashCommandGroup(name="voice", description="TempVoice related commands")

    @voice.command(name="clean", description="Clean temporary voice channels")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
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
    @commands.has_permissions(manage_channels=True)
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

    @voice.command(name="kick", description="Disconnects a member from current voice channel.")
    async def kick(self, ctx: discord.ApplicationContext, user:discord.Member):
        """
        Disconnect the selected member from current voice channel.

        Parameters:
            ctx: The application context of the command.
            name: Partial or full name of the member to search.
        """
        if not ctx.guild:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return
        
        channel= ctx.author.voice.channel
        if user.voice and user.voice.channel== channel:
            try:
                await user.move_to(None)
                await ctx.respond(f"✅ {user.display_name} has been disconnected from **{channel.name}**.")
            except discord.Forbidden:
                await ctx.respond("I lack the necessary permissions to disconnect this user.", ephemeral=True)
            except discord.HTTPException as e:
                await ctx.respond(f"Failed to disconnect the user: {e}", ephemeral=True)
        else:
            await ctx.respond(f"{user.display_name} is not in your current voice channel.", ephemeral=True)


    @voice.command(name="limit", description="Sets user limits to current voice channel")
    async def limit(self, ctx: discord.ApplicationContext, limit:int):
        """
        Sets a user limit for the current voice channel.

        Parameters:
            ctx: The application context of the command.
            limit: The maximum number of users allowed in the channel.
        """
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("You must be in a voice channel to use this command", ephemeral=True)
            return
        
        channel = ctx.author.voice.channel
        if limit < 0 and limit > 99:
            await ctx.respond("Please provide limit between 0(no limit) and 99.", ephemeral=True)
            return
        
        try:
            await channel.edit(user_limit=limit)
            await ctx.respond(f"The user limit for **{channel.name}** has been set to **{limit}**.", ephemeral=True)

        except discord.Forbidden:
            await ctx.respond("I don't have permission to edit this channel.", ephemeral=True)

        except discord.HTTPException as e:
            await ctx.respond(f"Failed to set the user limit: {e}", ephemeral=True)

    @voice.command(name="invite", description="Create a custom invite link for the current voice channel.")
    async def invite(
        self,
        ctx: discord.ApplicationContext,
        max_age: int = 3600,
        max_uses: int = 5
    ):
        """
        Parameters:
            max_age: The duration (in seconds) before the invite expires.
            max_uses: The maximum number of uses for the invite.
        """
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("You must be in a voice channel to use this command.", ephemeral=True)
            return

        # Validate max_age and max_uses
        if max_age <= 0 or max_age > 86400:  # Max age can't exceed 24 hours (86400 seconds)
            await ctx.respond("Invite expiration time must be between 1 second and 24 hours.", ephemeral=True)
            return

        if max_uses <= 0 or max_uses > 100:  # Discord doesn't support more than 100 uses
            await ctx.respond("Invite usage limit must be between 1 and 100.", ephemeral=True)
            return

        try:
            invite = await ctx.author.voice.channel.create_invite(
                max_age=max_age,
                max_uses=max_uses,
                unique=True
            )
            await ctx.respond(
                f"Here is your invite link for **{ctx.author.voice.channel.name}**:\n{invite.url}\n"
                f"Expires in {max_age/60} minutes | Max uses: {max_uses}"
            )
        except discord.Forbidden:
            await ctx.respond("I lack the necessary permissions to create invites for this channel.", ephemeral=True)
        except discord.HTTPException as e:
            await ctx.respond(f"Failed to create invite: {e}", ephemeral=True)


    @voice.command(name="privacy", description="Set the privacy of your current voice channel.")
    async def privacy(
        self,
        ctx: discord.ApplicationContext,
        mode: Option(
            str,
            "Choose the privacy mode: 'private' (only invitees can join) or 'public' (anyone can join).",
            choices=["private", "public"],
            required=True
        ) # type: ignore
    ):
        """
        Toggles privacy for the user's current voice channel.

        Parameters:
            ctx: The command's application context.
            mode: The desired privacy mode: 'private' or 'public'.
        """
        # Ensure the user is in a voice channel
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("You must be in a voice channel to use this command.", ephemeral=True)
            return

        channel = ctx.author.voice.channel

        try:
            if mode == "private":
                # Remove @everyone's connect permission
                await channel.set_permissions(ctx.guild.default_role, connect=False)
                await ctx.respond(
                    f"🔒 **{channel.name}** is now private. Only users with invites or specific roles can join."
                )
            elif mode == "public":
                # Allow @everyone to connect
                await channel.set_permissions(ctx.guild.default_role, connect=True)
                await ctx.respond(f"🌐 **{channel.name}** is now public. Anyone can join.")
        except discord.Forbidden:
            await ctx.respond(
                "I lack the necessary permissions to change the privacy settings of this channel.", ephemeral=True
            )
        except discord.HTTPException as e:
            await ctx.respond(f"Failed to update privacy settings: {e}", ephemeral=True)


    @voice.command(name="block", description="Blocks user from joining current voice channel")
    async def block(self, ctx:discord.ApplicationContext, 
                    user:discord.Member
                    ):
        """
        Blocks a specified user from joining the current voice channel.

        Parameters:
            ctx: The application context of the command.
            user: The member to block from the current voice channel.
        """
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("You must be in voice channel to use this command", ehpemeral=True)
            return
        
        channel = ctx.author.voice.channel
        
        current_overerites = channel.overwrites_for(user)
        if current_overerites.connect is False:
            await ctx.respond(f"{user.display_name} is already blocked from joining the channel **{channel.name}**.", ephemeral=True)
            return
        
        try:
            await channel.set_permissions(user, connect=False)
            await user.move_to(None)
            await ctx.respond(f"🚫 {user.display_name} has been blocked from joining the channel **{channel.name}**.", ephemeral = True)
        except discord.Forbidden:
            await ctx.respond("I lack the necessary permissions to block this user.", ephemeral=True)
        except discord.HTTPException as e:
            await ctx.respond(f"Failed to block the user: {e}", ephemeral=True)


    @voice.command(name="unblock", description="Unblocks a user from joining your current voice channel.")
    async def unblock(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Member,
    ):
        """
        Unblocks a specified user from joining the current voice channel.

        Parameters:
            ctx: The application context of the command.
            user: The member to unblock from the current voice channel.
        """
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("You must be in a voice channel to use this command.", ephemeral=True)
            return

        channel = ctx.author.voice.channel

        current_overwrites = channel.overwrites_for(user)
        if current_overwrites.connect is None or current_overwrites.connect is True:
            await ctx.respond(f"{user.display_name} is not currently blocked from **{channel.name}**.", ephemeral=True)
            return

        try:
            await channel.set_permissions(user, overwrite=None)
            await ctx.respond(f"✅ {user.display_name} has been unblocked from joining **{channel.name}**.")
        except discord.Forbidden:
            await ctx.respond("I lack the necessary permissions to unblock this user.", ephemeral=True)
        except discord.HTTPException as e:
            await ctx.respond(f"Failed to unblock the user: {e}", ephemeral=True)


def setup(bot):
    bot.add_cog(TempVoice(bot))
