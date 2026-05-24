from discord import app_commands, Interaction, Embed, Color
from discord.ext import commands
from db.database import get_session
from db.models import Bank, Deposit, Loan, Citizen, Wallet, Config
from cogs.employment import citizenship, admins, has_roles
from datetime import datetime, timezone


def deposit_interest_rate(session):
    config = session.get(Config, "deposit_tax_rate")
    if config:
        return float(config.value) / 100
    else:
        return 0.01


class Banking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @app_commands.command(name="deposit", description="Deposit coins in your bank.")
    @app_commands.describe(amount="The amount of coins to be deposited.")
    async def deposit(self, interaction: Interaction, amount: int):
        session = get_session()
        try:
            citizen = citizenship(session, interaction.user.id)
            wallet = session.query(Wallet).filter_by(user_id=citizen.user_id).first()
            if amount > wallet.balance:
                await interaction.response.send_message("You are trying to deposit more than you own.", ephemeral=True)
                return
            wallet.balance -= amount
            bank_obj = session.query(Bank).first()
            deposited = session.query(Deposit).filter_by(user_id=citizen.user_id).first()
            if not deposited:
                deposited = Deposit(user_id=citizen.user_id, amount=0)
                session.add(deposited)
            bank_obj.balance += amount
            deposited.amount += amount
            session.commit()
            await interaction.response.send_message(f"Transfer successful. You have transfered {amount} coins in the bank.")
        finally:
            session.close()


    @app_commands.command(name="withdraw", description="Withdraw coins from the bank.")
    @app_commands.describe(amount="The amount to withdraw from the bank.")
    async def withdraw(self, interaction: Interaction, amount: int):
        session = get_session()
        try:
            citizen = citizenship(session, interaction.user.id)
            wallet = session.query(Wallet).filter_by(user_id=citizen.user_id).first()
            bank_obj = session.query(Bank).first()
            deposited = session.query(Deposit).filter_by(user_id=citizen.user_id).first()
            if amount > deposited.amount:
                await interaction.response.send_message("You are trying to withdraw more than you deposited", ephemeral=True)
                return
            days = (datetime.now(timezone.utc) - deposited.deposited_at.replace(tzinfo=timezone.utc)).days
            interest = int(amount * deposit_interest_rate(session) * max(days, 1))
            added = amount + interest
            wallet.balance += added
            deposited.amount -= added
            bank_obj.balance -= added
            await interaction.response.send_message(f"Withdrawal successful. You have withdrawn {amount} from the bank.")
            session.commit()
        finally:
            session.close()
            

    @app_commands.command(name="loan", description="Request a loan from the bank.")
    @app_commands.describe(amount="Amount to be requested.")
    async def loan(self, interaction: Interaction, amount: int):
        session = get_session()
        try:
            citizen = citizenship(session, interaction.user.id)

        finally:
            session.close()


    @app_commands.command(name="repay", description="Repay a loan.")
    @app_commands.describe(id="Loan ID")
    async def repay(self, interaction: Interaction, id: int):
        session = get_session()



    @app_commands.command(name="bankinfo", description="View bank status.")
    async def bankinfo(self, interaction: Interaction):
        session = get_session()
        try:
            bank_admins = admins | {"Banker"}
            if not has_roles(interaction, bank_admins):
                await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
                return
            bank_obj = session.query(Bank).first()
            embed = Embed(title="Bamk Details", color=Color.random())
            embed.add_field(name="Balance:", value=bank_obj.balance, inline=False)
            embed.add_field(name="Deposit Interest Rate:", value=bank_obj.deposit_interest_rate, inline=False)
            embed.add_field(name="Loan Interest Rate:", value=bank_obj.loan_interest_rate, inline=False)
            await interaction.response.send_message(embed=embed)
        finally:
            session.close()


    @app_commands.command(name="bank", description="Check your bank details.")
    async def banks(self, interaction: Interaction):
        session = get_session()



async def setup(bot):
    await bot.add_cog(Banking(bot))
