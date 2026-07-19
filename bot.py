from discord import Intents, Object, Interaction, DMChannel, utils, Embed, Color
from dotenv import load_dotenv
from os import getenv
from discord.ext import commands
from db.database import init_db, get_session
from db.models import FeedbackRequest


load_dotenv()
guild = Object(id=int(getenv("GUILD")))
intents = Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='.', intents=intents)
cogs = ['cogs.employment', 'cogs.config', 'cogs.bank', 'cogs.elections']


async def setup_hook():
    init_db()
    for i in cogs:
        await bot.load_extension(i)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}.")


@bot.tree.command(name="hello", description="Replies back.")
async def hello(interaction: Interaction):
    await interaction.response.send_message(f"Hello, {interaction.user.mention}!")


@bot.tree.command(name="ping", description="Provides with the latency.")
async def ping(interaction: Interaction):
    await interaction.response.send_message(f"Pong! Response with {round(bot.latency * 1000)}ms")


@bot.event
async def on_member_remove(member):
    try:
        await member.send(f"Hey {member.display_name}, sorry to see you go from **Sarkari Adda**!\n\nWe'd love to hear your feedback. Just reply to this message and we'll pass it along. Please note that the feedback is expected in a single message.")
        session = get_session()
        try:
            session.add(FeedbackRequest(user_id=member.id))
            session.commit()
        finally:
            session.close()
    except Exception as e:
        print(f"Failed to DM {member.display_name} : {e}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if not isinstance(message.channel, DMChannel):
        return
    session = get_session()
    try:
        request = session.query(FeedbackRequest).filter_by(user_id=message.author.id).first()
        if not request:
            await bot.process_commands(message)
            return
        guild = bot.guilds[0]
        channel = utils.get(guild.text_channels, name="immigration-office")
        if channel:
            embed = Embed(title="Member Feedback", color=Color.random())
            embed.add_field(name="User:", value=f"{message.author.name} ({message.author.id})", inline=False)
            embed.add_field(name="Feedback:", value=message.content, inline=False)
            await channel.send(embed=embed)
        session.delete(request)
        session.commit()
        await message.reply("Thank you for your feedback! It has been forwarded to the team.")
    finally:
        session.close()


bot.setup_hook = setup_hook
bot.run(getenv("TOKEN"))
