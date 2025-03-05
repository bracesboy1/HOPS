#commands.py
import discord, random, sqlite3, io, asyncio, time, string
from player_cards import PlayerCard
from PIL import Image

DATABASE_NAME = 'HOPS_prototype1.db'
CARDS_PER_PAGE = 10


def connect_db():  # Connect to SQL database
    retries = 5
    while retries:
        try:
            return sqlite3.connect(DATABASE_NAME, timeout=10)
        except sqlite3.OperationalError:
            retries -= 1
            time.sleep(1)  # Wait for 1 second before retrying
    raise sqlite3.OperationalError("Database is locked and all retries failed.")


def add_user(discord_id):  # Adds user to database
    with connect_db() as conn:
        c = conn.cursor()

        # Create users table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            discord_id TEXT UNIQUE
        )''')

        # Insert user if they don't already exist
        c.execute('INSERT OR IGNORE INTO users (discord_id) VALUES (?)', (discord_id,))


def user_owns_card(discord_id, player_name):
    # Check if the user owns the specified player card by cross-referencing tables.
    conn = connect_db()
    try:
        c = conn.cursor()

        # Case-insensitive search for the card in the 'cards' table
        c.execute('SELECT card_id FROM cards WHERE LOWER(player_name) = LOWER(?)', (player_name,))
        card_row = c.fetchone()
        if not card_row:
            return False, "This card does not exist."
        card_id = card_row[0]

        # Find the internal user id based on the discord_id
        c.execute('SELECT user_id FROM users WHERE discord_id = ?', (discord_id,))
        user_row = c.fetchone()
        if not user_row:
            return False, "User not found. Please register first."
        user_id = user_row[0]

        # Check if the user owns the card in 'user_cards'
        c.execute('SELECT * FROM user_cards WHERE user_id = ? AND card_id = ?', (user_id, card_id))
        if not c.fetchone():
            return False, "You don't own this card."

        return True, "Card found in your collection."

    finally:
        conn.close()


def initialize_cards_table():
    # Ensure the cards table exists with the correct structure.

    with connect_db() as conn:
        c = conn.cursor()
        # Create table if it doesn't exist
        c.execute(''' 
            CREATE TABLE IF NOT EXISTS cards (
                card_id INTEGER PRIMARY KEY,
                player_name TEXT NOT NULL,
                position INTEGER NOT NULL,
                season_year INTEGER NOT NULL,
                stats TEXT NOT NULL,
                offensive_rating REAL NOT NULL,
                defensive_rating REAL NOT NULL,
                attributes TEXT NOT NULL  -- New attribute for storing player-specific attributes
            )
        ''')
        conn.commit()


def sync_player_cards_to_db():
    #Sync all PlayerCard instances to the database. Ensures all cards in PlayerCard are inserted or updated in the cards table.

    with connect_db() as conn:
        c = conn.cursor()

        for card in PlayerCard.cards:
            # Prepare data for insertion or update
            data = (
                card.card_id,  # card_id
                card.player_name,  # player_name
                card.position,  # position
                card.season_year,  # season_year
                str(card.stats),  # stats as a string
                card.offensive_rating,  # offensive_rating
                card.defensive_rating,  # defensive_rating
                str(card.attributes)  # attributes as a string
            )

            # Insert or update the card
            c.execute(''' 
                INSERT INTO cards (card_id, player_name, position, season_year, stats, offensive_rating, defensive_rating, attributes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(card_id) DO UPDATE SET
                    player_name = excluded.player_name,
                    position = excluded.position,
                    season_year = excluded.season_year,
                    stats = excluded.stats,
                    offensive_rating = excluded.offensive_rating,
                    defensive_rating = excluded.defensive_rating,
                    attributes = excluded.attributes
            ''', data)

        conn.commit()

def get_user_id(discord_id):
    # Get user_id from discord_id.
    conn = connect_db()
    c = conn.cursor()
    c.execute('SELECT user_id FROM users WHERE discord_id = ?', (discord_id,))
    user_id = c.fetchone()
    conn.close()
    return user_id[0] if user_id else None

def get_random_condition():
    # Returns a random condition based on predefined probabilities. This will affect gameplay later on
    conditions = ['Healthy', 'Injury Watch', 'Injured', 'Peak Condition']
    probabilities = [0.7, 0.15, 0.1, 0.05]
    return random.choices(conditions, probabilities)[0]

def generate_card_id():
    # Generate a unique six-character alphanumeric ID for the card.
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

def generate_card_instance_id():
    # Generates a random 6-character alphanumeric string for the instance ID.
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))


def add_card_to_user(discord_id, player_name, season_year):
    # Adds card to user's collection in the database

    with connect_db() as conn:
        c = conn.cursor()

        # Get the internal user ID using the Discord ID
        c.execute("SELECT user_id, court_cash FROM users WHERE discord_id = ?", (discord_id,))
        user_row = c.fetchone()

        if not user_row:
            return "User not found in the database."

        user_id, current_cash = user_row

        # Validate the card exists in the cards table and fetch additional data
        c.execute(
            """
            SELECT card_id, offensive_rating, defensive_rating, attributes 
            FROM cards 
            WHERE LOWER(player_name) = ? AND season_year = ?
            """,
            (player_name.lower(), season_year),
        )
        card_row = c.fetchone()

        if not card_row:
            return f"Card for {player_name} ({season_year}) not found."

        card_id = card_row[0]  # Generic card ID from the cards table
        offensive_rating = card_row[1]
        defensive_rating = card_row[2]
        attributes = card_row[3]

        # Determine the next instance_number for this card_id (GLOBAL, across all users)
        c.execute(
            """
            SELECT MAX(instance_number) FROM user_cards
            WHERE card_id = ?
            """,
            (card_id,),
        )
        max_instance_number = c.fetchone()[0]
        next_instance_number = 1 if max_instance_number is None else max_instance_number + 1

        # Generate a unique alphanumeric instance ID
        instance_id = generate_card_instance_id()

        # Assign a random condition to the card
        condition_probabilities = {"Injured": 0.1, "Injury Watch": 0.15, "Healthy": 0.7, "Peak Condition": 0.05}
        condition = random.choices(
            list(condition_probabilities.keys()), weights=list(condition_probabilities.values()), k=1
        )[0]

        # Insert the new card instance into the user_cards table
        try:
            c.execute(
                """
                INSERT INTO user_cards (instance_id, user_id, card_id, instance_number, condition, offensive_rating, defensive_rating, attributes) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (instance_id, user_id, card_id, next_instance_number, condition, offensive_rating, defensive_rating,
                 attributes),
            )

            # Add $100 Court Cash to the user
            if current_cash is None:
                current_cash = 0
            new_cash_balance = current_cash + 100
            c.execute("UPDATE users SET court_cash = ? WHERE user_id = ?", (new_cash_balance, user_id))

            conn.commit()

            # Prepare condition-specific messages
            condition_messages = {
                "Injured": f"You claimed {player_name}, {season_year} #{next_instance_number}, but unfortunately, he's **Injured**! You also received **$100 Court Cash**.",
                "Injury Watch": f"You claimed {player_name}, {season_year} #{next_instance_number}, but he's on **Injury Watch**. Be cautious! You also received **$100 Court Cash**.",
                "Healthy": f"You claimed {player_name}, {season_year} #{next_instance_number}, and he's **Healthy**. Good luck! You also received **$100 Court Cash**.",
                "Peak Condition": f"You claimed {player_name}, {season_year} #{next_instance_number}, and he's in **Peak Condition**! Amazing find! You also received **$100 Court Cash**.",
            }

            return condition_messages[condition]

        except sqlite3.IntegrityError as e:
            return f"An error occurred while adding the card: {str(e)}"

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

async def send_player_cards(channel, user_id, bot):
    # Pick 3 random cards
    selected_cards = pick_random_cards(3)
    if not selected_cards:
        await channel.send("Not enough cards to choose from.")
        return

    # Compile images for the selected cards
    compiled_image = compile_images(selected_cards)
    message = await channel.send(file=discord.File(compiled_image, filename='compiled_player_cards.png'))

    # Set expiration time for the card drop
    card_drop_expiration_times[message.id] = time.time() + 60  # Expires after 1 minute

    # Add reactions to the message for card selection
    emoji_list = ['1️⃣', '2️⃣', '3️⃣']
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

    # Fetch the user's cards along with instance numbers, instance ids, and condition
    c.execute('''SELECT cards.player_name, cards.season_year, user_cards.instance_number, 
                         user_cards.instance_id AS instance_id, user_cards.condition
                  FROM user_cards
                  JOIN cards ON user_cards.card_id = cards.card_id
                  WHERE user_cards.user_id = (SELECT user_id FROM users WHERE discord_id = ?)
              ''', (discord_id,))

    user_cards = c.fetchall()
    conn.close()

    if not user_cards:
        await channel.send("You don't have any cards in your collection.")
        return

    # Define pagination variables
    total_cards = len(user_cards)
    total_pages = (total_cards + CARDS_PER_PAGE - 1) // CARDS_PER_PAGE
    current_page = 0

    def generate_page_content(page_index):
        start = page_index * CARDS_PER_PAGE
        end = start + CARDS_PER_PAGE
        cards_on_page = user_cards[start:end]

        content = f"**Your Collection - Page {page_index + 1}/{total_pages}:**\n"
        for idx, (player_name, season_year, instance_number, instance_id, condition) in enumerate(cards_on_page, start=start + 1):
            content += f"{idx}. {player_name}, {season_year} #{instance_number} (ID: {instance_id}) - Condition: {condition}\n"

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


async def send_card_stats(channel, discord_id, player_name):
    # Send a message containing the stats of a player/card
    try:
        # If player_name is provided, search for it
        if player_name:
            print(f"Searching for player name: {player_name}")

            # Log contents of PlayerCard.cards for debugging
            print("Contents of PlayerCard.cards:", [card.player_name for card in PlayerCard.cards])

            # Retrieve specific card by player_name from PlayerCard.cards
            card = next(
                (card for card in PlayerCard.cards if card.player_name.lower().strip() == player_name.lower().strip()),
                None
            )

            if not card:
                print(f"No matching card found for player: {player_name}")
        else:
            # If no player_name, get the most recently claimed card using discord_id
            card = get_last_claimed_card(discord_id)

        if isinstance(card, PlayerCard):
            # Prepare the message with stats, including offensive and defensive ratings, attributes, condition, and positions
            stats_message = (
                f"Stats for {card.player_name} ({card.stats})\n"
                f"Position: {card.position}\n"
                f"Offensive Rating: {card.offensive_rating}\n"
                f"Defensive Rating: {card.defensive_rating}\n"
                f"Attributes: {', '.join(card.attributes) if card.attributes else 'No attributes'}"
            )

            await channel.send(stats_message)

            # Send the image if available
            if card.image:
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



def get_last_claimed_card(discord_id):
    # This is so !stats automatically prints the stats of the last player collected, if no other player is specified
    conn = sqlite3.connect('HOPS_prototype1.db')
    cursor = conn.cursor()

    try:
        # Step 1: Retrieve user_id from users table using discord_id
        cursor.execute("SELECT user_id FROM users WHERE discord_id = ?", (discord_id,))
        user_record = cursor.fetchone()

        if user_record is None:
            print(f"No user found for Discord ID {discord_id}")
            return None

        HOPS_user_id = user_record[0]
        print(f"Found HOPS User ID: {HOPS_user_id} for Discord ID {discord_id}")

        # Step 2: Use the retrieved user_id to fetch the most recent card claimed by the user
        cursor.execute("""
            SELECT card_id 
            FROM user_cards 
            WHERE user_id = ? 
            ORDER BY rowid DESC 
            LIMIT 1
        """, (HOPS_user_id,))
        card_record = cursor.fetchone()

        if card_record is None:
            print(f"No cards found for HOPS User ID {HOPS_user_id}")
            return None

        last_card_id = card_record[0]
        print(f"Found last claimed card ID: {last_card_id} for HOPS User ID {HOPS_user_id}")

        # Step 3: Retrieve player name for the found card ID from the cards table
        cursor.execute("SELECT player_name FROM cards WHERE card_id = ?", (last_card_id,))
        card_info = cursor.fetchone()

        if card_info is None:
            print(f"No card data found for card ID {last_card_id}")
            return None

        player_name = card_info[0]
        print(f"Found player name: {player_name} for card ID {last_card_id}")

        # Step 4: Retrieve the corresponding PlayerCard instance based on the player name
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

async def trade_card(message, target_user: discord.Member, offer: str, bot: discord.Client):
    # Two players make a trade
    sender = message.author
    sender_id = sender.id
    target_user_id = target_user.id

    with connect_db() as conn:
        c = conn.cursor()

        # Retrieve user IDs & balances from the database
        c.execute("SELECT user_id, court_cash FROM users WHERE discord_id = ?", (sender_id,))
        sender_row = c.fetchone()
        c.execute("SELECT user_id, court_cash FROM users WHERE discord_id = ?", (target_user_id,))
        receiver_row = c.fetchone()

        if not sender_row or not receiver_row:
            await message.channel.send("One of the users is not found in the database.")
            return

        sender_user_id, sender_cash = sender_row
        receiver_user_id, receiver_cash = receiver_row

        # Parse offer
        offer_details = offer.strip().split()
        sender_cards, sender_cash_offer = [], 0

        for item in offer_details:
            if item.startswith("$"):  # If it's cash
                try:
                    sender_cash_offer = int(item[1:])
                except ValueError:
                    await message.channel.send("Invalid cash amount. Please enter a valid number.")
                    return
            else:  # Assume it's a card
                c.execute("""
                    SELECT cards.player_name, user_cards.instance_number, user_cards.instance_id
                    FROM user_cards
                    INNER JOIN cards ON user_cards.card_id = cards.card_id
                    WHERE user_cards.instance_id = ? AND user_cards.user_id = ?
                """, (item, sender_user_id))

                card_row = c.fetchone()
                if card_row:
                    sender_cards.append(f"{card_row[0]} #{card_row[1]} ({item})")  # Format with player_name, instance_number, and instance_id
                else:
                    await message.channel.send(f"You do not own the card with Instance ID `{item}`.")
                    return

        # Check if sender has enough Court Cash
        if sender_cash < sender_cash_offer:
            await message.channel.send("You do not have enough Court Cash to make this offer.")
            return

        # Format trade message
        sender_offer_str = ", ".join(sender_cards) + (f" and ${sender_cash_offer}" if sender_cash_offer else "")
        trade_msg = await message.channel.send(
            f"{target_user.mention}, {sender.mention} is offering `{sender_offer_str}`. Do you accept or decline?"
        )
        await trade_msg.add_reaction("✅")
        await trade_msg.add_reaction("❌")

        def check_reaction(reaction, user):
            return user == target_user and reaction.message.id == trade_msg.id and str(reaction.emoji) in ["✅", "❌"]

        try:
            reaction, _ = await bot.wait_for("reaction_add", timeout=60.0, check=check_reaction)
        except asyncio.TimeoutError:
            await message.channel.send("Trade request timed out.")
            return

        if str(reaction.emoji) == "❌":
            await message.channel.send("Trade Offer Declined.")
            return

        await message.channel.send(f"{target_user.mention}, input your return offer using `!return <Cards/Cash>`.")

        def check_return(m):
            return m.author == target_user and m.content.startswith("!return")

        try:
            return_msg = await bot.wait_for("message", timeout=60.0, check=check_return)
        except asyncio.TimeoutError:
            await message.channel.send("Return trade offer timed out.")
            return

        # Process return offer
        return_offer = return_msg.content.replace("!return ", "").strip().split()
        receiver_cards, receiver_cash_offer = [], 0

        for item in return_offer:
            if item.startswith("$"):  # If it's cash
                try:
                    receiver_cash_offer = int(item[1:])
                except ValueError:
                    await message.channel.send("Invalid cash amount in return offer.")
                    return
            else:  # Assume it's a card
                c.execute("""
                    SELECT cards.player_name, user_cards.instance_number, user_cards.instance_id
                    FROM user_cards
                    INNER JOIN cards ON user_cards.card_id = cards.card_id
                    WHERE user_cards.instance_id = ? AND user_cards.user_id = ?
                """, (item, receiver_user_id))

                card_row = c.fetchone()
                if card_row:
                    receiver_cards.append(f"{card_row[0]} #{card_row[1]} ({item})")  # Format with player_name, instance_number, and instance_id
                else:
                    await message.channel.send(f"You do not own the card with Instance ID `{item}`.")
                    return

        # Check if receiver has enough Court Cash
        if receiver_cash < receiver_cash_offer:
            await message.channel.send("You do not have enough Court Cash to make this return offer.")
            return

        # Final Confirmation
        receiver_offer_str = ", ".join(receiver_cards) + (f" and ${receiver_cash_offer}" if receiver_cash_offer else "")
        confirm_msg = await message.channel.send(
            f"{sender.mention} is offering `{sender_offer_str}`.\n"
            f"{target_user.mention} is offering `{receiver_offer_str}`.\n"
            f"Do both players accept?"
        )
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")

        def check_final(reaction, user):
            return user in [sender, target_user] and reaction.message.id == confirm_msg.id and str(reaction.emoji) in ["✅", "❌"]

        accepted_users = set()
        try:
            while len(accepted_users) < 2:
                reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check_final)
                if str(reaction.emoji) == "❌":
                    await message.channel.send("Trade Offer Declined.")
                    return
                accepted_users.add(user)
        except asyncio.TimeoutError:
            await message.channel.send("Final trade confirmation timed out.")
            return

        # Execute the trade
        # Swap the user_id of the instance_id between both users
        for sender_instance_id in sender_cards:
            instance_id = sender_instance_id.split('(')[-1].strip(')')
            c.execute("UPDATE user_cards SET user_id = ? WHERE instance_id = ?", (receiver_user_id, instance_id))
        for receiver_instance_id in receiver_cards:
            instance_id = receiver_instance_id.split('(')[-1].strip(')')
            c.execute("UPDATE user_cards SET user_id = ? WHERE instance_id = ?", (sender_user_id, instance_id))

        # Exchange Court Cash
        c.execute("UPDATE users SET court_cash = court_cash - ? WHERE discord_id = ?", (sender_cash_offer, sender_id))
        c.execute("UPDATE users SET court_cash = court_cash + ? WHERE discord_id = ?", (sender_cash_offer, target_user_id))
        c.execute("UPDATE users SET court_cash = court_cash - ? WHERE discord_id = ?", (receiver_cash_offer, target_user_id))
        c.execute("UPDATE users SET court_cash = court_cash + ? WHERE discord_id = ?", (receiver_cash_offer, sender_id))
        conn.commit()

        await message.channel.send(f"Trade Completed! `{sender_offer_str}` exchanged for `{receiver_offer_str}`.")

async def giveaway(message, target_user: discord.Member, giveaway: str, bot: discord.Client):
    # Giveaway a card
    sender = message.author
    sender_id = sender.id
    target_user_id = target_user.id

    with connect_db() as conn:
        c = conn.cursor()

        # Retrieve user IDs & balances from the database
        c.execute("SELECT user_id, court_cash FROM users WHERE discord_id = ?", (sender_id,))
        sender_row = c.fetchone()
        c.execute("SELECT user_id, court_cash FROM users WHERE discord_id = ?", (target_user_id,))
        receiver_row = c.fetchone()

        if not sender_row or not receiver_row:
            await message.channel.send("One of the users is not found in the database.")
            return

        sender_user_id, sender_cash = sender_row
        receiver_user_id, receiver_cash = receiver_row

        # Parse giveaway details
        giveaway_details = giveaway.strip().split()
        sender_cards, sender_cash_giveaway = [], 0

        for item in giveaway_details:
            if item.startswith("$"):  # If it's cash
                try:
                    sender_cash_giveaway = int(item[1:])
                except ValueError:
                    await message.channel.send("Invalid cash amount. Please enter a valid number.")
                    return
            else:  # Assume it's a card
                c.execute("""
                    SELECT cards.player_name, user_cards.instance_number, user_cards.instance_id
                    FROM user_cards
                    INNER JOIN cards ON user_cards.card_id = cards.card_id
                    WHERE user_cards.instance_id = ? AND user_cards.user_id = ?
                """, (item, sender_user_id))

                card_row = c.fetchone()
                if card_row:
                    sender_cards.append(
                        f"{card_row[0]} #{card_row[1]} ({item})")  # Format with player_name, instance_number, and instance_id
                else:
                    await message.channel.send(f"You do not own the card with Instance ID `{item}`.")
                    return

        # Check if sender has enough Court Cash
        if sender_cash < sender_cash_giveaway:
            await message.channel.send("You do not have enough Court Cash to give away.")
            return

        # Confirm giveaway with the user
        sender_offer_str = ", ".join(sender_cards) + (f" and ${sender_cash_giveaway}" if sender_cash_giveaway else "")
        confirm_msg = await message.channel.send(
            f"{target_user.mention}, {sender.mention} is giving away `{sender_offer_str}`. Do you accept?"
        )
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")

        def check_reaction(reaction, user):
            return user == target_user and reaction.message.id == confirm_msg.id and str(reaction.emoji) in ["✅", "❌"]

        try:
            reaction, _ = await bot.wait_for("reaction_add", timeout=60.0, check=check_reaction)
        except asyncio.TimeoutError:
            await message.channel.send("Giveaway request timed out.")
            return

        if str(reaction.emoji) == "❌":
            await message.channel.send("Giveaway Declined.")
            return

        # Execute the giveaway
        # Transfer cards
        for sender_instance_id in sender_cards:
            instance_id = sender_instance_id.split('(')[-1].strip(')')
            c.execute("UPDATE user_cards SET user_id = ? WHERE instance_id = ?", (receiver_user_id, instance_id))

        # Transfer Court Cash
        c.execute("UPDATE users SET court_cash = court_cash - ? WHERE discord_id = ?",
                  (sender_cash_giveaway, sender_id))
        c.execute("UPDATE users SET court_cash = court_cash + ? WHERE discord_id = ?",
                  (sender_cash_giveaway, target_user_id))

        conn.commit()

        await message.channel.send(f"Giveaway Completed! `{sender_offer_str}` has been given to {target_user.mention}.")
