from database import VoiceDB
from discord.ext import commands
from discord import Option

import logging
import discord
import asyncio

logger = logging.getLogger("discord")


class TempVoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = VoiceDB()

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
            await rules_channel.send(embed=embed)

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
        logger.error("Error setting up server configuration.{error}")

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
        logger.error("Error resetting server configuration.{error}")

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
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("You are not in a voice channel.", ephemeral=True)
            return
        temp_channels = self.db.get_temp_channels(ctx.guild.id)
        if ctx.author.voice.channel.id not in [
            ch["channel_id"] for ch in temp_channels
        ]:
            await ctx.respond(
                "You can only rename your own temporary voice channel.", ephemeral=True
            )
            return
        if ctx.author.id not in [
            ch["owner_id"]
            for ch in temp_channels
            if ch["channel_id"] == ctx.author.voice.channel.id
        ]:
            await ctx.respond(
                "Only the channel owner can rename the channel.", ephemeral=True
            )
            return
        if len(new_name) > 100:
            await ctx.respond(
                "Channel name is too long must be under 100 characters.", ephemeral=True
            )
            return
        try:
            await ctx.author.voice.channel.edit(name=new_name)
            await ctx.respond(
                f"Channel name has been changed to {new_name}.", ephemeral=True
            )
            logger.info(
                f"Renamed temporary channel to {new_name} for guild {ctx.guild.id}"
            )
        except Exception as e:
            logger.error(
                f"Error renaming temporary channel for guild {ctx.guild.id}: {e}"
            )
            await ctx.respond("Error renaming channel.", ephemeral=True)

    @voice.command(
        name="limit", description="Set a user limit for a temporary voice channel."
    )
    async def limit(self, ctx, limit: int):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("You are not in a voice channel.", ephemeral=True)
            return
        temp_channels = self.db.get_temp_channels(ctx.guild.id)
        if ctx.author.voice.channel.id not in [
            ch["channel_id"] for ch in temp_channels
        ]:
            await ctx.respond("Only owners can set channel limit.", ephemeral=True)
            return
        if limit < 0 or limit > 99:
            await ctx.respond("Limit must be between 0 and 99.", ephemeral=True)
            return
        try:
            await ctx.author.voice.channel.edit(user_limit=limit)
            await ctx.respond(f"User limit has been set to {limit}.", ephemeral=True)
            logger.info(
                f"Set user limit to {limit} for temporary channel in guild {ctx.guild.id}"
            )
        except Exception as e:
            logger.error(
                f"Error setting user limit for temporary channel in guild {ctx.guild.id}: {e}"
            )
            await ctx.respond("Error setting user limit.", ephemeral=True)

    @voice.command(
        name="privacy", description="Make a temporary voice channel private or public."
    )
    async def privacy(self, ctx, mode: Option(str, choices=["public", "private"])):  # type: ignore
        channel = ctx.author.voice.channel
        if not ctx.author.voice or not channel:
            await ctx.respond("You are not in a voice channel.", ephemeral=True)
            return
        temp_channels = self.db.get_temp_channels(ctx.guild.id)
        if ctx.author.voice.channel.id not in [
            ch["channel_id"] for ch in temp_channels
        ]:
            await ctx.respond("Only owners can change channel privacy.", ephemeral=True)
            return
        try:
            if mode == "public":
                await channel.set_permissions(ctx.guild.default_role, connect=True)
                await ctx.respond("Channel is now public.", ephemeral=True)
                logger.info(f"Set temporary channel to public in guild {ctx.guild.id}")
            elif mode == "private":
                await channel.set_permissions(ctx.guild.default_role, connect=False)
                await ctx.respond("Channel is now private.", ephemeral=True)
                logger.info(f"Set temporary channel to private in guild {ctx.guild.id}")
        except Exception as e:
            logger.error(
                f"Error changing channel privacy for temporary channel in guild {ctx.guild.id}: {e}"
            )
            await ctx.respond("Error changing channel privacy.", ephemeral=True)

    @voice.command(
        name="kick", description="Kick a user from a temporary voice channel."
    )
    async def kick(self, ctx, member: discord.Member):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("You are not in a voice channel.", ephemeral=True)
            return
        temp_channels = self.db.get_temp_channels(ctx.guild.id)
        if ctx.author.voice.channel.id not in [
            ch["channel_id"] for ch in temp_channels
        ]:
            await ctx.respond("Only owners can kick users.", ephemeral=True)
            return
        if member.voice and member.voice.channel == ctx.author.voice.channel:
            try:
                await member.move_to(None)
                await ctx.respond(
                    f"{member.display_name} has been kicked.", ephemeral=True
                )
                logger.info(
                    f"Kicked {member.display_name} from temporary channel in guild {ctx.guild.id}"
                )
            except Exception as e:
                logger.error(
                    f"Error kicking {member.display_name} from temporary channel in guild {ctx.guild.id}: {e}"
                )
                await ctx.respond("Error kicking user.", ephemeral=True)

    @voice.command(name="ban", description="Ban a user from a temporary voice channel.")
    async def ban(self, ctx, member: discord.Member):
        channel = ctx.author.voice.channel
        current_overwrites = channel.overwrites_for(member)
        if not ctx.author.voice or not channel:
            await ctx.respond("You are not in a voice channel.", ephemeral=True)
            return
        temp_channels = self.db.get_temp_channels(ctx.guild.id)
        if ctx.author.voice.channel.id not in [
            ch["channel_id"] for ch in temp_channels
        ]:
            await ctx.respond("Only owners can ban users.", ephemeral=True)
            return
        if current_overwrites.connect is False:
            await ctx.respond(
                f"{member.display_name} is already banned.", ephemeral=True
            )
            return
        if member.voice and member.voice.channel == ctx.author.voice.channel:
            try:
                await member.move_to(None)
                await channel.set_permissions(member, connect=False)
                await ctx.respond(
                    f"{member.display_name} has been banned.", ephemeral=True
                )
                logger.info(
                    f"Banned {member.display_name} from temporary channel in guild {ctx.guild.id}"
                )
            except Exception as e:
                logger.error(
                    f"Error banning {member.display_name} from temporary channel in guild {ctx.guild.id}: {e}"
                )
                await ctx.respond("Error banning user.", ephemeral=True)

    @voice.command(
        name="unban", description="Unban a user from a temporary voice channel."
    )
    async def unban(self, ctx, member: discord.Member):
        channel = ctx.author.voice.channel
        current_overwrites = channel.overwrites_for(member)
        if not ctx.author.voice or not channel:
            await ctx.respond("You are not in a voice channel.", ephemeral=True)
            return
        temp_channels = self.db.get_temp_channels(ctx.guild.id)
        if ctx.author.voice.channel.id not in [
            ch["channel_id"] for ch in temp_channels
        ]:
            await ctx.respond("Only owners can unban users.", ephemeral=True)
            return
        if current_overwrites.connect is True:
            await ctx.respond(f"{member.display_name} is not banned.", ephemeral=True)
            return
        else:
            try:
                await channel.set_permissions(member, connect=True)
                await ctx.respond(
                    f"{member.display_name} has been unbanned.", ephemeral=True
                )
                logger.info(
                    f"Unbanned {member.display_name} from temporary channel in guild {ctx.guild.id}"
                )
            except Exception as e:
                logger.error(
                    f"Error unbanning {member.display_name} from temporary channel in guild {ctx.guild.id}: {e}"
                )
                await ctx.respond("Error unbanning user.", ephemeral=True)

    @voice.command(
        name="invite", description="Invite a user to a temporary voice channel."
    )
    async def invite(self, ctx, max_age: int = 3600, max_usage: int = 5):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("You are not in a voice channel.", ephemeral=True)
            return
        temp_channels = self.db.get_temp_channels(ctx.guild.id)
        if ctx.author.voice.channel.id not in [
            ch["channel_id"] for ch in temp_channels
        ]:
            await ctx.respond("Only owners can invite users.", ephemeral=True)
            return
        try:
            invite = await ctx.author.voice.channel.create_invite(
                max_age=max_age, max_uses=max_usage
            )
            await ctx.respond(
                f"Here is your invite link for **{ctx.author.voice.channel.name}**:\n{invite.url}\n"
                f"Expires in {max_age/60} minutes | Max uses: {max_usage}",
                ephemeral=True,
            )
            logger.info(f"Created invite for temporary channel in guild {ctx.guild.id}")
        except discord.Forbidden:
            await ctx.respond(
                "I lack the necessary permissions to create invites for this channel.",
                ephemeral=True,
            )
            logger.error(
                f"Permission error creating invite for temporary channel in guild {ctx.guild.id}"
            )
        except discord.HTTPException as e:
            await ctx.respond(f"Failed to create invite: {e}", ephemeral=True)
            logger.error(
                f"HTTP error creating invite for temporary channel in guild {ctx.guild.id}: {e}"
            )


def setup(bot):
    bot.add_cog(TempVoice(bot))
