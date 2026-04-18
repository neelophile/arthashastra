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


def summarise_text(text):
    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Summarize this Discord chat like a chill server mod.\n"
                    "- Understand Hinglish, slang, memes\n"
                    "- Keep it casual, not formal\n"
                    "- Highlight important and funny moments\n"
                )
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "max_tokens": 200,
        "temperature": 0.7
    }
    try:
        response = post(getenv("LLAMA_URL"), json=payload, timeout=60)
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {str(e)}"


def chunk_text(text, size=1500):
    return [text[i:i+size] for i in range(0, len(text), size)]


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
            messages.append(f"[{i.author.display_name}] {i.content}")
    if not messages:
        await interaction.followup.send("No messages found", ephemeral=True)
        return
    messages.reverse()
    transcript = "\n".join(messages)
    chunks = chunk_text(transcript)
    summaries = []
    for chunk in chunks:
        summaries.append(summarise_text(chunk))
    final_summary = summarize_text(" ".join(summaries))
    embed = Embed(title="Here is your Summary!",
                  description=final_summary[:4000],
                  color=Color.random())
    await interaction.followup.send(embed=embed)


bot.run(getenv("TOKEN"))
