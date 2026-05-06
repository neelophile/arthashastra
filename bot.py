from discord import Intents, Object, Interaction, Embed, Color
from dotenv import load_dotenv
from os import getenv
from discord.ext import commands
from db.database import init_db
from requests import post


load_dotenv()
guild = Object(id=int(getenv("GUILD")))
intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='.', intents=intents)
cogs = ['cogs.employment']


@bot.event
async def on_ready():
    init_db()
    for i in cogs:
        await bot.load_extension(i)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print(f"Logged in as {bot.user}.")


@bot.tree.command(name="hello", description="Replies back.")
async def hello(interaction: Interaction):
    await interaction.response.send_message(f"Hello, {interaction.user.mention}!")


@bot.tree.command(name="ping", description="Provides with the latency.")
async def ping(interaction: Interaction):
    await interaction.response.send_message(f"Pong! Response with {round(bot.latency * 1000)}ms")


bot.run(getenv("TOKEN"))
