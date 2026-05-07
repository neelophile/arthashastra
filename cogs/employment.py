from discord import app_commands, Interaction, utils, ui, Embed, Color, ButtonStyle, Member, AllowedMentions
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
from db.database import get_session
from math import log, ceil
from db.models import Citizen, Job, JobLevel, JobXP, Transaction, Wallet, Bounty, NegotiationLog, EmploymentLog, Treasury, Fine, Config, utcnow
from typing import Optional


role = "Citizen (Lv 10 - 15)"
admins = {"Finance Minister", "Home Minister", "Prime Minister", "President", "Chief Justice"}


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


async def autocomplete(interaction: Interaction, current: str):
    session = get_session()
    try:
        jobs = session.query(Job).filter(Job.title.ilike(f"%{current}%")).all()
        return [app_commands.Choice(name=i.title, value=i.slug) for i in jobs]
    finally:
        session.close()


class Pages(ui.View):
    def __init__(self, bounties, author, size=5):
        super().__init__()
        self.bounties = bounties
        self.size = size
        self.author = author
        self.page = 0


    def get_embed(self):
        start = self.page * self.size
        chunk = self.bounties[start:start + self.size]
        embed = Embed(title="Open Bounties", color=Color.random())
        for i in chunk:
            embed.add_field(name=f"ID: {i.bounty_id}", value=f"{i.description}\nPosted by: <@{i.customer_id}>", inline=False)
        embed.set_footer(text=f"Page {self.page + 1}/{ceil(len(self.bounties) / self.size)}")
        return embed


    async def interaction_check(self, interaction: Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("This command is not issued by you.", ephemeral=True)
            return False
        return True

    
    @ui.button(label="Previous", style=ButtonStyle.gray)
    async def previous(self, interaction: Interaction, button: ui.Button):
        self.page = max(0, self.page - 1)
        await interaction.response.edit_message(embed=self.get_embed())


    @ui.button(label="Next", style=ButtonStyle.gray)
    async def next(self, interaction: Interaction, button: ui.Button):
        self.page = min(ceil(len(self.bounties) / self.size) - 1, self.page + 1)
        await interaction.response.edit_message(embed=self.get_embed())


class NegotiateView(ui.View):
    def __init__(self, bounty_id: int, prize: int, employee_id: int, customer):
        super().__init__(timeout=84600)
        self.bounty_id = bounty_id
        self.prize = prize
        self.employee_id = employee_id
        self.customer = customer

    
    async def interaction_check(self, interaction: Interaction):
        if interaction.user.id != self.customer:
            await interaction.response.send_message("These buttons are not meant for you.", ephemeral=True)
            return False
        return True


    @ui.button(label="Accept", style=ButtonStyle.green)
    async def accept(self, interaction: Interaction, button: ui.Button):
        session = get_session()
        try:
            bounty = session.get(Bounty, self.bounty_id)
            bounty.prize = self.prize
            session.commit()
            await interaction.response.send_message(f"The new prize is {bounty.prize}.")
            self.stop()
        finally:
            session.close()


    @ui.button(label="Decline", style=ButtonStyle.red)
    async def decline(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_message("Negotiation has been declined.")
        employee = interaction.guild.get_member(self.employee_id)
        if employee:
            try:
                await employee.send(f"Your negotiation request for Bounty (ID: {self.bounty_id}) was declined by your client.")
            except Exception:
                pass
        self.stop()


class DisputeView(ui.View):
    def __init__(self, bounty_id: int):
        super().__init__(timeout=86400)
        self.bounty_id = bounty_id

    async def interaction_check(self, interaction: Interaction) -> bool:
        session = get_session()
        try:
            bounty = session.get(Bounty, self.bounty_id)
            if interaction.user.id != bounty.employee_id:
                await interaction.response.send_message("These buttons are not meant for you.", ephemeral=True)
                return False
            return True
        finally:
            session.close()

    @ui.button(label="Dispute", style=ButtonStyle.red)
    async def dispute(self, interaction: Interaction, button: ui.Button):
        session = get_session()
        try:
            bounty = session.get(Bounty, self.bounty_id)
            bounty.status = "disputed"
            session.commit()
            await interaction.response.send_message("Bounty has been disputed. A moderator will review.")
            self.stop()
        finally:
            session.close()


    @ui.button(label="No", style=ButtonStyle.gray)
    async def no(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_message("Bounty remains active. Continue working.")
        self.stop()


class CompleteView(ui.View):
    def __init__(self, bounty_id: int, employee_id: int, cog):
        super().__init__(timeout=86400)
        self.bounty_id = bounty_id
        self.employee_id = employee_id
        self.cog = cog

    async def interaction_check(self, interaction: Interaction) -> bool:
        session = get_session()
        try:
            bounty = session.get(Bounty, self.bounty_id)
            if interaction.user.id != bounty.customer_id:
                await interaction.response.send_message("These buttons are not meant for you.", ephemeral=True)
                return False
            return True
        finally:
            session.close()

    @ui.button(label="Accept", style=ButtonStyle.green)
    async def accept(self, interaction: Interaction, button: ui.Button):
        session = get_session()
        try:
            bounty = session.get(Bounty, self.bounty_id)
            await self.cog.payment(bounty, session)
            await interaction.response.send_message("Payment released. Bounty completed.")
            self.stop()
        finally:
            session.close()

    @ui.button(label="Decline", style=ButtonStyle.red)
    async def decline(self, interaction: Interaction, button: ui.Button):
        employee = interaction.guild.get_member(self.employee_id)
        if employee:
            try:
                view = DisputeView(bounty_id=self.bounty_id)
                await employee.send(f"Your completion request for Bounty #{self.bounty_id} was declined. You can dispute it.", view=view)
            except Exception:
                pass
        await interaction.response.send_message("Completion declined.")
        self.stop()


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
                   created = i.created_at
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
        customer_wallet = session.get(Wallet, bounty.customer_id)
        if not employee_wallet or not treasury or not customer_wallet:
            return
        customer_wallet.balance -= bounty.prize
        employee_wallet.balance += net
        treasury.balance += tax
        employee_citizen = session.get(Citizen, bounty.employee_id)
        if employee_citizen:
            employee_citizen.total_income += net
        session.add(Transaction(from_id=bounty.customer_id, to_id=bounty.employee_id, amount=net, type="payment", bounty_id=bounty.bounty_id))
        session.add(Transaction(from_id=bounty.employee_id, to_id=None, amount=tax, type="tax", bounty_id=bounty.bounty_id))
        xp_earned = xp(bounty.prize)
        job_xp = session.query(JobXP).filter_by(user_id=bounty.employee_id, job_id=employee_citizen.current_job_id).first()
        if job_xp:
            job_xp.xp += xp_earned
        bounty.status = "completed"
        session.commit()
        guild = self.bot.guilds[0]
        channel = guild.get_channel(bounty.channel_id)
        if channel:
            await channel.send(f"Bounty auto-completed. Net coins **{net}** coins paid to employee, **{tax}** coins taxed.")
    

    @app_commands.command(name="employ", description="Get a job.")
    @app_commands.autocomplete(job=autocomplete)
    async def employ(self, interaction: Interaction, job: str):
        if not has_role(interaction, role):
            await interaction.response.send_message("You are not Level 10 yet.", ephemeral=True)
            return
        session = get_session()
        try:
            citizen = citizenship(session, interaction.user.id)
            if citizen.current_job_id:
                await interaction.response.send_message("You are already employed.", ephemeral=True)
                return
            if citizen.last_quit:
                if citizen.last_quit.tzinfo is None:
                    last_quit = citizen.last_quit.replace(tzinfo=timezone.utc)
                else:
                    last_quit = citizen.last_quit
                remaining = (last_quit + timedelta(hours=48)) - utcnow()
                if remaining.total_seconds() > 0:
                    hours = int(remaining.total_seconds() // 3600)
                    minutes = int((remaining.total_seconds() % 3600) // 60)
                    seconds = int(remaining.total_seconds() % 60)
                    await interaction.response.send_message(f"You're on a cooldown. {hours}h {minutes}m {seconds}s remaining", ephemeral=True)
                    return
            job_object = session.query(Job).filter_by(slug=job).first()
            if not job_object:
                await interaction.response.send_message("No such job.", ephemeral=True)
                return
            level1 = session.query(JobLevel).filter_by(job_id=job_object.job_id, level=1).first()
            existing_xp = session.query(JobXP).filter_by(user_id=interaction.user.id, job_id=job_object.job_id).first()
            if not existing_xp:
                session.add(JobXP(user_id=interaction.user.id, job_id=job_object.job_id, xp=0))  
            session.add(EmploymentLog(user_id=interaction.user.id, job_id=job_object.job_id))
            citizen.current_job_id = job_object.job_id
            if level1:
                citizen.job_level_id = level1.job_level_id
            else: 
                citizen.job_level_id = None
            session.commit()
            await interaction.response.send_message(f"Your new job is now: {job_object.title}")
        finally:
            session.close()

    
    @app_commands.command(name="quit", description="Quit a job.")
    async def quit_job(self, interaction: Interaction):
        session = get_session()
        try:
            citizen = citizenship(session, interaction.user.id)
            if not citizen.current_job_id:
                await interaction.response.send_message("You are already unemployed", ephemeral=True)
                return
            citizen.current_job_id = None
            citizen.job_level_id = None
            citizen.last_quit = utcnow()
            log = session.query(EmploymentLog).filter_by(user_id=interaction.user.id, quit_at=None).first()
            if log:
                log.quit_at = utcnow()
            session.commit()
            await interaction.response.send_message("You have quit your job.")
        finally:
            session.close()


    @app_commands.command(name="issue", description="Issue a bounty")
    @app_commands.autocomplete(for_job=autocomplete)
    async def issue(self, interaction: Interaction, description: str, for_job: str, prize: int):
        session = get_session()
        try:
            wallet = session.get(Wallet, interaction.user.id)
            if not wallet or wallet.balance < prize:
                await interaction.response.send_message("You do not have enough money", ephemeral=True)
                return
            job_obj = session.query(Job).filter_by(slug=for_job).first()
            if not job_obj:
                await interaction.response.send_message("No such job", ephemeral=True)
                return
            citizen = citizenship(session, interaction.user.id)
            bounty_obj = Bounty(customer_id=interaction.user.id, description=description, job_id=job_obj.job_id, prize=prize)
            session.add(bounty_obj)
            session.flush()
            session.commit()
            await interaction.response.send_message(f"Bounty has been issued. ID: {bounty_obj.bounty_id}")
        finally:
            session.close()


    @app_commands.command(name="bounties", description="Check available bounties")
    async def bounties(self, interaction: Interaction):
        session = get_session()
        try:
            citizen = citizenship(session, interaction.user.id)
            if not citizen.current_job_id:
                await interaction.response.send_message("You must be employed to use this command.", ephemeral=True)
                return
            bounty = session.query(Bounty).filter_by(job_id=citizen.current_job_id, status="open").all()
            if not bounty:
                await interaction.response.send_message("No bounties for now.", ephemeral=True)
                return
            view = Pages(bounty, interaction.user)
            await interaction.response.send_message(embed=view.get_embed(), view=view)
        finally:
            session.close()


    @app_commands.command(name="claim", description="Claim a bounty.")
    async def claim(self, interaction: Interaction, id: int):
        session = get_session()
        try:
            citizen = citizenship(session, interaction.user.id)
            if not citizen.current_job_id:
                await interaction.response.send_message("You must be employed to use this command.", ephemeral=True)
                return
            bounty = session.query(Bounty).filter_by(bounty_id=id).first()
            if not bounty:
                await interaction.response.send_message("No such bounty found.", ephemeral=True)
                return
            if bounty.status != "open":
                await interaction.response.send_message("The bounty is either taken, completed or in dispute", ephemeral=True)
                return
            if bounty.customer_id == interaction.user.id:
                await interaction.response.send_message("I see what you're trying to do :eyes:", ephemeral=True)
                return
            category = utils.get(interaction.guild.categories, name="Bounties")
            channel = await interaction.guild.create_text_channel(name=f"bounty-{id}", category=category)
            await channel.set_permissions(interaction.guild.default_role, view_channel=False)
            await channel.set_permissions(interaction.user, view_channel=True)
            await channel.set_permissions(interaction.guild.get_member(bounty.customer_id), view_channel=True)
            bounty.employee_id = interaction.user.id
            bounty.channel_id = channel.id
            bounty.status = "taken"
            session.commit()
            await interaction.response.send_message(f"Your Bounty ID is: {bounty.bounty_id}. Visit <#{channel.id}> to discuss further with your client.")
        finally:
            session.close()


    @app_commands.command(name="negotiate", description="Negotiate the prize money.")
    async def negotiate(self, interaction: Interaction, id: int, prize: int):
        session = get_session()
        try:
            bounty = session.query(Bounty).filter_by(employee_id=interaction.user.id, bounty_id=id).first()
            if not bounty:
                await interaction.response.send_message("No such bounty exists", ephemeral=True)
                return
            if bounty.status != "taken":
                await interaction.response.send_message("You haven't taken this bounty.", ephemeral=True)
                return
            session.add(NegotiationLog(bounty_id=id, proposed_by=interaction.user.id, amount=prize))
            session.commit()
            channel = interaction.guild.get_channel(bounty.channel_id)
            customer = interaction.guild.get_member(bounty.customer_id)
            if channel:
                view = NegotiateView(bounty_id=id, prize=prize, employee_id=interaction.user.id, customer=bounty.customer_id)
                await channel.send(f"{customer.mention if customer else 'Customer'}, {interaction.user.mention}  proposes **{prize}** coins", view=view, allowed_mentions=AllowedMentions(users=False))
            await interaction.response.send_message("Negotiation request sent.")
        finally:
            session.close()


    @app_commands.command(name="complete", description="Mark a bounty as complete.")
    async def complete(self, interaction: Interaction, id: int):
        session = get_session()
        try:
            bounty = session.query(Bounty).filter_by(employee_id=interaction.user.id, bounty_id=id).first()
            if not bounty:
                await interaction.response.send_message("No such bounty exists.", ephemeral=True)
                return
            if bounty.status != "taken":
                await interaction.response.send_message("This bounty is not active.", ephemeral=True)
                return
            channel = interaction.guild.get_channel(bounty.channel_id)
            customer = interaction.guild.get_member(bounty.customer_id)
            if channel:
                view = CompleteView(bounty_id=id, employee_id=interaction.user.id, cog=self)
                await channel.send(f"{customer.mention if customer else 'Customer'}, {interaction.user.mention} has marked this bounty as complete.", view=view, allowed_mentions=AllowedMentions(users=True))
            await interaction.response.send_message("Completion request sent.", ephemeral=True)
        finally:
            session.close()


    @app_commands.command(name="profile", description="Sends the statistics of the selected person.")
    async def profile(self, interaction: Interaction, member: Optional[Member] = None):
        target = member or interaction.user
        session = get_session()
        try:
            citizen = citizenship(session, target.id)
            name = target.mention
            job = session.get(Job, citizen.current_job_id)
            job_title = job.title if job else "Unemployed"
            level = session.query(JobLevel).filter_by(job_level_id=citizen.job_level_id).first()
            level_str = f"{level.level} — {level.title}" if level else 0
            xp = session.query(JobXP).filter_by(user_id=target.id, job_id=citizen.current_job_id).first()
            xp_next = session.query(JobLevel).filter_by(job_id=citizen.current_job_id, level=level.level + 1).first() if level else None
            xp_needed = xp_next.xp_required if xp_next else "MAX"
            xp_count = xp.xp if xp else 0
            bounties = len(session.query(Bounty).filter_by(employee_id=target.id, status="completed").all())
            if not citizen.profile_access and citizen.user_id != interaction.user.id and not has_roles(interaction, admins):
                await interaction.response.send_message("The profile you are trying to access is private.", ephemeral=True)
                return
            embed = Embed(title="Your Profile", color=Color.random())
            embed.add_field(name="Name:", value=name, inline=True)
            embed.add_field(name="Job:", value=job_title, inline=True)
            embed.add_field(name="Level:", value=level_str, inline=True)
            embed.add_field(name="XP:", value=f"{xp_count}/{xp_needed}", inline=True)
            embed.add_field(name="Bounties completed:", value=bounties, inline=True)
            embed.set_thumbnail(url=target.display_avatar.url)
            await interaction.response.send_message(embed=embed)
        finally:
            session.close()


    @app_commands.command(name="wallet", description="Displays balance in a person's aiccount.")
    async def wallet(self, interaction: Interaction, member: Optional[Member] = None):
        target = member or interaction.user
        session = get_session()
        try:
            citizen = citizenship(session, target.id)
            wallet = session.query(Wallet).filter_by(user_id=citizen.user_id).first()
            balance = wallet.balance if wallet else 0
            if not citizen.profile_access and citizen.user_id != interaction.user.id and not has_roles(interaction, admins):
                await interaction.response.send_message("The profile you are trying to access is private.", ephemeral=True)
                return
            msg = "You have" if target.id == interaction.user.id else f"{target.mention} has"
            await interaction.response.send_message(f"{msg} {balance} coins in their wallet.", allowed_mentions=AllowedMentions(users=False))
        finally:
            session.close()
    

    @app_commands.command(name="leaderboard", description="Shows the server leaderboards.")
    async def leaderboard(self, interaction: Interaction):
        session = get_session()
        try:
            citizen = session.query(Citizen).order_by(Citizen.total_income.desc()).limit(10).all()
            embed = Embed(title="Here the the top 10 players of the server.", color=Color.random())
            for i, j in enumerate(citizen, start=1):
                member = interaction.guild.get_member(j.user_id)
                name = member.mention if member else str(j.user_id)
                embed.add_field(name=f"{i}", value=f"{name} — {j.total_income} coins in total.", inline=True)
            await interaction.response.send_message(embed=embed)
        finally:
            session.close()


    @app_commands.command(name="fine", description="Fine citizens with an amount.")
    async def fine(self, interaction: Interaction, member: Member, amount: int, reason: Optional[str] = None):
        session = get_session()
        try:
            if not has_roles(interaction, admins):
                await interaction.response.send_message("This is an admin-only command.", ephemeral=True)
                return
            citizen = citizenship(session, member.id)
            wallet = session.get(Wallet, member.id)
            if not wallet or wallet.balance < amount:
                await interaction.response.send_message("The citizen in context does not have enough balance.")
                return
            wallet.balance -= amount
            treasury = session.query(Treasury).first()
            treasury.balance += amount
            session.add(Fine(issued_to=member.id, amount=amount, reason=reason))
            session.add(Transaction(from_id=member.id, to_id=None, amount=amount, type="fine"))
            session.commit()
            await interaction.response.send_message(f"{member.mention} has been fined **{amount}** coins. Reason: {reason if reason else "None"}", allowed_mentions=AllowedMentions(users=False))
            try:
                await member.send(f"You have been fined with **{amount}** coins.")
            except Exception:
                pass
        finally:
            session.close()


    @app_commands.command(name="send", description="Send someone coins.")
    async def send(self, interaction: Interaction, amount: int, member: Member):
        session = get_session()
        try:
            citizen = citizenship(session, interaction.user.id)
            wallet = session.get(Wallet, interaction.user.id)
            if member.id == interaction.user.id:
                await interaction.response.send_message("Wanna send youself money? Get a job.", ephemeral=True)
                return
            if wallet.balance < amount:
                await interaction.response.send_message("You don't have enough coins.", ephemeral=True)
                return
            wallet.balance -= amount
            receiver = session.query(Wallet).filter_by(user_id=member.id).first()
            receiver.balance += amount
            session.add(Transaction(from_id=interaction.user.id, to_id=member.id, amount=amount, type="payment"))
            session.commit()
            await interaction.response.send_message(f"Transaction successful! You have transferred {amount} coins to {member.mention}.", allowed_mentions=AllowedMentions(users=False))
            try:
                await member.send(f"You have received {amount} from {interaction.user.mention}.")
            except Exception:
                pass
        finally:
            session.close()


    @app_commands.command(name="treasury", description="Check the Server Treasury.")
    async def treasury(self, interaction: Interaction):
        session = get_session()
        try:
            if not has_roles(interaction, admins):
                await interaction.response.send_message("This is an admin-only command.", ephemeral=True)
                return
            treasury_obj = session.query(Treasury).first()
            await interaction.response.send_message(f"Treasury: {treasury_obj.balance} coins")
            
        finally:
            session.close()


async def setup(bot):
    await bot.add_cog(Employment(bot))
