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
    final_summary = summarise_text(" ".join(summaries))
    embed = Embed(title="Here is your Summary!",
                  description=final_summary[:5000],
                  color=Color.random())
    await interaction.followup.send(embed=embed)


