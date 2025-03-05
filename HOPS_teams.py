# HOPS_teams.py
import sqlite3, asyncio
from commands import get_user_id, connect_db, user_owns_card

def create_user_team(discord_id, team_name, instance_ids):
    # Adds user to teams table and makes a six-man team of players
    if len(instance_ids) != 6:
        return "You must provide exactly six instance IDs, one for each position."

    user_id = get_user_id(discord_id)
    if user_id is None:
        return "User not found. Use `!cards` first to add yourself to the database."

    with connect_db() as conn:
        c = conn.cursor()

        # Ensure the teams table exists
        c.execute('''CREATE TABLE IF NOT EXISTS teams (
            user_id INTEGER PRIMARY KEY,
            team_name TEXT,
            point_guard TEXT,
            shooting_guard TEXT,
            small_forward TEXT,
            power_forward TEXT,
            center TEXT,
            sixth_man TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')

        # Check if the user already has a team
        c.execute('SELECT team_name FROM teams WHERE user_id = ?', (user_id,))
        existing_team = c.fetchone()
        if existing_team:
            return f"You already have a team named '{existing_team[0]}'. Use `!rename_team` to make changes to it."

        # Validate instance IDs and ensure no duplicate card_id is used
        c.execute('SELECT card_id, instance_id FROM user_cards WHERE user_id = ? AND instance_id IN (?, ?, ?, ?, ?, ?)',
                  (user_id, *instance_ids))
        owned_cards = c.fetchall()

        if len(owned_cards) != 6:
            return "One or more instance IDs are invalid or do not belong to you."

        card_ids = [card[0] for card in owned_cards]
        if len(set(card_ids)) != 6:
            return "You cannot use the same player in multiple positions."

        # Insert the new team
        c.execute('''
            INSERT INTO teams (user_id, team_name, point_guard, shooting_guard, small_forward, power_forward, center, sixth_man) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, team_name, *instance_ids))
        conn.commit()

    return f"Team '{team_name}' created successfully!"

def change_team_name(discord_id, new_team_name):
    user_id = get_user_id(discord_id)
    if user_id is None:
        return "User not found. Use `!cards` first to add yourself to the database."

    with connect_db() as conn:
        c = conn.cursor()
        c.execute('UPDATE teams SET team_name = ? WHERE user_id = ?', (new_team_name, user_id))
        conn.commit()

    return f"Team name updated to '{new_team_name}'!"


async def update_team_position(message, user_id, bot):
    # Updates individual position on user's team
    sender = message.author
    sender_id = sender.id

    with connect_db() as conn:
        c = conn.cursor()

        # Get user ID
        c.execute("SELECT user_id FROM users WHERE discord_id = ?", (sender_id,))
        user_row = c.fetchone()
        if not user_row:
            await message.channel.send("You need to be registered first. Use `!cards` to register.")
            return
        user_id = user_row[0]

        # Check if user has a team
        c.execute("SELECT team_name FROM teams WHERE user_id = ?", (user_id,))
        team_row = c.fetchone()
        if not team_row:
            await message.channel.send("You don't have a team yet! Use `!team <team_name>` first.")
            return

    # Ask which position they want to update
    position_msg = await message.channel.send(
        "Which position would you like to update on your team? React with 1️⃣-6️⃣.\n\n1️⃣ Point Guard\n2️⃣ Shooting Guard\n3️⃣ Small Forward\n4️⃣ Power Forward\n5️⃣ Center\n6️⃣ Sixth Man")
    reactions = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]
    for emoji in reactions:
        await position_msg.add_reaction(emoji)

    def check_reaction(reaction, user):
        return user == sender and reaction.message.id == position_msg.id and str(reaction.emoji) in reactions

    try:
        reaction, _ = await bot.wait_for("reaction_add", timeout=60.0, check=check_reaction)
    except asyncio.TimeoutError:
        await message.channel.send("Team update timed out.")
        return

    position_map = {
        "1️⃣": "point_guard",
        "2️⃣": "shooting_guard",
        "3️⃣": "small_forward",
        "4️⃣": "power_forward",
        "5️⃣": "center",
        "6️⃣": "sixth_man"
    }
    selected_position = position_map[str(reaction.emoji)]

    await message.channel.send(
        f"Send the instance ID of the player you want to assign as your {selected_position.replace('_', ' ').title()}.")

    def check_message(m):
        return m.author == sender and m.channel == message.channel

    try:
        instance_msg = await bot.wait_for("message", timeout=60.0, check=check_message)
    except asyncio.TimeoutError:
        await message.channel.send("You took too long to respond.")
        return

    instance_id = instance_msg.content.strip()

    with connect_db() as conn:
        c = conn.cursor()
        # Validate that the user owns the card
        c.execute("SELECT card_id FROM user_cards WHERE instance_id = ? AND user_id = ?", (instance_id, user_id))
        card_row = c.fetchone()
        if not card_row:
            await message.channel.send("You do not own this card or the instance ID is incorrect.")
            return
        card_id = card_row[0]

        # Update the team
        c.execute(f"UPDATE teams SET {selected_position} = ? WHERE user_id = ?", (instance_id, user_id))
        conn.commit()

    await message.channel.send(f"Your {selected_position.replace('_', ' ').title()} has been updated!")

def view_team(discord_id):
    # Sends message with users' team
    user_id = get_user_id(discord_id)
    if user_id is None:
        return "User not found. Use `!cards` first to add yourself to the database."

    with connect_db() as conn:
        c = conn.cursor()

        # Retrieve the team information
        c.execute(
            'SELECT team_name, point_guard, shooting_guard, small_forward, power_forward, center, sixth_man FROM teams WHERE user_id = ?',
            (user_id,))
        team = c.fetchone()

        if team is None:
            return "You do not have a team yet. Use `!team create <team_name>` to create one."

        team_name, pg, sg, sf, pf, c_, sm = team

        # Retrieve player names based on instance IDs
        def get_player(instance_id):
            if instance_id:
                with connect_db() as conn:
                    c = conn.cursor()
                    c.execute('''
                        SELECT c.player_name, uc.instance_number
                        FROM user_cards uc
                        JOIN cards c ON uc.card_id = c.card_id
                        WHERE uc.instance_id = ?
                    ''', (instance_id,))
                    player = c.fetchone()
                    if player:
                        return f"{player[0]} #{player[1]}"  # Format as "Player Name #InstanceNumber"
            return "Empty"

        team_display = (
            f"**{team_name}**\n"
            f"🏀 Point Guard: {get_player(pg)}\n"
            f"🏀 Shooting Guard: {get_player(sg)}\n"
            f"🏀 Small Forward: {get_player(sf)}\n"
            f"🏀 Power Forward: {get_player(pf)}\n"
            f"🏀 Center: {get_player(c_)}\n"
            f"🏀 Sixth Man: {get_player(sm)}"
        )

    return team_display
