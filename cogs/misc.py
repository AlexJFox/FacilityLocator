from typing import ValuesView
from discord.ext import commands
from discord import app_commands
import discord


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command()
    @commands.is_owner()
    async def reload(self, ctx, extension):
        try:
            await self.bot.reload_extension(extension)
        except Exception as e:
            await ctx.send(f':x: Failed to reload extension\n```py\n{e}```')
        else:
            await ctx.send(':white_check_mark: Successfully reloaded')

    @commands.hybrid_command()
    @commands.is_owner()
    async def load(self, ctx, extension):
        try:
            await self.bot.load_extension(extension)
        except Exception as e:
            await ctx.send(f':x: Failed to load extension\n```py\n{e}```')
        else:
            await ctx.send(':white_check_mark: Successfully loaded')

    @commands.hybrid_command()
    @commands.is_owner()
    async def unload(self, ctx, extension):
        try:
            await self.bot.unload_extension(extension)
        except Exception as e:
            await ctx.send(f':x: Failed to unload extension\n```py\n{e}```')
        else:
            await ctx.send(':white_check_mark: Successfully unloaded')

    @commands.hybrid_command()
    @commands.is_owner()
    async def synctree(self, ctx):
        synced_commands = await self.bot.tree.sync()
        command_names = [command.name for command in synced_commands]
        await ctx.send(f':white_check_mark: Synced {len(synced_commands)} commands```{command_names}```')


async def setup(bot: commands.bot) -> None:
    await bot.add_cog(Misc(bot))
