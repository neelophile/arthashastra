from discord import app_commands, Interaction
from discord.ext import commands
from db.models import Citizen, Config as Conf
from db.database import get_session
from cogs.employment import admins, has_roles


class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    config_group = app_commands.Group(name="config", description="Configure settings.")


    @config_group.command(name="profile", description="Configure profile privacy.")
    @app_commands.describe(status="Modify access to your profile")
    @app_commands.choices(status=[app_commands.Choice(name="Public", value="public"), app_commands.Choice(name="Private", value="private")])
    async def profile(self, interaction: Interaction, status: str):
        session = get_session()
        try:
            citizen = session.get(Citizen, interaction.user.id)
            if not citizen:
                await interaction.response.send_message("You are not registered yet.", ephemeral=True)
                return
            citizen.profile_access = status == "public"
            session.commit()
            await interaction.response.send_message(f"Your profile access has been set to {status}")
        finally:
            session.close()


    @config_group.command(name="tax", description="Configure tax rates.")
    @app_commands.describe(rate="The rate of tax.")
    async def tax(self, interaction: Interaction, rate: int):
        if not has_roles(interaction, admins):
            await interaction.response.send_message("This is an admin-only command.", ephemeral=True)
            return
        if not 0 <= rate <= 100:
            await interaction.response.send_message("Rate must be between 0 and 100.", ephemeral=True)
            return
        session = get_session()
        try:
            config = session.get(Conf, "tax_rate")
            if config:
                config.value = str(rate)
            else:
                session.add(ConfigModel(key="tax_rate", value=str(rate)))
            session.commit()
            await interaction.response.send_message(f"Tax rate set to **{rate}%**.")
        finally:
            session.close()



async def setup(bot):
    await bot.add_cog(Config(bot))
