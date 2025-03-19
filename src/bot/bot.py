import os
import discord
from discord import Intents, Client, Interaction, Message, ChannelType, ButtonStyle, InteractionType, app_commands
from discord.ui import Button, View
from discord.ext import commands

client = commands.Bot(command_prefix="!", intents=discord.Intents.all())

def trunc(text: str, max: int = 20):
  return text[:max] if len(text) > max else text

@client.event
async def on_ready():
  print(f'We have logged in as {client.user}')

async def thumbsup_callback(interaction: Interaction):
  await interaction.response.send_message("You clicked thumbs up!", ephemeral=True)

async def thumbsdown_callback(interaction: Interaction):
  await interaction.response.send_message("You clicked thumbs down!", ephemeral=True)

@client.event
async def on_interaction(interaction: Interaction):
  if interaction.type != InteractionType.component:
    return

@client.event
async def on_message(message: Message):
  if message.author == client.user or not client.user:
    return

  if not client.user.mentioned_in(message):
    return

  thumbsup_button = Button(label="👍", style=ButtonStyle.green)
  thumbsdown_button = Button(label="👎", style=ButtonStyle.red)

  thumbsup_button.callback = thumbsup_callback
  thumbsdown_button.callback = thumbsdown_callback

  view = View()
  view.add_item(thumbsup_button)
  view.add_item(thumbsdown_button)

  for attachment in message.attachments:
    attachment.url

  if message.channel.type in [ChannelType.public_thread, ChannelType.private_thread]:
    await message.reply("hello world", view=view)
  else:
    thread = await message.create_thread(name=trunc(message.clean_content))
    await thread.send("hello world", view=view)

@client.event
async def on_ready():
  try:
    s = await client.tree.sync()
    print(f"Synced {len(s)} commands")
  except Exception as e:
    print(e)


@client.tree.command(name = "help")
async def test(interaction: discord.Interaction):
  await interaction.response.send_message(f"""
Hi {interaction.user.mention}!

I'm the Solace AI Chatbot, designed to assist Solace employees with various tasks and information needs. 

## What I can do:
* Answer general questions and provide assistance
* Search Solace customer documentation for product information
* Access Confluence pages for internal documentation
* Retrieve employee information (schedules, contact details, org charts)
* Work with Jira issues and RT support tickets
* Generate diagrams, charts, and reports
* Process and analyze images
* Search the web for current information

I can help with both general inquiries and Solace-specific questions by leveraging specialized agents to access the right information sources. Just let me know what you need assistance with!""", ephemeral=True)


client.run(os.getenv('DISCORD_TOKEN') or exit(-123))
