from discord import Intents, Object, Interaction, Embed, Color
from dotenv import load_dotenv
from os import getenv
from discord.ext import commands
from db.database import init_db
from google import genai


load_dotenv()
guild = Object(id=int(getenv("GUILD")))
intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='.', intents=intents)
cogs = ['cogs.employment']
client = genai.Client(api_key=getenv('GEMINI_API_KEY'))


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


@bot.tree.command(name="summarise", description="Summarise whatever has happened in chat")
async def summarise(interaction: Interaction, count: int):
    if count < 1 or count > 500:
        await interaction.response.send_message("Thoda aukat mein yaar!!", ephemeral=True)
        return
    await interaction.response.defer()
    messages = []
    async for i in interaction.channel.history(limit=count):
        if not i.author.bot:
            messages.append(f"{i.author.display_name}: {i.content}")
    if not messages:
        await interaction.followup.send("No messages found", ephemeral=True)
        return
    messages.reverse()
    transcript = "\n".join(messages)
    response = client.models.generate_content(model="gemini-3.1-flash-lite-preview",
                                              contents=f"Summarise the following Discord chat concisely:\n\n{transcript}")
    embed = Embed(title="Here is your Summary!",
                  description=response.text,
                  color=Color.random())
    await interaction.followup.send(embed=embed)


bot.run(getenv("TOKEN"))
