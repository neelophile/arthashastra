from discord import app_commands, Interaction
from discord.ext import commands
from db.models import Citizen, Config as Conf, Loan, utcnow
from db.database import get_session
from cogs.employment import admins, has_roles, citizenship
from typing import Optional
from datetime import datetime, timezone, timedelta


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
            citizen = citizenship(session, interaction.user.id)
            if not citizen:
                await interaction.response.send_message("You are not registered yet.", ephemeral=True)
                return
            citizen.profile_access = status == "public"
            session.commit()
            await interaction.response.send_message(f"Your profile access has been set to {status}.")
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
                session.add(Conf(key="tax_rate", value=str(rate)))
            session.commit()
            await interaction.response.send_message(f"Tax rate set to **{rate}%**.")
        finally:
            session.close()


    @config_group.command(name="loan", description="Configure loan settings.")
    @app_commands.describe(loan_id="ID of the Loan which is to be modified.", days="Due days till loan repayment.", rate="Rate of interest applied on repayment.")
    async def loan(self, interaction: Interaction, loan_id: int, days: Optional[int] = None, rate: Optional[int] = None):
        if not has_roles(interaction, admins | {"Banker"}):
            await interaction.response.send_message("This is a banker-only command.", ephemeral=True)
            return
        session = get_session()
        try:
            loan_obj = session.get(Loan, loan_id)
            if not loan_obj:
                await interaction.response.send_message("This loan does not exist.", ephemeral=True)
                return
            if loan_obj.repaid:
                await interaction.response.send_message("You cannot configure a repaid loan.", ephemeral=True)
                return
            if loan_obj.user_id == interaction.user.id:
                await interaction.response.send_message("I see what you're trying to do :eyes:", ephemeral=True)
                return
            if days:
                loan_obj.due_date = utcnow() + timedelta(days=days)
            if rate:
                loan_obj.interest_rate = rate
            if not any([days, rate]):
                await interaction.response.send_message("You need to update at least something.", ephemeral=True)
                return
            await interaction.response.send_message(f"Loan #{loan_id} updated.")
            session.commit()
        finally:
            session.close()
    

    @config_group.command(name="deposit", description="Configure deposit settings.")
    @app_commands.describe(rate="The interest rate earned upon withdrawal.")
    async def deposit(self, interaction: Interaction, rate: int):
        if not has_roles(interaction, admins | {"Banker"}):
            await interaction.response.send_message("This is a banker-only command.", ephemeral=True)
            return
        if not 0 <= rate <= 100:
            await interaction.response.send_message("Rate must be between 0 to 100.", ephemeral=True)
            return
        session = get_session()
        try:
            config = session.get(Conf, "deposit_interest_rate")
            if config:
                config.value = str(rate)
            else:                                                                                               session.add(Conf(key="deposit_interest_rate", value=str(rate)))
            session.commit()
            await interaction.response.send_message(f"Deposit Interest Rate set to **{rate}%**.")
        finally:
            session.close()


async def setup(bot):
    await bot.add_cog(Config(bot))
