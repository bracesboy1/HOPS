#commands.py
import discord
import random
import sqlite3 # Imported for database structure
from player_cards import PlayerCard
from PIL import Image # Imported for card image compilation
import io
import asyncio # Imported for time expiration
import time  # Imported for retry logic

DATABASE_NAME = 'user_cards1.db'
CARDS_PER_PAGE = 10

def connect_db(): # Connect to SQL database
    retries = 5
    while retries:
        try:
            return sqlite3.connect(DATABASE_NAME, timeout=10)
        except sqlite3.OperationalError:
            retries -= 1
            time.sleep(1)  # Wait for 1 second before retrying
    raise sqlite3.OperationalError("Database is locked and all retries failed.")

def add_user(discord_id): # Adds user to database
    with connect_db() as conn:  # Use the connect_db()
        c = conn.cursor()

        # Create users table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            discord_id TEXT UNIQUE
        )''')

        # Insert user if they don't already exist
        c.execute('INSERT OR IGNORE INTO users (discord_id) VALUES (?)', (discord_id,))

def get_user_id(discord_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute('SELECT id FROM users WHERE discord_id = ?', (discord_id,))
    user_id = c.fetchone()
    conn.close()
    return user_id[0] if user_id else None

def add_card_to_user(discord_id, player_name, season_year): # Adds specific card instance to user
    user_id = get_user_id(discord_id)

    if user_id is None:
        return "User not found."

    conn = connect_db()
    c = conn.cursor()

    # Create cards table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY,
        player_name TEXT,
        season_year TEXT
    )''')

    # Create user_cards table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS user_cards1 (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        card_id INTEGER,
        instance_number INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (card_id) REFERENCES cards (id),
        UNIQUE (user_id, card_id, instance_number)  -- Prevent duplicate instances for a user
    )''')

    # Insert card if it doesn't already exist
    c.execute('INSERT OR IGNORE INTO cards (player_name, season_year) VALUES (?, ?)', (player_name, season_year))
    conn.commit()

    # Get the card_id
    c.execute('SELECT id FROM cards WHERE player_name = ? AND season_year = ?', (player_name, season_year))
    card_id = c.fetchone()[0]

    # Find the next instance number for this specific card across all users
    c.execute('SELECT COUNT(*) FROM user_cards1 WHERE card_id = ?', (card_id,))
    instance_number = c.fetchone()[0] + 1  # Set to current count plus one for this card

    # Insert the user-card relationship
    c.execute('INSERT INTO user_cards1 (user_id, card_id, instance_number) VALUES (?, ?, ?)',
              (user_id, card_id, instance_number))
    conn.commit()
    conn.close()

    return f"You claimed {player_name}, {season_year} #{instance_number}!"

def pick_random_cards(num_cards=3):
    all_cards = PlayerCard.get_cards()
    if len(all_cards) < num_cards:
        return []

    return random.sample(all_cards, num_cards)

def compile_images(cards): # Creates image of three cards
    images = [card.image for card in cards if card.image is not None]

    if not images:
        print("No images found for the selected cards.")
        return None

    total_width = sum(image.width for image in images)
    max_height = max(image.height for image in images)

    # Create a transparent background for the compiled image
    compiled_image = Image.new("RGBA", (total_width, max_height), (0, 0, 0, 0))

    x_offset = 0
    for img in images:
        compiled_image.paste(img, (x_offset, 0), img if img.mode == 'RGBA' else None)
        x_offset += img.width

    # Save to a BytesIO object instead of a file
    img_byte_arr = io.BytesIO()
    compiled_image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)  # Move to the beginning of the BytesIO object

    return img_byte_arr

# To store cooldown information and expiration timestamps for card drops
user_cooldowns = {}
card_drop_expiration_times = {}

async def send_player_cards(channel, user_id, bot):  # Sends cards to specified channel
    current_time = time.time()

    # Check if user is in cooldown period
    if user_id in user_cooldowns:
        time_since_last_drop = current_time - user_cooldowns[user_id]
        cooldown_remaining = 30 * 60 - time_since_last_drop
        if cooldown_remaining > 0:
            await channel.send(f"You must wait {int(cooldown_remaining // 60)} minutes "
                               f"and {int(cooldown_remaining % 60)} seconds before dropping cards again.")
            return
    user_cooldowns[user_id] = current_time  # Update the cooldown timestamp

    selected_cards = pick_random_cards(3)
    if not selected_cards:
        await channel.send("Not enough cards to choose from.")
        return

    # Compile images
    compiled_image = compile_images(selected_cards)
    message = await channel.send(file=discord.File(compiled_image, filename='compiled_player_cards.png'))

    # Set expiration time for card drop
    card_drop_expiration_times[message.id] = current_time + 60  # Expires after 1 minute

    # Add reactions to the message
    emoji_list = ['1️⃣', '2️⃣', '3️⃣']  # Emojis for selection
    for emoji in emoji_list:
        await message.add_reaction(emoji)

    # Wait for a reaction from the user
    def check(reaction, user):
        # Check expiration before allowing claim
        if time.time() > card_drop_expiration_times.get(message.id, 0):
            return False
        return user != message.guild.me and str(reaction.emoji) in emoji_list and reaction.message.id == message.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await channel.send("The card drop has expired!")
    else:
        if time.time() > card_drop_expiration_times[message.id]:  # Re-check expiration
            await channel.send("The card drop has expired!")
        else:
            chosen_card_index = emoji_list.index(str(reaction.emoji))
            chosen_card = selected_cards[chosen_card_index]
            response = add_card_to_user(user.id, chosen_card.player_name, chosen_card.season_year)
            await channel.send(response)

    # Clean up expired card drop data
    card_drop_expiration_times.pop(message.id, None)

async def view_collection(channel, discord_id, bot):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()

    # Fetch the user's cards and their instance numbers
    c.execute('''SELECT cards.player_name, cards.season_year, user_cards1.instance_number
                 FROM user_cards1
                 JOIN users ON user_cards1.user_id = users.id
                 JOIN cards ON user_cards1.card_id = cards.id
                 WHERE users.discord_id = ?''', (discord_id,))

    user_cards1 = c.fetchall()
    conn.close()

    if not user_cards1:
        await channel.send("You don't have any cards in your collection.")
        return

    # Define pagination variables
    total_cards = len(user_cards1)
    total_pages = (total_cards + CARDS_PER_PAGE - 1) // CARDS_PER_PAGE
    current_page = 0

    def generate_page_content(page_index):
        start = page_index * CARDS_PER_PAGE
        end = start + CARDS_PER_PAGE
        cards_on_page = user_cards1[start:end]

        content = f"**Your Collection - Page {page_index + 1}/{total_pages}:**\n"
        for idx, (player_name, season_year, instance_number) in enumerate(cards_on_page, start=start + 1):
            content += f"{idx}. {player_name}, {season_year} #{instance_number}\n"

        return content

    # Send the first page of the collection
    message = await channel.send(generate_page_content(current_page))

    # Add reaction buttons for pagination if more than one page exists
    if total_pages > 1:
        await message.add_reaction("◀️")
        await message.add_reaction("▶️")

        # Reaction check function
        def check(reaction, user):
            return (user != bot.user and
                    str(reaction.emoji) in ["◀️", "▶️"] and
                    reaction.message.id == message.id)

        while True:
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
                await message.remove_reaction(reaction.emoji, user)

                # Update current_page based on the reaction
                if reaction.emoji == "▶️" and current_page < total_pages - 1:
                    current_page += 1
                elif reaction.emoji == "◀️" and current_page > 0:
                    current_page -= 1

                # Edit the message to show the new page
                await message.edit(content=generate_page_content(current_page))

            except asyncio.TimeoutError:
                await message.clear_reactions()
                break
            except Exception as e:
                print(f"An unexpected error occurred: {e}")

async def send_card_stats(channel, user_discord_id, player_name):
    try:
        if player_name:
            print("Searching for player name:", player_name)

            # Log contents of PlayerCard.cards for debugging
            print("Contents of PlayerCard.cards:", [card.player_name for card in PlayerCard.cards])

            # Retrieve specific card by name
            card = next(
                (card for card in PlayerCard.cards if card.player_name.lower().strip() == player_name.lower().strip()),
                None
            )

            # Print debug information if card is not found
            if not card:
                print("No matching card found for:", player_name)
        else:
            card = get_last_claimed_card(user_discord_id)

        if isinstance(card, PlayerCard):
            stats_message = f"Stats for {card.player_name}: {card.stats}"
            await channel.send(stats_message)

            if card.image is not None:
                img_byte_arr = io.BytesIO()
                card.image.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                await channel.send(file=discord.File(img_byte_arr, filename='card_image.png'))
            else:
                await channel.send("No image available for this card.")
        else:
            await channel.send("Player card not found.")
    except Exception as e:
        print(f"Error sending stats: {e}")
        await channel.send("An error occurred while retrieving stats.")

def get_last_claimed_card(user_discord_id):
    conn = sqlite3.connect('user_cards1.db')
    cursor = conn.cursor()

    try:
        # Step 1: Find the internal user ID using the discord_id
        cursor.execute("SELECT id FROM users WHERE discord_id = ?", (user_discord_id,))
        user_record = cursor.fetchone()

        if user_record is None:
            print(f"No internal user ID found for Discord ID {user_discord_id}")
            return None

        internal_user_id = user_record[0]
        print(f"Found internal user ID: {internal_user_id} for Discord ID {user_discord_id}")

        # Step 2: Find the most recent card claimed by this user (if any)
        cursor.execute("""
            SELECT card_id 
            FROM user_cards1 
            WHERE user_id = ? 
            ORDER BY rowid DESC 
            LIMIT 1
        """, (internal_user_id,))
        card_record = cursor.fetchone()

        if card_record is None:
            print(f"No cards found for internal user ID {internal_user_id}")
            return None

        last_card_id = card_record[0]
        print(f"Found last claimed card ID: {last_card_id} for internal user ID {internal_user_id}")

        # Step 3: Retrieve player name associated with the found card ID
        cursor.execute("SELECT player_name FROM cards WHERE id = ?", (last_card_id,))
        card_info = cursor.fetchone()

        if card_info is None:
            print(f"No card data found for card ID {last_card_id}")
            return None

        player_name = card_info[0]
        print(f"Found player name: {player_name} for card ID {last_card_id}")

        # Step 4: Locate the existing PlayerCard instance by player_name in PlayerCard.cards
        card = next((card for card in PlayerCard.cards if card.player_name.lower() == player_name.lower()), None)

        if card is None:
            print(f"No matching PlayerCard instance found for player name: {player_name}")
            return None

        return card

    except Exception as e:
        print(f"Error in get_last_claimed_card: {e}")
        return None
    finally:
        conn.close()


                await message.edit(content=generate_page_content(current_page))

            except asyncio.TimeoutError:
                break  # Stop if the user takes too long
