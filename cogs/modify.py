from discord.ext import commands
from discord import (
    app_commands,
    Member,
    TextChannel,
    ui,
    ButtonStyle,
    Attachment,
)

from bot import FacilityBot
from .utils.transformers import (
    LocationTransformer,
    FacilityLocation,
    IdTransformer,
    MarkerTransformer,
)
from .utils.mixins import InteractionCheckedView
from .utils.embeds import FeedbackEmbed, FeedbackType
from .utils.checks import check_facility_permission
from .utils.facility import Facility
from .utils.views import (
    CreateFacilityView,
    ModifyFacilityView,
    RemoveFacilitiesView,
    DynamicListConfirm,
)
from .utils.context import GuildInteraction


class SetupView(InteractionCheckedView):
    @ui.select(
        cls=ui.RoleSelect,
        placeholder="Select roles to access facilities...",
        min_values=0,
        max_values=25,
    )
    async def role_select(self, interaction: GuildInteraction, _: ui.RoleSelect):
        await interaction.response.defer()

    @ui.button(label="Confirm", style=ButtonStyle.blurple)
    async def confirm(self, interaction: GuildInteraction, _: ui.Button):
        await self._finish_view(interaction)
        role_ids = [role.id for role in self.role_select.values]
        try:
            await interaction.client.db.set_roles(role_ids, interaction.guild_id)
        except Exception as exc:
            embed = FeedbackEmbed("Failed to set roles", FeedbackType.ERROR, exc)
        else:
            embed = FeedbackEmbed("Set roles for server", FeedbackType.SUCCESS)

        await interaction.followup.send(embed=embed, ephemeral=True)


class Modify(commands.Cog):
    def __init__(self, bot: FacilityBot):
        self.bot: FacilityBot = bot
        self._facility_being_created: set[int] = set()

    @app_commands.command()
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 20, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.rename(name="facility-name", location="region")
    @check_facility_permission()
    async def create(
        self,
        interaction: GuildInteraction,
        name: app_commands.Range[str, 1, 100],
        location: app_commands.Transform[FacilityLocation, LocationTransformer],
        marker: app_commands.Transform[str, MarkerTransformer],
        maintainer: app_commands.Range[str, 1, 200],
        coordinates: str = "",
        image: Attachment | None = None,
    ) -> None:
        """Creates a public facility

        Args:
            name (str): Name of facility
            location (app_commands.Transform[FacilityLocation, LocationTransformer]): Region with optional coordinates in the form of region-coordinates from ctrl-click of map
            marker (str): Nearest townhall/relic or location
            maintainer (str): Who maintains the facility
            coordinates (str): Optional coordinates (incase it doesn't work in the region field)
            image (discord.Attachment): Image to be displayed along with facility (URL can be set in edit modal)
        """
        final_coordinates = coordinates or location.coordinates
        final_coordinates = final_coordinates.upper()

        if interaction.user.id in self._facility_being_created:
            embed = FeedbackEmbed("Already creating a facility", FeedbackType.ERROR)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        search_dict = {
            " guild_id == ? ": interaction.guild_id,
            " author == ? ": interaction.user.id,
        }

        facility_list = await self.bot.db.get_facilities(search_dict)
        if (
            len(facility_list) >= 5
            and not interaction.user.guild_permissions.administrator
        ):
            embed = FeedbackEmbed(
                "Cannot create more then 5 facilities", FeedbackType.ERROR
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        facility = Facility(
            name=name,
            region=location.region,
            coordinates=final_coordinates,
            maintainer=maintainer,
            author=interaction.user.id,
            marker=marker,
            guild_id=interaction.guild_id,
            image_url=image and image.url,
        )

        view = CreateFacilityView(facility=facility, original_author=interaction.user)
        embed = facility.embed()

        self._facility_being_created.add(interaction.user.id)
        await view.send(interaction, embed=embed, ephemeral=True)
        await view.wait()
        self._facility_being_created.remove(interaction.user.id)

    @app_commands.command()
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 4, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.rename(id_="id")
    @check_facility_permission()
    async def modify(self, interaction: GuildInteraction, id_: int):
        """Modify faciliy information

        Args:
            id_ (int): ID of facility
        """
        facility: Facility = await self.bot.db.get_facility_id(id_)

        if facility is None:
            return await interaction.response.send_message(
                ":x: No facility found", ephemeral=True
            )

        if self.bot.owner_id != interaction.user.id:
            if facility.can_modify(interaction) is False:
                return await interaction.response.send_message(
                    ":x: No permission to modify facility", ephemeral=True
                )

        view = ModifyFacilityView(facility=facility, original_author=interaction.user)
        embed = facility.embed()

        await view.send(interaction, embed=embed, ephemeral=True)

    @app_commands.command()
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 4, key=lambda i: (i.guild_id, i.user.id))
    async def setup(self, interaction: GuildInteraction):
        """Setup the roles to allow access to facilities"""
        view = SetupView(original_author=interaction.user)

        role_ids: list[int] = await self.bot.db.get_roles(interaction.user.guild.id)

        current_roles = "\n".join("<@&%s>" % role_id for role_id in role_ids)
        if current_roles:
            embed = FeedbackEmbed(
                f"Currently selected roles:\n{current_roles}", FeedbackType.INFO
            )
        else:
            embed = FeedbackEmbed(
                "No roles selected, all roles can access facilities", FeedbackType.INFO
            )

        await view.send(
            interaction,
            embed=embed,
            ephemeral=True,
        )

    @app_commands.command()
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 4, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.default_permissions(administrator=True)
    async def set_list_channel(
        self, interaction: GuildInteraction, channel: TextChannel | None
    ):
        """Sets list channel to post updates of facilities

        Args:
            channel (TextChannel): Channel to set, default to current channel
        """
        if not channel:
            if not isinstance(interaction.channel, TextChannel):
                embed = FeedbackEmbed("Channel is not supported", FeedbackType.ERROR)
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )
            channel = interaction.channel

        search_dict = {" guild_id == ? ": interaction.guild_id}

        facility_list: list = await self.bot.db.get_facilities(search_dict)

        embed = FeedbackEmbed(
            f"Confirm setting {channel.mention} as facility update channel",
            FeedbackType.INFO,
        )
        view = DynamicListConfirm(
            original_author=interaction.user,
            selected_channel=channel,
            facilities=facility_list,
        )
        await view.send(interaction, embed=embed, ephemeral=True)

    remove = app_commands.Group(
        name="remove", description="Remove facilities", guild_only=True
    )

    @remove.command()
    @app_commands.checks.cooldown(1, 4, key=lambda i: (i.guild_id, i.user.id))
    @check_facility_permission()
    async def user(self, interaction: GuildInteraction, user: Member):
        """Removes all of the users facilities for the current guild"""

        search_dict = {
            " guild_id == ? ": interaction.guild_id,
            " author == ? ": user.id,
        }
        facilities: list[Facility] = await self.bot.db.get_facilities(search_dict)

        removed_facilities: list[Facility] = []
        for facility in facilities[:]:
            if facility.guild_id != interaction.guild_id:
                facilities.remove(facility)
                removed_facilities.append(facility)
                continue
            if not facility.can_modify(interaction):
                if interaction.user.guild_permissions.administrator:
                    continue
                facilities.remove(facility)
                removed_facilities.append(facility)

        if not facilities:
            embed = FeedbackEmbed("No facilities/required access", FeedbackType.ERROR)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        facility_amount = len(facilities)
        embed = FeedbackEmbed(
            f"Confirm removing {facility_amount} facilit{'ies' if facility_amount > 1 else 'y'} created by {user.mention} from {interaction.guild.name}",
            FeedbackType.WARNING,
        )
        view = RemoveFacilitiesView(
            original_author=interaction.user, facilities=facilities
        )

        await view.send(interaction, embed=embed, ephemeral=True)

    @remove.command()
    @app_commands.checks.cooldown(1, 4, key=lambda i: (i.guild_id, i.user.id))
    @check_facility_permission()
    async def ids(
        self,
        interaction: GuildInteraction,
        ids: app_commands.Transform[tuple, IdTransformer],
    ):
        """Removes facilities by ID's for the current guild

        Args:
            ids (app_commands.Transform[tuple, IdTransformer]): List of facility ID's to remove with a delimiter of ',' or a space ' ' Ex. 1,3 4 8
        """
        facilities: list[Facility] = await self.bot.db.get_facility_ids(ids)
        not_found_facilities = len(ids) - len(facilities)

        removed_facilities: list[Facility] = []
        for facility in facilities[:]:
            if facility.guild_id != interaction.guild_id:
                facilities.remove(facility)
                removed_facilities.append(facility)
                continue
            if not facility.can_modify(interaction):
                if interaction.user.guild_permissions.administrator:
                    continue
                facilities.remove(facility)
                removed_facilities.append(facility)

        if not facilities:
            embed = FeedbackEmbed("No facilities/required access", FeedbackType.ERROR)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        facility_amount = len(facilities)
        embed = FeedbackEmbed(
            f"Confirm removing {facility_amount} facilit{'ies' if facility_amount > 1 else 'y'} from {interaction.guild.name}",
            FeedbackType.WARNING,
        )
        view = RemoveFacilitiesView(
            original_author=interaction.user, facilities=facilities
        )

        removed_facility_amount = len(removed_facilities)
        prevented_message = (
            f":x: Not Removing {removed_facility_amount} facilit{'ies' if removed_facility_amount > 1 else 'y'} due to missing permissions"
            if removed_facility_amount > 0
            else ""
        )

        not_found_message = (
            f":x: {not_found_facilities} facilit{'ies' if not_found_facilities > 1 else 'y'} not found"
            if not_found_facilities > 0
            else ""
        )

        await view.send(
            interaction,
            content="\n".join((prevented_message, not_found_message)),
            embed=embed,
            ephemeral=True,
        )

    @remove.command()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 4, key=lambda i: (i.guild_id, i.user.id))
    @check_facility_permission()
    async def all(self, interaction: GuildInteraction):
        """Removes all facilities for the current guild"""

        search_dict = {"guild_id == ?": interaction.guild_id}
        facilities: list[Facility] = await self.bot.db.get_facilities(search_dict)

        if not facilities:
            embed = FeedbackEmbed("No facilities found", FeedbackType.ERROR)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        facility_amount = len(facilities)
        embed = FeedbackEmbed(
            f"Confirm removing {facility_amount} facilit{'ies' if facility_amount > 1 else 'y'} from {interaction.guild.name}",
            FeedbackType.WARNING,
        )
        view = RemoveFacilitiesView(
            original_author=interaction.user, facilities=facilities
        )

        await view.send(
            interaction,
            embed=embed,
            ephemeral=True,
        )


async def setup(bot: FacilityBot) -> None:
    await bot.add_cog(Modify(bot))
