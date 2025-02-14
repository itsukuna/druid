from database import VoiceDB
from discord.ext import commands
from discord.ui import View, Button, Modal, InputText

import logging
import discord
import asyncio
import error

logger = logging.getLogger("discord")


class TempVoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = VoiceDB()

    def in_voice_channel(self, ctx):
        user=self.get_user(ctx)
        if not user.voice or not user.voice.channel:
            raise error.invalidVoiceChannel("You are not in a voice channel.")
    
    def is_owner(self, ctx, action):
        """Helper function to check ownership of voice channel"""
        temp_channels = self.db.get_temp_channels(ctx.guild.id)
        user = self.get_user(ctx)
        if user.voice.channel.id not in[
            ch["channel_id"] for ch in temp_channels
        ]:
            raise error.Ownership(f"You are not in a temporary voice channel.")
        if user.id not in [
            ch["owner_id"]
            for ch in temp_channels
            if ch["channel_id"] == user.voice.channel.id
        ]:
            raise error.Ownership(f"Only the channel owner can {action}.")
        
    def get_user(self, ctx_or_interaction):
        """Helper function to extract the user from either a command context or an interaction."""
        if isinstance(ctx_or_interaction, discord.ApplicationContext):
            return ctx_or_interaction.author
        elif isinstance(ctx_or_interaction, discord.Interaction):
            return ctx_or_interaction.user
        else:
            raise ValueError("Invalid context or interaction")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"{self.__class__.__name__} is ready.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild_id = member.guild.id
        lobby_vc = discord.utils.get(
            member.guild.channels,
            id=self.db.get_server_config(guild_id)["voice_lobby"]["id"],
        )
        active_category = discord.utils.get(
            member.guild.categories,
            id=self.db.get_server_config(guild_id)["active_category"]["id"],
        )
        if after.channel == lobby_vc and before.channel != lobby_vc:
            try:
                temp_vc = await member.guild.create_voice_channel(
                    f"{member.display_name}'s channel", category=active_category
                )
                await member.move_to(temp_vc)
                logger.info(
                    f"Created temporary channel {temp_vc.name} for member {member.display_name}"
                )
                self.db.add_temp_channel(guild_id, temp_vc.id, member.id)
            except Exception as e:
                logger.error(
                    f"Error creating temporary channel for member {member.display_name}: {e}"
                )
            return

        if before.channel and before.channel.id in [
            ch["channel_id"] for ch in self.db.get_temp_channels(guild_id)
        ]:
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                    self.db.remove_temp_channel(guild_id, before.channel.id)
                    logger.info(
                        f"Deleted empty temporary channel {before.channel.name}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error deleting temporary channel {before.channel.name}: {e}"
                    )
            else:
                temp_channels = self.db.get_temp_channels(guild_id)
                for ch in temp_channels:
                    if (
                        ch["channel_id"] == before.channel.id
                        and ch["owner_id"] == member.id
                    ):
                        new_owner = before.channel.members[0]
                        self.db.update_temp_channel_owner(
                            guild_id, before.channel.id, new_owner.id
                        )
                        logger.info(
                            f"Transferred ownership of temporary channel {before.channel.name} to {new_owner.display_name}"
                        )
                        break

    voice = discord.SlashCommandGroup(
        name="voice", description="Commands for managing temporary voice channels."
    )

    @voice.command(name="setup", description="Creates a default configuration.")
    @commands.has_permissions(manage_channels=True)
    async def setup(self, ctx):
        guild = ctx.guild
        guild_id = ctx.guild.id
        if not self.db.get_server_config(guild_id):
            lobby_category = await guild.create_category("voice lobby")
            voice_lobby = await guild.create_voice_channel(
                "start vc", category=lobby_category
            )
            active_category = await guild.create_category("active channels")
            rules_channel = await guild.create_text_channel(
                "rules-and-commands", category=lobby_category
            )

            server_config = {
                "guild_id": guild_id,
                "lobby_category": {
                    "id": lobby_category.id,
                    "name": lobby_category.name,
                },
                "voice_lobby": {"id": voice_lobby.id, "name": voice_lobby.name},
                "active_category": {
                    "id": active_category.id,
                    "name": active_category.name,
                },
                "rules_channel": {"id": rules_channel.id, "name": rules_channel.name},
            }
            self.db.set_server_config(guild_id, server_config)

            embed = discord.Embed(
                title="📢 Voice Channel Rules and Commands",
                description=(
                    "Welcome to the **Voice Channel Rules and Commands** guide! "
                    "Below are the rules to follow and the commands you can use to manage your temporary voice channels."
                ),
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="📜 Rules",
                value=(
                    "1. **Be respectful** to others.\n"
                    "2. **No spamming or excessive noise**.\n"
                    "3. Follow the server's **general rules**.\n"
                    "\nViolating these rules may result in removal from the voice channel."
                ),
                inline=False,
            )
            embed.add_field(
                name="🛠️ Commands",
                value=(
                    "`/voice rename <new_name>` - Rename your temporary voice channel.\n"
                    "`/voice limit <number>` - Set a user limit for your temporary voice channel.\n"
                    "`/voice privacy <public/private>` - Make your voice channel public or private.\n"
                    "`/voice kick <user>` - Kick a user from your temporary voice channel.\n"
                    "`/voice ban <user>` - Ban a user from your temporary voice channel.\n"
                    "`/voice unban <user>` - Unban a user from your temporary voice channel.\n"
                    "`/voice invite` - Generate an invite link for your temporary voice channel."
                ),
                inline=False,
            )
            view = View()
            button_labels = {
                "Rename": "rename",
                "Limit": "limit",
                "Privacy": "privacy",
                "Kick": "kick",
                "Ban": "ban",
                "Unban": "unban",
                "Invite": "invite"
            }
            for label, custom_id in button_labels.items():
                view.add_item(Button(label=label, style=discord.ButtonStyle.secondary, custom_id=custom_id))

            await rules_channel.send(embed=embed, view=view)

            await ctx.respond("Server configuration has been created.", ephemeral=True)
            logger.info(f"Server configuration created for guild {guild_id}")
        else:
            await ctx.respond(
                "Server configuration already exists. Use `/voice reset` to remove config from database",
                ephemeral=True,
            )
            logger.info(f"Server configuration already exists for guild {guild_id}")

    @setup.error
    async def setup_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.respond(
                "You do not have permission to use this command.", ephemeral=True
            )
        logger.error(f"Error setting up server configuration.{error}")

    @voice.command(name="reset", description="Reset the configuration for your server.")
    @commands.has_permissions(manage_channels=True)
    async def reset(self, ctx):
        guild_id = ctx.guild.id
        config = self.db.get_server_config(guild_id)
        logger.info(f"Resetting server configuration for guild {guild_id}")
        if not config:
            await ctx.respond(
                "Server configuration does not exist. Use `/voice setup` to create a configuration.",
                ephemeral=True,
            )
            logger.info(f"Server configuration does not exist for guild {guild_id}")
        else:
            try:
                lobby_category = ctx.guild.get_channel(config["lobby_category"]["id"])
                active_category = ctx.guild.get_channel(config["active_category"]["id"])
                rules_channel = ctx.guild.get_channel(config["rules_channel"]["id"])
                voice_lobby = ctx.guild.get_channel(config["voice_lobby"]["id"])

                if voice_lobby:
                    await voice_lobby.delete()
                    logger.info(f"Deleted voice lobby for guild {guild_id}")
                if rules_channel:
                    await rules_channel.delete()
                    logger.info(f"Deleted rules channel for guild {guild_id}")
                if lobby_category:
                    await lobby_category.delete()
                    logger.info(f"Deleted lobby category for guild {guild_id}")
                if active_category:
                    await active_category.delete()
                    logger.info(f"Deleted active category for guild {guild_id}")
                
                await asyncio.sleep(0.5)
                await ctx.respond(
                    "Server configuration has been removed.", ephemeral=True
                )
                self.db.remove_server_config(guild_id)
                logger.info(f"Server configuration removed for guild {guild_id}")
            except discord.NotFound:
                logger.error(f"Channel not found while resetting server configuration for guild {guild_id}")
                await ctx.respond(
                    "Error resetting server configuration: Channel not found.", ephemeral=True
                )
            except Exception as e:
                logger.error(
                    f"Error resetting server configuration for guild {guild_id}: {e}"
                )
                await ctx.respond(
                    "Error resetting server configuration.", ephemeral=True
                )

    @reset.error
    async def reset_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.respond(
                "You do not have permission to use this command.", ephemeral=True
            )
        logger.error(f"Error resetting server configuration.{error}")

    @voice.command(
        name="cleanup", description="Cleanup temporary voice channels for your server."
    )
    @commands.has_permissions(manage_channels=True)
    async def cleanup(self, ctx):
        guild_id = ctx.guild.id
        temp_channels = self.db.get_temp_channels(guild_id)
        if not temp_channels:
            await ctx.respond("No temporary channels to cleanup.", ephemeral=True)
            logger.info(f"No temporary channels to cleanup for guild {guild_id}")
            return
        for ch in temp_channels:
            channel = discord.utils.get(ctx.guild.voice_channels, id=ch["channel_id"])
            if channel and len(channel.members) == 0:
                try:
                    await channel.delete()
                    self.db.remove_temp_channel(guild_id, ch["channel_id"])
                    logger.info(
                        f"Deleted empty temporary channel {channel.name} for guild {guild_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error deleting temporary channel {channel.name} for guild {guild_id}: {e}"
                    )
            await asyncio.sleep(0.5)
        await ctx.respond("Cleanup completed.", ephemeral=True)
        logger.info(f"Cleanup completed for guild {guild_id}")

    @voice.command(name="rename", description="Rename a temporary voice channel.")
    async def rename(self, ctx: discord.ApplicationContext, new_name: str):
        await self.rename_channel(ctx, new_name)

    @voice.command(
        name="limit", description="Set a user limit for a temporary voice channel."
    )
    async def limit(self, ctx, limit: int):
        await self.set_limit(ctx, limit)

    @voice.command(
        name="privacy", description="Make a temporary voice channel private or public."
    )
    async def privacy(self, ctx):
        await self.set_privacy(ctx)

    @voice.command(
        name="kick", description="Kick a user from a temporary voice channel."
    )
    async def kick(self, ctx):
        await self.get_voice_members(ctx, "kick")

    @voice.command(name="ban", description="Ban a user from a temporary voice channel.")
    async def ban(self, ctx):
        await self.get_voice_members(ctx, "ban")

    @voice.command(
        name="unban", description="Unban a user from a temporary voice channel."
    )
    async def unban(self, ctx):
        await self.get_banned_user(ctx, "unban")

    @voice.command(
        name="invite", description="Invite a user to a temporary voice channel."
    )
    async def invite(self, ctx):
        await self.new_invite(ctx)

    #Helper functions
    async def rename_channel(self, ctx_or_interaction, new_name: str):
        user = self.get_user(ctx_or_interaction)
        try:
            self.in_voice_channel(ctx_or_interaction)
            self.is_owner(ctx_or_interaction, "rename the channel")
        except (error.invalidVoiceChannel, error.Ownership) as e:
            await ctx_or_interaction.response.send_message(str(e), ephemeral=True)
            return

        if len(new_name) > 100:
            await ctx_or_interaction.response.send_message(
                "Channel name is too long, must be under 100 characters.", ephemeral=True
            )
            return

        try:
            await user.voice.channel.edit(name=new_name)
            await ctx_or_interaction.response.send_message(
                f"Channel name has been changed to {new_name}.", ephemeral=True
            )
            logger.info(
                f"Renamed temporary channel to {new_name} for guild {ctx_or_interaction.guild.id}"
            )
        except Exception as e:
            logger.error(
                f"Error renaming temporary channel for guild {ctx_or_interaction.guild.id}: {e}"
            )
            await ctx_or_interaction.response.send_message("Error renaming channel.", ephemeral=True)

    async def set_limit(self, ctx_or_interaction, limit: int):
        user = self.get_user(ctx_or_interaction)
        try:
            self.in_voice_channel(ctx_or_interaction)
            self.is_owner(ctx_or_interaction, "set a user limit")
        except (error.invalidVoiceChannel, error.Ownership) as e:
            await ctx_or_interaction.respond(str(e), ephemeral=True)
            return
        if limit < 0 or limit > 99:
            await ctx_or_interaction.respond("Limit must be between 0 and 99.", ephemeral=True)
            return
        try:
            await user.voice.channel.edit(user_limit=limit)
            await ctx_or_interaction.respond(f"User limit has been set to {limit}.", ephemeral=True)
            logger.info(
                f"Set user limit to {limit} for temporary channel in guild {ctx_or_interaction.guild.id}"
            )
        except Exception as e:
            logger.error(
                f"Error setting user limit for temporary channel in guild {ctx_or_interaction.guild.id}: {e}"
            )
            await ctx_or_interaction.respond("Error setting user limit.", ephemeral=True)

    async def set_privacy(self, ctx_or_interaction):
        """Toggles the privacy of a temporary voice channel between public and private."""
        user = self.get_user(ctx_or_interaction)
        try:
            self.in_voice_channel(ctx_or_interaction)
            self.is_owner(ctx_or_interaction, "change the channel privacy")
        except (error.invalidVoiceChannel, error.Ownership) as e:
            await ctx_or_interaction.respond(str(e), ephemeral=True)
            return
        
        channel = user.voice.channel
        try:
            if channel.overwrites_for(ctx_or_interaction.guild.default_role).connect is False:
                await channel.set_permissions(ctx_or_interaction.guild.default_role, connect=True)
                await ctx_or_interaction.respond("Channel is now public.", ephemeral=True)
                logger.info(
                    f"Set temporary channel to public for guild {ctx_or_interaction.guild.id}"
                )
            else:
                await channel.set_permissions(ctx_or_interaction.guild.default_role, connect=False)
                await ctx_or_interaction.respond("Channel is now private.", ephemeral=True)
                logger.info(
                    f"Set temporary channel to private for guild {ctx_or_interaction.guild.id}"
                )
        except Exception as e:
            logger.error(f"Error changing channel privacy in guild {ctx_or_interaction.guild.id}: {e}")
            await ctx_or_interaction.respond("⚠️ Error changing channel privacy.", ephemeral=True)

    async def new_invite(self, ctx_or_interaction, max_age: int = 3600, max_usage: int = 5):
        user = self.get_user(ctx_or_interaction)
        try:
            self.in_voice_channel(ctx_or_interaction)
            self.is_owner(ctx_or_interaction, "create an invite")
        except (error.invalidVoiceChannel, error.Ownership) as e:
            await ctx_or_interaction.respond(str(e), ephemeral=True)
            return
        try:
            invite = await user.voice.channel.create_invite(
                max_age=max_age, max_uses=max_usage
            )
            await ctx_or_interaction.respond(
                f"Here is your invite link for **{user.voice.channel.name}**:\n{invite.url}\n"
                f"Expires in {max_age/60} minutes | Max uses: {max_usage}",
                ephemeral=True,
            )
            logger.info(f"Created invite for temporary channel in guild {ctx_or_interaction.guild.id}")
        except discord.Forbidden:
            await ctx_or_interaction.respond(
                "I lack the necessary permissions to create invites for this channel.",
                ephemeral=True,
            )
            logger.error(
                f"Permission error creating invite for temporary channel in guild {ctx_or_interaction.guild.id}"
            )
        except discord.HTTPException as e:
            await ctx_or_interaction.respond(f"Failed to create invite: {e}", ephemeral=True)
            logger.error(
                f"HTTP error creating invite for temporary channel in guild {ctx_or_interaction.guild.id}: {e}"
            )

    async def get_voice_members(self, ctx_or_interaction, action):
        user = self.get_user(ctx_or_interaction)
        try:
            self.in_voice_channel(ctx_or_interaction)
            self.is_owner(ctx_or_interaction, "kick a user")
        except (error.invalidVoiceChannel, error.Ownership) as e:
            await ctx_or_interaction.respond(str(e), ephemeral=True)
            return
        
        if user.voice and user.voice.channel:
            members = user.voice.channel.members
            await ctx_or_interaction.respond(view=UserSelectionView(members, action, self), ephemeral=True)

    async def get_banned_user(self, ctx_or_interaction, action):
        """Fetches banned users and allows selection for unbanning."""
        user = self.get_user(ctx_or_interaction)

        try:
            self.in_voice_channel(ctx_or_interaction)
            self.is_owner(ctx_or_interaction, "unban a user")
        except (error.invalidVoiceChannel, error.Ownership) as e:
            await ctx_or_interaction.respond(str(e), ephemeral=True)
            return

        channel = user.voice.channel
        banned_user_ids = self.db.get_banned_users(ctx_or_interaction.guild.id, channel.id)

        if not banned_user_ids:
            await ctx_or_interaction.respond("No users are banned from this channel.", ephemeral=True)
            return

        # Convert user IDs to `discord.Member` objects (skip users who left the server)
        banned_members = [ctx_or_interaction.guild.get_member(user_id) for user_id in banned_user_ids if ctx_or_interaction.guild.get_member(user_id)]

        if not banned_members:
            await ctx_or_interaction.respond("No banned users are currently in the server.", ephemeral=True)
            return

        await ctx_or_interaction.respond(view=UserSelectionView(banned_members, action, self), ephemeral=True)


    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            match interaction.data.get("custom_id"):
                case "rename":
                    await interaction.response.send_modal(Controls("Rename Channel", "New Name", self))
                case "limit":
                    await interaction.response.send_modal(Controls("Set Limit", "User Limit", self))
                case "privacy":
                    await self.set_privacy(interaction)
                case "kick":
                    await self.get_voice_members(interaction, "kick")
                case "ban":
                    await self.get_voice_members(interaction, "ban")
                case "unban":
                    await self.get_banned_user(interaction, "unban")
                case "invite":
                    await self.new_invite(interaction)

class Controls(Modal):
    def __init__(self, title, label, cog):
        super().__init__(title=title, timeout=300)
        self.add_item(InputText(label=label))
        self.cog = cog
    
    async def callback(self, interaction):
        new_value = self.children[0].value
        match self.title:
            case "Rename Channel":
                await self.cog.rename_channel(interaction, new_value)
            case "Set Limit":
                await self.cog.set_limit(interaction, int(new_value))

class UserSelectionView(View):
    def __init__(self, members, action, cog):
        super().__init__(timeout=60)
        self.add_item(UserSelect(members, action, cog))

class UserSelect(discord.ui.Select):
    def __init__(self, members, action, cog):
        options =[
            discord.SelectOption(label=member.name, value=str(member.id))
            for member in members
        ]
        self.action = action
        self.cog = cog
        super().__init__(placeholder="Select a user...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        """Handles selection."""
        selected_user_id = int(self.values[0])
        logger.info(selected_user_id)
        selected_user = interaction.guild.get_member(selected_user_id)
        channel = interaction.user.voice.channel

        if selected_user and selected_user.voice:
            match self.action:
                case "kick":
                    await selected_user.move_to(None)
                    await interaction.response.send_message(f"{selected_user.mention} has been kicked.", ephemeral=True)

                case "ban":
                    current_overwrites = channel.overwrites_for(selected_user)
                    if current_overwrites.connect is False:
                        await interaction.respond(
                            f"{selected_user.display_name} is already banned.", ephemeral=True
                        )
                        return
                    try:
                        await selected_user.move_to(None)
                        await channel.set_permissions(selected_user, connect=False, view_channel=False)
                        self.cog.db.add_banned_user(interaction.guild.id, channel.id, selected_user.id)
                        await interaction.response.send_message(
                            f"{selected_user.display_name} has been banned.", ephemeral=True
                        )
                        logger.info(
                            f"Banned {selected_user.display_name} from temporary channel in guild {interaction.guild.id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error banning {selected_user.display_name} from temporary channel in guild {interaction.guild.id}: {e}"
                        )
                        await interaction.respond("Error banning user.", ephemeral=True)

                case "unban":
                    try:
                        await channel.set_permissions(selected_user, connect=True, view_channel=True)
                        await interaction.response.send_message(
                            f"{selected_user.display_name} has been unbanned.", ephemeral=True
                        )
                        self.cog.db.remove_banned_user(interaction.guild.id, channel.id, selected_user_id)
                        logger.info(
                            f"Unbanned {selected_user.display_name} from temporary channel in guild {interaction.guild.id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error unbanning {selected_user.display_name} from temporary channel in guild {interaction.guild.id}: {e}"
                        )
                        await interaction.response.send_message("Error unbanning user.", ephemeral=True)


def setup(bot):
    bot.add_cog(TempVoice(bot))
