from discord import app_commands, Interaction, utils
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
from db.database import get_session
from math import log

from db.models import Citizen, JobLevel, JobXP, Transaction, Wallet, Bounty, NegotiationLog, EmploymentLog, Treasury, Fine, Config, utcnow


role = "Citizen (Level 10-15)"
taxers = {"Finance Minister", "Home Minister", "Prime Minister", "President"}


def has_role(interaction: Interaction, rolename: str):
    return utils.get(interaction.user.roles, name=rolename) is not None


def has_roles(interaction: Interaction, rolenames: set):
    roles = {i.name for i in interaction.user.roles}
    return bool(roles & rolenames)


def xp(prize: int):
    return max(1, int(log(prize + 1) * 10))


def citizenship(session, user_id: int):
    citizen = session.get(Citizen, user_id)
    if not citizen:
        citizen = Citizen(user_id=user_id)
        wallet = Wallet(user_id=user_id)
        session.add(citizen)
        session.add(wallet)
        session.flush()
    return citizen


def tax_rate(session):
    config = session.get(Config, "tax_rate")
    if config:
        return float(config.value) / 100
    else:
        return 0.10


class Employment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_bounties.start()

    def cog_unload(self):
        self.check_bounties.cancel()
        

    @tasks.loop(minutes=10)
    async def check_bounties(self):
        session = get_session()
        try:
            now = utcnow()
            taken = session.query(Bounty).filter_by(status='taken').all()
            for i in taken:
                if i.created_at.tzinfo is None:
                    created = i.created_at.replace(tzinfo=timezone.utc)
                else:
                    i.created_at
                if now >= created + timedelta(hours=48):
                    await self.payment(i, session)
        finally:
            session.close()


    async def payment(self, bounty: Bounty, session):
        if not bounty.prize or not bounty.employee_id:
            return
        taxrate = tax_rate(session)
        tax = int(bounty.prize * taxrate)
        net = bounty.prize - tax
        employee_wallet = session.get(Wallet, bounty.employee_id)
        treasury = session.query(Treasury).first()
        if not employee_wallet or not treasury:
            return
        employee_wallet += net
        treasury.balance += tax
        employee_citizen = session.get(Citizen, bounty.employee_id)
        if employee_citizen:
            employee_citizen.total_income += net
        session.add(Transaction(
            from_id=bounty.customer_id,
            to_id=bounty.employee_id,
            amount=net,
            type="payment",
            bounty_id=bounty.bounty_id
        ))
        session.add(Transaction(
            from_id=bounty.employee_id,
            to_id=None,
            amount=tax,
            type="tax",
            bounty_id=bounty.bounty_id
        ))
        xp_earned = xp(bounty.prize)
        job_xp = session.query(JobXP).filter_by(user_id=bounty.employee_id,
            job_id=employee_citizen.current_job_id).first()
        if job_xp:
            job_xp.xp += xp_earned
        bounty.status = "completed"
        session.commit()
        guild = self.bot.guilds[0]
        channel = guild.get_channel(bounty.channel_id)
        if channel:
            await channel.send(f"Bounty auto-completed. Net coins **{net}** coins paid to employee, **{tax}** coins taxed.")


async def setup(bot):
    await bot.add_cog(Employment(bot))
