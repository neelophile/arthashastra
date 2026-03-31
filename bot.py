from discord import Intents, Object, Interaction
from dotenv import load_dotenv
from os import getenv
from discord.ext import commands


load_dotenv()
guild = Object(id=int(getenv("GUILD")))
intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}.")


@bot.tree.command(name="hello", description="Replies back.")
async def hello(interaction: Interaction):
    await interaction.response.send_message(f"Hello, {interaction.user.mention}!")


@bot.tree.command(name="ping", description="Provides with the latency.")
async def ping(interaction: Interaction):
    await interaction.response.send_message(f"Pong! Response with {round(bot.latency * 1000)}ms")


bot.run(getenv("TOKEN"))
