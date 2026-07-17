from discord import app_commands, Interaction, utils, ui, Embed, Color, ButtonStyle, Member
from discord.ext import commands, tasks
from datetime import datetime, timezone
from db.database import get_session
from db.models import utcnow, Election, Candidate, Party, PartyMember, Vote, Citizen
from cogs.employement import has_role, has_roles, citizenship
from typing import Optional


cec = "Chief Election Commissioner"
president = "President"
level_25 = "Citizen (Level 25 - 30)"
level_35 = "Citizen (Level 35 - 40)"


def is_cec(interaction: Interaction):
    return has_roles(interaction, {cec, president})


class VoteView(ui.View):
    def __init__(self, election_id: int, candidates: list):
        super().__init__(timeout=None)
        for candidate, label in candidates:
            self.add_item(VoteButton(election_id=election_id, candidate=candidate, label=label))


class VoteButton(ui.Button):
    def __init__(self, election_id: int, candidate, label: str):
        self.election_id = election_id
        self.candidate_obj = candidate
        super().__init__(label=label[:80], style=ButtonStyle.primary, custom_id=f"vote_{election_id}_{candidate.candidate_id}")


    async def callback(self, interaction: Interaction):
        session = get_session()
        try:
            existing = session.query(Vote).filter_by(election_id=self.election_id, voter_id=interaction.user.id).first()
            if existing:
                exisiting.candidate_id = self.candidate_obj.candidate_id
                session.commit()
                await interaction.response.send_message("Your vote has been updated.", ephemeral=True)
            else:
                session.add(Vote(election_id=self.election_id, voter_id=interaction.user.id, candidate_id=self.candidate_obj.candidate_id))
                session.commit()
                await interaction.response.send_message("Your vote has been cast", ephemeral=True)
        finally:
            session.close()


class InviteView(ui.View):
    def __init__(self, party_id: int, invitee_id: int):
        super().__init__(timeout=84600)
        self.party_id = party_id
        self.invitee_id = invitee_id
    

    async def interaction_check(self, interaction: Interaction):
        if interaction.user.id != self.invitee_id:
            await interaction.response.send_message("This invite is not for you.", ephemeral=True)
            return False
        return True


    @ui.button(label="Accept", style=ButtonStyle.green)
    async def accept(self, interaction: Interaction, button: ui.Button):
        session = get_session()
        try:
            existing = session.query(PartyMember).filter_by(user_id=interaction.user.id).first()
            if existing:
                await interaction.response.send_message("You are already in a party.", ephemeral=True)
                return
            session.add(PartyMember(party_id=self.party_id, user_id=interaction.user.id))
            session.commit()
            await interaction.response.send_message("You have joined the party.")
            self.stop()
        finally:
            session.close()


    @ui.button(label="Reject", style=ButtonStyle.red)
    async def reject(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_message("Invite Declined.")
        self.stop()


class Elections(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_elections.start()


    def cog_unload(self):
        self.check_elections.cancel()


    @tasks.loop(minutes=5)
    async def check_elections(self):
        session = get_session()
        try:
            now = utcnow()
            ongoing = session.query(Election).filter_by(status="ongoing").all()
            for i in ongoing:
                end = i.end_date.replace(tzinfo=timezone.utc) if i.end_date.tzinfo is None else i.end_date
                if now >= end:
                    await self.declare_results(i, session)
        finally:
            session.close()


    async def declare_results(self, election: Election, session):
        candidates = session.query(Candidate).filter_by(election_id=election.election_id).all()
        results = []
        for i in candidates:
            count = session.query(Vote).filter_by(election_id=election.election_id, candidate_id=i.candidate_id).count()
            results.append((i, count))
        results.sort(key=lambda x: x[1], reverse=True)
        top = results[:election.seats]
        election.status = "closed"
        session.commit()
        guild = self.bot.guilds[0]
        channel = utils.get(guild.text_channels, name="lok-sabha")
        if not channel:
            return
        embed = Embed(title="Election Results", color=Color.gold())
        for i, (candidate, votes) in enumerate(top, 1):
            if candidate.is_party:
                party = session.get(Party, candidate.party_id)
                name = party.name if party else f"Party {candidate.party_id}"
            else:
                member = guild.get_member(candidate.user_id)
                name = member.display_name if member else str(candidate.user_id)
            embed.add_field(name=f"{i}. {name}", value=f"{votes} votes", inline=False)
        await channel.send(embed=embed)


    election_group = app_commands.Group(mame="election", description="Election-related commands.")


    @election_group.command(name="create", description="Create and start an election.")
    @app_commands.describe(type="Type of election.", end_date="End Date in DD-MM-YYYY format.")
    @app_commands.choices(type=[app_commands.Choice(name="Cabinet", value="cabinet"), app_commands.Choice(name="Club", value="club"), app_commands.Choice(name="Byelection", value="byelection")])
    async def create(self, interaction: Interaction, type: str, end_date: str, seats: Optional[int] = None):
        if not is_cec(interaction):
            await interaction.response.send_message("Only CEC or the President can create elections.", ephemeral=True)
            return
        try:
            date = datetime.strptime(end_date, "%d-%m-%Y").replace(tzinfo=timezone.utc)
        except ValueError:
            await interaction.response.send_message("Invalid date format, use DD-MM-YYYY.", ephemeral=True)
            return
        if date <= utcnow():
            await interaction.response.send_message("End date must be in the future.", ephemeral=True)
            return
        session = get_session()
        try:
            if seats is None:
                seats = 7 if type == "cabinet" else 1
            election = Election(type=type, status="registration", end_date=date, created_by=interaction.user.id, seats=seats)
            session.add(election)
            session.commit()
            await interaction.response.send_message(f"{type.capitalize()} election created. ID: `{election.election_id}`. Ends: <t:{int(date.timestamp())}:D>")
        finally:
            session.close()

    
    @election_group.command(name="register", description="Register as a candidate")
    @app_commands.describe(election_id="ID of the Election.")
    async def register(self, interaction: Interaction, election_id: int):
        if not has_role(interaction, level_25):
            await interaction.response.send_message("You are not eligible to contest the elections.", ephemeral=True)
            return
        session = get_session()
        try:
            election = session.get(Election, election_id)
            if not election or election.status != "registration":
                await interaction.response.send_message("Election is not in registration phase anymore.", ephemeral=True)
                return
            party_member = session.query(PartyMember).filter_by(user_id=interaction.user.id).first()
            if party_member:
                party = session.get(Party, party_member.party_id)
                if party.leader_id != interaction.user.id:
                    await interaction.response.send_message("Only the party leader can register the party.", ephemeral=True)
                    return
                existing = session.query(Candidate).filter_by(election_id=election_id, party_id=party.party_id).first()
                if existing:
                    await interaction.response.send_message("Your party is already registered.", ephemeral=True)
                    return
                candidate = Candidate(election_id=election_id, user_id=interaction.user.id, party_id=party.party_id, is_party=True)
                session.add(candidate)
                session.commit()
                await interaction.response.send_message(f"Party **{party.name}** registered as a candidate.")
            else:
                existing = session.query(Candidate).filter_by(election_id=election_id, user_id=interaction.user.id).first()
                if existing:
                    await interaction.response.send_message("You are already registered.", ephemeral=True)
                    return
                candidate = Candidate(election_id=election_id, user_id=interaction.user.id, party_id=None, is_party=False)
                session.add(candidate)
                session.commit()
                await interaction.response.send_message("Registered as an independent candidate.")
        finally:
            session.close()

    
    @election_group.command(name="candidatws", description="List all candidates for an election.")
    @app_commands.describe(election_id="ID of the election.")
    async def candidates(self, interaction: Interaction, election_id: int):
        session = get_session()
        try:
            election = session.get(Election, election_id)
            if not election:
                await interaction.response.send_message("Election not found.", ephemeral=True)
                return
            candidates = session.query(Candidate).filter_by(election_id=election_id).all()
            if not candidates:
                await interaction.response.send_message("No candidates yet.", ephemeral=True)
                return
            embed = Embed(title=f"Candidates — {election.type.capitalize()} Election", color=Color.blue())
            for i in candidates:
                if i.is_party:
                    party = session.get(Party, c.party_id)
                    name = party.name if party else f"Party {i.party_id}"
                else:
                    member = interaction.guild.get_member(i.user_id)
                    name = member.display_name if member else str(i.user_id)
                embed.add_field(name=name, value="Independent" if not i.is_party else "Party", inline=False)
            await interaction.response.send_message(embed=embed)
        finally:
            session.close()


    @election_group.command(name="vote", description="Open the voting panel.")
    @app_commands.describe(election_id="ID of the election.")
    async def vote(self, interaction: Interaction, election_id: int):
        session = get_session()
        try:
            election = session.get(Election, election_id)
            if not election or election.status != "ongoing":
                await interaction.response.send_message("Voting is not open yet.", ephemeral=True)
                return
            candidates = session.query(Candidate).filter_by(election_id=election_id).all()
            if not candidates:
                await interaction.response.send_message("No candidates registered yet.", ephemeral=True)
                return
            buttons = []
            for i in candidates:
                if i.party_id:
                    party = session.get(Party, i.party_id)
                    label = party.name if party else f"Party {i.party_id}"
                else:
                    member = interaction.guild.get_member(i.user_id)
                    label = member.display_name if member else str(i.user_id)
                buttons.append((i, label))
            view = VoteView(election_id=election_id, candidate=buttons)
            embed = Embed(title="Cast Your Vote", description="Click a button to vote. You can change your vote anytime before the election ends.", color=Color.green())
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        finally:
            session.close()


    @election_group.command(name="results", description="View results of an election.")
    @app_commands.describe(election_id="ID of the election.")
    async def results(self, interaction: Interaction, election_id: int):
        session = get_session()
        try:
            election = session.get(Election, election_id)
            if not election:
                await interaction.response.send_message("Election not found.", ephemeral=True)
                return
            candidates = session.query(Candidate).filter_by(election_id=election_id).all()
            results = []
            for i in candidates:
                count = session.query(Vote).filter_by(election_id=election_id, candidate_id=i.candidate_id).count()
                results.append((i, count))
            results.sort(key=lambda x: x[1], reverse=True)
            embed = Embed(title=f"Results — {election.type.capitalize()} Election", color=Color.gold())
            for i, (c, votes) in enumerate(results, 1):
                if c.is_party:
                    party = session.get(Party, c.party_id)
                    name = party.name if party else f"Party {c.party_id}"
                else:
                    member = interaction.guild.get_member(c.user_id)
                    name = member.display_name if member else str(c.user_id)
                embed.add_field(name=f"{i}. {name}", value=f"{votes} votes", inline=False)
            await interaction.response.send_message(embed=embed)
        finally:
            session.close()


    @election_group.command(name="start", description="Start voting for an election.")
    @app_commands.describe(election_id="ID of the election.")
    async def start(self, interaction: Interaction, election_id: int):
        if not is_cec(interaction):
            await interaction.response.send_message("Only CEC or President can start elections.", ephemeral=True)
            return
        session = get_session()
        try:
            election = session.get(Election, election_id)
            if not election:
                await interaction.response.send_message("Election not found.", ephemeral=True)
                return
            if election.status != "registration":
                await interaction.response.send_message("Election is not in registration phase.", ephemeral=True)
                return
            election.status = "ongoing"
            session.commit()
            await interaction.response.send_message(f"Election `{election_id}` is now open for voting. Ends: <t:{int(election.end_date.timestamp())}:R>.")
        finally:
            session.close()


    party_group = app_commands.Group(name="party", description="Party-related commands.")


    @party_group.command(name="invite", description="Invite a member to your party.")
    @app_commands.describe(member="Member to invite.")
    async def invite(self, interaction: Interaction, member: Member):
        session = get_session()
        try:
            party = session.query(Party).filter_by(leader_id=interaction.user.id).first()
            if not party:
                await interaction.response.send_message("You don't lead a party.", ephemeral=True)
                return
            existing = session.query(PartyMember).filter_by(user_id=member.id).first()
            if existing:
                await interaction.response.send_message(f"{member.display_name} is already in a party.", ephemeral=True)
                return
            view = InviteView(party_id=party.party_id, invitee_id=member.id)
            await interaction.response.send_message(f"{member.mention}, you have been invited to join **{party.name}**.", view=view)
        finally:
            session.close()


    @party_group.command(name="create", description="Create a party.")
    @app_commands.describe(name="Name of your party.")
    async def create(self, interaction: Interaction, name: str):
        if not has_role(interaction, LEVEL_30):
            await interaction.response.send_message("You need to be Level 30 to form a party.", ephemeral=True)
            return
        session = get_session()
        try:
            existing = session.query(Party).filter_by(leader_id=interaction.user.id).first()
            if existing:
                await interaction.response.send_message("You already lead a party.", ephemeral=True)
                return
            in_party = session.query(PartyMember).filter_by(user_id=interaction.user.id).first()
            if in_party:
                await interaction.response.send_message("You must leave your current party before creating one.", ephemeral=True)
                return
            party = Party(name=name, leader_id=interaction.user.id)
            session.add(party)
            session.flush()
            session.add(PartyMember(party_id=party.party_id, user_id=interaction.user.id))
            session.commit()
            await interaction.response.send_message(f"Party **{name}** created.")
        finally:
            session.close()


    @party_group.command(name="leave", description="Leave your current party.")
    async def party_leave(self, interaction: Interaction):
        session = get_session()
        try:
            member = session.query(PartyMember).filter_by(user_id=interaction.user.id).first()
            if not member:
                await interaction.response.send_message("You are not in a party.", ephemeral=True)
                return
            party = session.get(Party, member.party_id)
            if party and party.leader_id == interaction.user.id:
                await interaction.response.send_message("You can't leave a party you lead. Disband it instead.", ephemeral=True)
                return
            session.delete(member)
            session.commit()
            await interaction.response.send_message("You have left your party.")
        finally:
            session.close()


    @party_group.command(name="info", description="View party details.")
    @app_commands.describe(party_id="ID of the party.")
    async def party_info(self, interaction: Interaction, party_id: int):
        session = get_session()
        try:
            party = session.get(Party, party_id)
            if not party:
                await interaction.response.send_message("Party not found.", ephemeral=True)
                return
            members = session.query(PartyMember).filter_by(party_id=party_id).all()
            leader = interaction.guild.get_member(party.leader_id)
            embed = Embed(title=f"Party — {party.name}", color=Color.blue())
            embed.add_field(name="Leader:", value=leader.display_name if leader else str(party.leader_id), inline=False)
            member_names = []
            for i in members:
                member = interaction.guild.get_member(i.user_id)
                member_names.append(member.display_name if member else str(i.user_id))
            embed.add_field(name="Members:", value="\n".join(member_names) if member_names else "None", inline=False)
            await interaction.response.send_message(embed=embed)
        finally:
            session.close()


    @app_commands.command(name="vacate", description="Mark a seat as vacant and trigger a by-election.")
    @app_commands.describe(member="The minister who vacated.", end_date="End date for by-election in DD-MM-YYYY format.")
    async def vacate(self, interaction: Interaction, member: Member, end_date: str):
        if not is_cec(interaction):
            await interaction.response.send_message("Only CEC or President can use this command.", ephemeral=True)
            return
        try:
            date = datetime.strptime(end_date, "%d-%m-%Y").replace(tzinfo=timezone.utc)
        except ValueError:
            await interaction.response.send_message("Invalid date format. Use DD-MM-YYYY.", ephemeral=True)
            return
        if date <= utcnow():
            await interaction.response.send_message("End date must be in the future.", ephemeral=True)
            return
        session = get_session()
        try:
            election = Election(type="byelection", status="ongoing", end_date=date, created_by=interaction.user.id, seats=1)
            session.add(election)
            session.commit()
            await interaction.response.send_message(f"{member.mention}'s seat has been vacated. By-election created. ID: `{election.election_id}`. Ends: <t:{int(date.timestamp())}:R>.")
        finally:
            session.close()


async def setup(bot):
    await bot.add_cog(Elections(bot))

