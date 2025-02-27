from discord.ext import commands, tasks
from database import LevelDB
import discord
import asyncio
import math
import logging


logger = logging.getLogger("discord")

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = LevelDB()
        self.cooldowns = {}

    def cog_unload(self):
        self.voice_xp_task.cancel()

    @tasks.loop(minutes=5)
    async def voice_xp_task(self):
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                for member in channel.members:
                    if not member.bot:
                        try:
                            level = self.db.get_level(guild.id, member.id)
                            xp_gain = 5 * level  # Arbitrary XP gain for sitting in a voice channel
                            self.db.add_xp(guild.id, member.id, xp_gain)
                            current_xp = self.db.get_xp(guild.id, member.id)
                            new_level = self.calculate_level(current_xp)
                            if new_level > level:
                                self.db.set_level(guild.id, member.id, new_level)
                                await self.level_up_announcement(channel, member, new_level)
                        except Exception as e:
                            logger.error(f"Error processing voice XP for member {member.id} in guild {guild.id}: {e}")

    @voice_xp_task.before_loop
    async def before_voice_xp_task(self):
        await self.bot.wait_until_ready()

        self.voice_xp_task.start()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        user_id = message.author.id
        guild_id = message.guild.id
        if self.cooldowns.get(user_id, 0) > asyncio.get_event_loop().time():
            return

        try:
            xp_gain = len(message.content) / 20
            self.db.add_xp(guild_id, user_id, xp_gain)
            self.cooldowns[user_id] = asyncio.get_event_loop().time() + 60

            level = self.db.get_level(guild_id, user_id)
            current_xp = self.db.get_xp(guild_id, user_id)
            new_level = self.calculate_level(current_xp)
            if new_level > level:
                self.db.set_level(guild_id, user_id, new_level)
                await self.level_up_announcement(message.channel, message.author, new_level)
        except Exception as e:
            logger.error(f"Error processing message for XP: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        guild_id = member.guild.id
        user_id = member.id

        if user_id in self.cooldowns and self.cooldowns[user_id] > asyncio.get_event_loop().time():
            return

        try:
            if after.channel and not before.channel:
                xp_gain = 10  # Arbitrary XP gain for joining a voice channel
                self.db.add_xp(guild_id, user_id, xp_gain)
                self.cooldowns[user_id] = asyncio.get_event_loop().time() + 60

                level = self.db.get_level(guild_id, user_id)
                new_level = self.calculate_level(self.db.get_xp(guild_id, user_id))
                if new_level > level:
                    self.db.set_level(guild_id, user_id, new_level)
                    await self.level_up_announcement(after.channel, member, new_level)
        except Exception as e:
            logger.error(f"Error processing voice state update for XP: {e}")

    def calculate_level(self, xp):
        return math.floor(0.1 * math.sqrt(xp))

    async def level_up_announcement(self, channel, user, level):
        embed = discord.Embed(
            title="Level Up!",
            description=f"{user.mention} has reached level {level}!",
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1323598442970218526.png") #change emoji id to your own
        embed.set_footer(text=f"Congratulations!")
        await channel.send(embed=embed)

    xp = discord.SlashCommandGroup(name="xp", description="Commands for the XP system.")

    @xp.command(name="leaderboard", description="Show the XP leaderboard.")
    async def leaderboard(self, ctx):
        guild_id = ctx.guild.id
        try:
            leaderboard = self.db.get_leaderboard(guild_id)
            embed = discord.Embed(
                title="XP Leaderboard",
                description="\n".join([f"{i+1}. {ctx.guild.get_member(entry['user_id']).display_name} - Level {entry['level']}" for i, entry in enumerate(leaderboard)]),
                color=discord.Color.blue(),
            )
            embed.set_thumbnail(url=ctx.guild.icon.url)
            embed.set_footer(text="Top 10 users by XP")
            embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)
            await ctx.respond(embed=embed)
        except Exception as e:
            logger.error(f"Error fetching leaderboard: {e}")
            await ctx.respond("Error fetching leaderboard.", ephemeral=True)

    @xp.command(name="rank", description="Show the rank of a specific user.")
    async def rank(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        guild_id = ctx.guild.id
        try:
            leaderboard = self.db.get_leaderboard(guild_id)
            rank = next((i for i, entry in enumerate(leaderboard) if entry['user_id'] == user.id), None)
            if rank is not None:
                level = self.db.get_level(guild_id, user.id)
                xp = self.db.get_xp(guild_id, user.id)
                embed = discord.Embed(
                    title=f"{user.display_name}'s Rank",
                    description=f"Rank: {rank + 1}\nLevel: {level}\nXP: {xp}/{100*(level+1)**2}",
                    color=discord.Color.blue(),
                )
                embed.set_thumbnail(url=user.display_avatar.url)
                await ctx.respond(embed=embed)
            else:
                await ctx.respond(f"{user.display_name} is not on the leaderboard.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error fetching rank for user {user.id}: {e}")
            await ctx.respond("Error fetching rank.", ephemeral=True)

    @xp.command(name="profile", description="Show the XP profile of a user.")
    async def profile(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        guild_id = ctx.guild.id
        try:
            level = self.db.get_level(guild_id, user.id)
            xp = self.db.get_xp(guild_id, user.id)
            embed = discord.Embed(
                title=f"{user.display_name}'s Profile",
                description=f"Level: {level}\nXP: {xp}/{100*(level+1)**2}",
                color=discord.Color.blue(),
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            await ctx.respond(embed=embed)
        except Exception as e:
            logger.error(f"Error fetching profile for user {user.id}: {e}")
            await ctx.respond("Error fetching profile.", ephemeral=True)

    @commands.has_permissions(administrator=True)
    async def set_level(self, ctx, user: discord.Member, level: int):
        guild_id = ctx.guild.id
        self.db.set_level(guild_id, user.id, level)
        await ctx.respond(f"Set level for user {user.display_name} to {level}.", ephemeral=True)
        logger.info(f"Set level for user {user.id} to {level} in guild {guild_id}")

    @xp.command(name="add_xp", description="Add XP to a user.")
    @commands.has_permissions(administrator=True)
    async def add_xp(self, ctx, user: discord.Member, xp: int):
        guild_id = ctx.guild.id
        self.db.add_xp(guild_id, user.id, xp)
        await ctx.respond(f"Added {xp} XP to user {user.display_name}.", ephemeral=True)
        logger.info(f"Added {xp} XP to user {user.id} in guild {guild_id}")

    @xp.command(name="remove_xp", description="Remove XP from a user.")
    @commands.has_permissions(administrator=True)
    async def remove_xp(self, ctx, user: discord.Member, xp: int):
        guild_id = ctx.guild.id
        self.db.add_xp(guild_id, user.id, -xp)
        await ctx.respond(f"Removed {xp} XP from user {user.display_name}.", ephemeral=True)
        logger.info(f"Removed {xp} XP from user {user.id} in guild {guild_id}")

    @xp.command(name="reset_xp", description="Reset the XP of a user.")
    @commands.has_permissions(administrator=True)
    async def reset_xp(self, ctx, user: discord.Member):
        guild_id = ctx.guild.id
        self.db.add_xp(guild_id, user.id, -self.db.get_xp(guild_id, user.id))
        await ctx.respond(f"Reset XP for user {user.display_name}.", ephemeral=True)
        logger.info(f"Reset XP for user {user.id} in guild {guild_id}")

    @xp.command(name="reset_level", description="Reset the level of a user.")
    @commands.has_permissions(administrator=True)
    async def reset_level(self, ctx, user: discord.Member):
        guild_id = ctx.guild.id
        self.db.set_level(guild_id, user.id, 0)
        await ctx.respond(f"Reset level for user {user.display_name}.", ephemeral=True)
        logger.info(f"Reset level for user {user.id} in guild {guild_id}")

    @xp.command(name="reset_all", description="Reset the XP and level of all users.")
    @commands.has_permissions(administrator=True)
    async def reset_all(self, ctx):
        guild_id = ctx.guild.id
        members = ctx.guild.members
        for member in members:
            if not member.bot:
                self.db.add_xp(guild_id, member.id, -self.db.get_xp(guild_id, member.id))
                self.db.set_level(guild_id, member.id, 0)
        await ctx.respond("Reset XP and level for all users.", ephemeral=True)
        logger.info(f"Reset XP and level for all users in guild {guild_id}")

    @xp.command(name="reset_leaderboard", description="Reset the XP leaderboard.")
    @commands.has_permissions(administrator=True)
    async def reset_leaderboard(self, ctx):
        guild_id = ctx.guild.id
        self.db.db.xp.delete_many({"guild_id": guild_id})
        await ctx.respond("Reset XP leaderboard.", ephemeral=True)
        logger.info(f"Reset XP leaderboard in guild {guild_id}")

def setup(bot):
    """
    Add the XP cog to the bot.

    Parameters:
    bot (commands.Bot): The bot instance to which the cog is added.
    """
    bot.add_cog(Leveling(bot))
