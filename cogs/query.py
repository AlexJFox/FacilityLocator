import discord
from discord.ext import commands
from discord import app_commands
import Paginator
from utils.autocomplete import region_autocomplete


class Query(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command()
    @app_commands.autocomplete(region=region_autocomplete)
    async def locate(self, interaction: discord.Interaction, region: str):
        facilitylist = await self.bot.db.get_facility(region)
        if not facilitylist:
            return await interaction.response.send_message(':x: No facilities in requested region')
        embeds = []
        for facility in facilitylist:
            id, facilityname, region, maintainer, services, notes, author = facility
            e = discord.Embed(title=facilityname,
                              description=notes,
                              color=0x54A24A)
            e.add_field(name='Region-Coordinates', value=region)
            e.add_field(name='Maintainer', value=maintainer)
            e.add_field(name='Author', value=self.bot.get_user(author))
            e.set_footer(text=f'Internal id: {id}')
            embeds.append(e)
        await Paginator.Simple().start(interaction, pages=embeds)
        # await interaction.response.send_message(embed=e)


async def setup(bot: commands.bot) -> None:
    await bot.add_cog(Query(bot))
