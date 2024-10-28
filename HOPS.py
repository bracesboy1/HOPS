#HOPS.py
import discord
import random
import sqlite3
from player_cards import PlayerCard, initialize_player_cards
from commands import send_player_cards, view_collection, add_user, send_card_stats
import asyncio

initialize_player_cards()

intents = discord.Intents.default()
intents.message_content = True  # Enable message-related events
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user: # Prevent the bot from replying to itself
        return


    if message.guild: # Check if the bot can access message content in the server
        print(f"Message in server: {message.guild.name} - {message.channel.name} - {message.content}")
    else:
        print(f"Message in DM: {message.content}")

    if message.content.startswith('!cards'):
        add_user(message.author.id)  # Ensure the user is added to the database
        await message.channel.send('Dropping three cards!')
        await send_player_cards(message.channel, message.author.id,bot)

    if message.content.startswith('!collection'):
        await view_collection(message.channel, message.author.id,bot)

    if message.content.startswith('!stats'):
        player_name = None
        parts = message.content.split(' ', 1)
        if len(parts) > 1:
            player_name = parts[1]  # The name of the player
        await send_card_stats(message.channel, message.author.id, player_name)

bot.run('bot token replaced')

