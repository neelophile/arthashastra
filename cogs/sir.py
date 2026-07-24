from discord import app_commands, Interaction, utils, Embed, Color, Member, AllowedMentions
from discord.ext import commands, tasks
from db.database import get_session
from db.models import utcnow, Citizen, SIRRecord, Wallet, Bounty, Transaction, Job, PartyMember, Party
from cogs.employment import has_roles, has_role
from datetime import datetime, timezone, timedelta


sir_channel = "s-i-r"
cec = "Chief Election Commissioner"
president = "President"


def is_cec(interaction: Interaction):
    return has_role(interaction, cec) or has_role(interaction, president)


class SIR(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_responses.start()


    def cog_unload(self):
        self.check_responses.cancel()


    @tasks.loop(minutes=30)
    async def check_responses(self):
        session = get_session()
        try:
            now = utcnow()
            pinged = session.query(SIRRecord).filter_by(status="pinged").all()
            for i in pinged:
                pinged_at = i.pinged_at.replace(tzinfo=timezone.utc) if i.pinged_at.tzinfo is None else i.pinged_at
                if now >= pinged_at + timedelta(hours=24):
                    i.status = "no_response"
                    guild = self.bot.guilds[0]
                    channel = utils.get(guild.text_channels, name=sir_channel)
                    if channel:
                        await channel.send(f"⚠️ <@{i.user_id}> has not responded in 24 hours. Status changed to **No Response**")
            session.commit()
        finally:
            session.close()


    sir_group = app_commands.Group(name="sir", description="SIR Commands")


    @sir_group.command(name="start", description="Initiate a Server Integrity Review.")
    async def sir_start(self, interaction: Interaction):
        if not is_cec(interaction):
            await interaction.response.send_message("Only CEC and President can use this command. (Default = 30)", ephemeral=True)
            return
        await interaction.response.defer()
        guild = interaction.guild
        session = get_session()
        try:
            now = utcnow()
            flagged = []
            citizens = session.query(Citizen).all()
            for i in citizens:
                member = guild.get_member(i.user_id)
                if not member:
                    existing = session.query(SIRRecord).filter_by(user_id=i.user_id).filter(SIRRecord.status.notin_(["purged", "cleared"])).first()
                    if not existing:
                        session.add(SIRRecord(user_id=i.user_id, reason="Left the server."))
                        flagged.append((i.user_id, "Left the server"))
            for i in citizens:
                member = guild.get_member(i.user_id)
                if not member:
                    continue
                if i.last_active is None or (now - i.last_active.replace(tzinfo=timezone.utc)).days > 30:
                    existing = session.query(SIRRecord).filter_by(user_id=i.user_id).filter(SIRRecord.status.notin_(["purged", "cleared"])).first()
                    if not existing:
                        days_inactive = "Never active" if not i.last_active else f"Inactive for {(now - i.last_active.replace(tzinfo=timezone.utc)).days} days"
                        session.add(SIRRecord(user_id=i.user_id, reason=days_inactive))
                        flagged.append((i.user_id, days_inactive))
            for i in guild.members:
                if i.bot:
                    continue
                account_age = (now - i.created_at.replace(tzinfo=timezone.utc)).days
                if account_age < 30:
                    existing = session.query(SIRRecord).filter_by(user_id=i.id).filter(SIRRecord.status.notin_(["purged", "cleared"])).first()
                    if not existing:
                        session.add(SIRRecord(user_id=i.id, reason=f"Account is {account_age} days old."))
                        flagged.append((i.id, f"Account is {account_age} days old"))
            session.commit()
            channel = utils.get(guild.text_channels, name=sir_channel)
            if not channel:
                await interaction.followup.send("SIR Channel not found.", ephemeral=True)
                return
            if not flagged:
                await interaction.followup.send("No accounts flagged.", ephemeral=True)
                return
            embed = Embed(title="🔍 SIR Draft Report", color=Color.orange())
            embed.description = f"**{len(flagged)}** accounts flagged. Use `/sir ping` to notify them."
            for user_id, reason in flagged[:25]:
                embed.add_field(name=f"<@{user_id}>", value=reason, inline=False)
            if len(flagged) > 25:
                embed.set_footer(text=f"...and {len(flagged) - 25} more. Use `/sir report for full list.`")
            await channel.send(embed=embed)
            await interaction.followup.send(f"SIR Initiated. {len(flagged)} accounts flagged. Check #{sir_channel}.")
        finally:
            session.close()


    @sir_group.command(name="ping", description="Ping flagged members to respond.")
    async def sir_ping(self, interaction: Interaction):
        if not is_cec(interaction):
            await interaction.response.send_message("Only CEC or President can use this.", ephemeral=True)
            return
        await interaction.response.defer()
        session = get_session()
        try:
            records = session.query(SIRRecord).filter(SIRRecord.status.in_(["flagged", "no_response"])).all()
            if not records:
                await interaction.followup.send("No flagged members to ping.", ephemeral=True)
                return
            channel = utils.get(interaction.guild.text_channels, name=sir_channel)
            if not channel:
                await interaction.followup.send("SIR channel #report not found.", ephemeral=True)
                return
            count = 0
            for i in records:
                member = interaction.guild.get_member(i.user_id)
                if not member:
                    continue
                i.status = "pinged"
                i.pinged_at = utcnow()
                await channel.send(f"{member.mention}, you have been flagged in a **Special Investigation Report**. Please respond to this message within **24 hours** to confirm your account is active. Failure to respond may result in removal from the electoral roll.")
                count += 1
            session.commit()
            await interaction.followup.send(f"Pinged {count} members in #{sir_channel}.")
        finally:
            session.close()


    @sir_group.command(name="info", description="View full bot info on a member.")
    @app_commands.describe(member="Member to inspect.")
    async def sir_info(self, interaction: Interaction, member: Member):
        if not is_cec(interaction):
            await interaction.response.send_message("Only CEC or President can use this.", ephemeral=True)
            return
        session = get_session()
        try:
            citizen = session.get(Citizen, member.id)
            wallet = session.get(Wallet, member.id)
            bounties_done = session.query(Bounty).filter_by(employee_id=member.id, status="completed").count()
            last_tx = session.query(Transaction).filter((Transaction.from_id == member.id) | (Transaction.to_id == member.id)).order_by(Transaction.timestamp.desc()).first()
            sir_record = session.query(SIRRecord).filter_by(user_id=member.id).first()
            job = session.get(Job, citizen.current_job_id) if citizen and citizen.current_job_id else None
            party_member = session.query(PartyMember).filter_by(user_id=member.id).first()
            party = session.get(Party, party_member.party_id) if party_member else None
            embed = Embed(title=f"SIR Info — {member.display_name}", color=Color.blue())
            embed.add_field(name="Account Created:", value=f"<t:{int(member.created_at.timestamp())}:D>", inline=True)
            embed.add_field(name="Joined Server:", value=f"<t:{int(member.joined_at.timestamp())}:D>" if member.joined_at else "Unknown", inline=True)
            embed.add_field(name="Citizen Record:", value="Yes" if citizen else "No", inline=True)
            embed.add_field(name="Wallet Balance:", value=f"{wallet.balance} coins" if wallet else "No wallet", inline=True)
            embed.add_field(name="Bounties Completed:", value=bounties_done, inline=True)
            embed.add_field(name="Last Transaction:", value=f"<t:{int(last_tx.timestamp.timestamp())}:R>" if last_tx else "Never", inline=True)
            embed.add_field(name="Current Job:", value=job.title if job else "Unemployed", inline=True)
            embed.add_field(name="Party:", value=party.name if party else "None", inline=True)
            embed.add_field(name="SIR Status:", value=sir_record.status if sir_record else "Not flagged", inline=True)
            embed.add_field(name="Last active:", value=f"<t:{int(citizen.last_active.timestamp())}:R>" if citizen and citizen.last_active else "Never", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            session.close()


    @sir_group.command(name="clear", description="Clear a member from the flagged list.")
    @app_commands.describe(member="Member to clear.")
    async def sir_clear(self, interaction: Interaction, member: Member):
        if not is_cec(interaction):
            await interaction.response.send_message("Only CEC or President can use this.", ephemeral=True)
            return
        session = get_session()
        try:
            record = session.query(SIRRecord).filter_by(user_id=member.id).first()
            if not record:
                await interaction.response.send_message("No SIR record found for this member.", ephemeral=True)
                return
            record.status = "cleared"
            session.commit()
            await interaction.response.send_message(f"{member.display_name} cleared from SIR.", ephemeral=True)
        finally:
            session.close()


    @sir_group.command(name="purge", description="Remove a citizen from the DB.")
    @app_commands.describe(member="Member to purge.")
    async def sir_purge(self, interaction: Interaction, member: Member):
        if not is_cec(interaction):
            await interaction.response.send_message("Only CEC or President can use this.", ephemeral=True)
            return
        session = get_session()
        try:
            record = session.query(SIRRecord).filter_by(user_id=member.id).first()
            if record:
                record.status = "purged"
            citizen = session.get(Citizen, member.id)
            if citizen:
                session.delete(citizen)
            session.commit()
            await interaction.response.send_message(f"{member.display_name} purged from citizen records.", ephemeral=True)
        finally:
            session.close()


    @sir_group.command(name="report", description="Post full SIR report.")
    async def sir_report(self, interaction: Interaction):
        if not is_cec(interaction):
            await interaction.response.send_message("Only CEC or President can use this.", ephemeral=True)
            return
        session = get_session()
        try:
            records = session.query(SIRRecord).all()
            if not records:
                await interaction.response.send_message("No SIR records found.", ephemeral=True)
                return
            channel = utils.get(interaction.guild.text_channels, name=sir_channel)
            embed = Embed(title="📋 Full SIR Report", color=Color.red())
            for i in records[:25]:
                embed.add_field(name=f"<@{i.user_id}>", value=f"Reason: {i.reason} | Status: **{i.status}** | Flagged: <t:{int(i.flagged_at.timestamp())}:D>", inline=False)
            await channel.send(embed=embed)
            await interaction.response.send_message("Report posted.", ephemeral=True)
        finally:
            session.close()


    @sir_group.command(name="reinstate", description="Reinstate a purged citizen.")
    @app_commands.describe(member="Member to reinstate.")
    async def sir_reinstate(self, interaction: Interaction, member: Member):
        if not is_cec(interaction):
            await interaction.response.send_message("Only CEC or President can use this.", ephemeral=True)
            return
        session = get_session()
        try:
            existing = session.get(Citizen, member.id)
            if existing:
                await interaction.response.send_message("This citizen already has a record.", ephemeral=True)
                return
            citizen = Citizen(user_id=member.id)
            wallet = Wallet(user_id=member.id)
            session.add(citizen)
            session.add(wallet)
            record = session.query(SIRRecord).filter_by(user_id=member.id).first()
            if record:
                record.status = "cleared"
            session.commit()
            await interaction.response.send_message(f"{member.display_name} reinstated as a citizen.", ephemeral=True)
        finally:
            session.close()


async def setup(bot):
    await bot.add_cog(SIR(bot))

