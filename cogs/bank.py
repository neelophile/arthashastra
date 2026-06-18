from discord import app_commands, Interaction, Embed, Color
from discord.ext import commands, tasks
from db.database import get_session
from db.models import Bank, Deposit, Loan, Citizen, Wallet, Config, utcnow, Transaction
from cogs.employment import citizenship, admins, has_roles
from datetime import datetime, timezone, timedelta


def deposit_interest_rate(session):
    config = session.get(Config, "deposit_interest_rate")
    if config:
        return float(config.value) / 100
    else:
        return 0.01


def loan_interest_rate(session):
    config = session.get(Config, "loan_interest_rate")
    if config:
        return float(config.value) / 100
    else:
        return 0.05


class Banking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_loans.start()


    def cog_unload(self):
        self.check_loans.cancel()


    @tasks.loop(minutes=30)
    async def check_loans(self):
        session = get_session()
        try:
            now = utcnow()
            overdue = session.query(Loan).filter_by(repaid=False).all()
            for i in overdue:
                due = i.due_date.replace(tzinfo=timezone.utc) if i.due_date.tzinfo is None else i.due_date
                if now < due:
                    continue
                citizen = citizenship(session, i.user_id)
                wallet = session.get(Wallet, i.user_id)
                bank_obj = session.query(Bank).first()
                total = i.amount + int(i.amount * i.interest_rate / 100)
                if not wallet or not bank_obj:
                    continue
                if wallet.balance >= total:
                    wallet.balance -= total
                    bank_obj.balance += total
                    i.repaid = True
                    if not i.penalised:
                        citizen.cibil_score -= 100
                        i.penalised = True
                    guild = self.bot.guilds[0]
                    member = guild.get_member(i.user_id)
                    if member:
                        try:
                            await member.send(f"Your loan of **{total}** coins has been auto-repaid. Due to negligence, Your CIBIL Score has been decreased by 100 points.")
                        except Exception:
                            pass
                elif wallet.balance > 0:
                    bank_obj.balance += wallet.balance
                    i.amount -= wallet.balance
                    wallet.balance = 0
                    if not i.penalised:
                        citizen.cibil_score -= 100
                        i.penalised = True
                    guild = self.bot.guilds[0]
                    member = guild.get_member(i.user_id)
                    if member:
                        try:
                            await member.send(f"Partial auto-repayment has been processed on your loan. Remaining amount to pay: **{i.amount}** coins.")
                        except Exception:
                            pass
                session.commit()
        finally:
            session.close()


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
            deposited.amount -= amount
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
            wallet = session.query(Wallet).filter_by(user_id=citizen.user_id).first()
            bank_obj = session.query(Bank).first()
            if not bank_obj or bank_obj.balance < amount:
                await interaction.response.send_message("The bank doesn't have required funds.", ephemeral=True)
                return
            if citizen.cibil_score >= 750:
                loanable = wallet.balance * 3
            elif citizen.cibil_score >= 650:
                loanable = wallet.balance * 2
            elif citizen.cibil_score >= 450:
                loanable = wallet.balance
            elif citizen.cibil_score < 450:
                await interaction.response.send_message("Your CIBIL Score is too low to seek the loan.", ephemeral=True)
                return
            if amount > loanable:
                await interaction.response.send_message(f"Your CIBIL Score allows only a maximum of {loanable} coins to be lent.", ephemeral=True)
                return
            interest_rate = int(loan_interest_rate(session) * 100)
            due_date = utcnow() + timedelta(days=7)
            session.add(Loan(user_id=citizen.user_id, amount=amount, due_date=due_date, repaid=False, interest_rate=interest_rate))
            session.add(Transaction(from_id=None, to_id=citizen.user_id, amount=amount, type="loan"))
            wallet.balance += amount
            bank_obj.balance -= amount
            session.commit()
            await interaction.response.send_message(f"Loan of {amount} coins approved. You must repay **{amount + int(loan_interest_rate(session) * amount / 100)}** by <t:{int(due_date.timestamp())}:D>.")
        finally:
            session.close()


    @app_commands.command(name="repay", description="Repay a loan.")
    @app_commands.describe(id="Loan ID")
    async def repay(self, interaction: Interaction, id: int):
        session = get_session()
        try:
            citizen = citizenship(session, interaction.user.id)
            loan = session.query(Loan).filter_by(user_id=citizen.user_id, loan_id=id).first()
            if not loan:
                await interaction.response.send_message("No such loan exists.", ephemeral=True)
                return
            if loan.repaid:
                await interaction.response.send_message("This loan has already been paid.", ephemeral=True)
                return
            total = loan.amount + int(loan.amount * loan.interest_rate / 100)
            wallet = session.query(Wallet).filter_by(user_id=citizen.user_id).first()
            bank_obj = session.query(Bank).first()
            if wallet.balance < total:
                await interaction.response.send_message("You do not have enough balance to repay the loan.", ephemeral=True)
                return
            if loan.taken_at and (utcnow() - loan.taken_at).total_seconds() > 86400*2:
                await interaction.response.send_message("You must hold the loan for at least 24 hours before repaying.", ephemeral=True)
                return
            wallet.balance -= total
            bank_obj.balance += total
            citizen.cibil_score += 50
            loan.repaid = True
            session.add(Transaction(from_id=citizen.user_id, to_id=None, amount=total, type='loan'))
            await interaction.response.send_message(f"Loan successfully repaid. Total payment: **{total}** coins. CIBIL Score has been raised by 50 points.")
            session.commit()
        finally:
            session.close()


    @app_commands.command(name="bankinfo", description="View bank status.")
    async def bankinfo(self, interaction: Interaction):
        session = get_session()
        try:
            bank_admins = admins | {"Banker"}
            if not has_roles(interaction, bank_admins):
                await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
                return
            bank_obj = session.query(Bank).first()
            embed = Embed(title="Bank Details", color=Color.random())
            embed.add_field(name="Balance:", value=bank_obj.balance, inline=False)
            embed.add_field(name="Deposit Interest Rate:", value=f"{deposit_interest_rate(session) * 100}%", inline=False)
            embed.add_field(name="Loan Interest Rate:", value=f"{loan_interest_rate(session) * 100}%", inline=False)
            await interaction.response.send_message(embed=embed)
        finally:
            session.close()


    @app_commands.command(name="bank", description="Check your bank details.")
    async def banks(self, interaction: Interaction):
        session = get_session()
        try:
            citizen = citizenship(session, interaction.user.id)
            deposited = session.query(Deposit).filter_by(user_id=citizen.user_id).first()
            embed = Embed(title="Your bank details.", color=Color.random())
            embed.add_field(name="Your balance:", value=deposited.amount if deposited else 0, inline=False)
            embed.add_field(name="Your CIBIL Score:", value=citizen.cibil_score, inline=False)
            loans = session.query(Loan).filter_by(user_id=citizen.user_id, repaid=False).all()
            embed.add_field(name="Active Loans:", value="None" if not loans else "\u200b", inline=False)
            for i in loans:
                total = i.amount + int(i.amount * i.interest_rate / 100)
                embed.add_field(name=f"Loan No. #{i.loan_id}", value=f"Remaining: {i.amount}  | Interest: {i.interest_rate}% | Total Due: {total} |  Due Date: <t:{int(i.due_date.timestamp())}:D>", inline=False)
            await interaction.response.send_message(embed=embed)
        finally:
            session.close()


async def setup(bot):
    await bot.add_cog(Banking(bot))
