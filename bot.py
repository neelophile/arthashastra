from discord import Intents, Object, Interaction, DMChannel, utils, Embed, Color
from dotenv import load_dotenv
from os import getenv
from discord.ext import commands
from db.database import init_db, get_session
from json import load
from random import choice
from cogs.employment import has_role


load_dotenv()
guild = Object(id=int(getenv("GUILD")))
intents = Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='.', intents=intents)
cogs = ['cogs.employment', 'cogs.config', 'cogs.bank', 'cogs.elections', 'cogs.sir']
with open("tips.json") as f:
    tips = load(f)


async def setup_hook():
    init_db()
    for i in cogs:
        await bot.load_extension(i)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}.")


@bot.event
async def on_app_command_completion(interaction: Interaction, command):
    tip = choice(tips)
    try:
        await interaction.followup.send(f"💡 **Did you know?** {tip}")
    except Exception:
        pass


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.name == "report":
        session = get_session()
        try:
            record = session.query(SIRRecord).filter_by(user_id=message.author.id, status="pinged").first()
            if record:
                record.status = "responded"
                session.commit()
                await message.add_reaction("✅")
        finally:
            session.close()
    if not isinstance(message.channel, DMChannel):
        return
    await bot.process_commands(message)


@bot.tree.command(name="hello", description="Replies back.")
async def hello(interaction: Interaction):
    await interaction.response.send_message(f"Hello, {interaction.user.mention}!")


@bot.tree.command(name="ping", description="Provides with the latency.")
async def ping(interaction: Interaction):
    await interaction.response.send_message(f"Pong! Response with {round(bot.latency * 1000)}ms")


@bot.tree.command(name="reloadtips", description="Reload pro tips to amend changes.")
async def reloadtips(interaction: Interaction):
    if not has_role(interaction, "President"):
        await interaction.response.send_message("Admins only.", ephemeral=True)
        return
    global tips
    with open("tips.json") as f:
        tips = load(f)
    await interaction.response.send_message("Tips reloaded.", ephemeral=True)


bot.setup_hook = setup_hook
bot.run(getenv("TOKEN"))
