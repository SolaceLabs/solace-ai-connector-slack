import os
import discord
from discord.ext import commands
from discord.ui import Button, View

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

async def thumbsup_callback(interaction: discord.Interaction):
    await interaction.response.send_message("You clicked thumbs up!", ephemeral=True)

async def thumbsdown_callback(interaction: discord.Interaction):
    await interaction.response.send_message("You clicked thumbs down!", ephemeral=True)


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if client.user.mentioned_in(message):
        thumbsup_button = Button(label="👍", style=discord.ButtonStyle.green)
        thumbsdown_button = Button(label="👎", style=discord.ButtonStyle.red)
        
        thumbsup_button.callback = thumbsup_callback
        thumbsdown_button.callback = thumbsdown_callback
        view = View()
        view.add_item(thumbsup_button)
        view.add_item(thumbsdown_button)
        
        # Send the message with the buttons
        await message.channel.send("test", view=view)

client.run(os.getenv('DISCORD_TOKEN'))