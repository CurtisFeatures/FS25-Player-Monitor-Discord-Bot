import discord
import requests
import xml.etree.ElementTree as ET
import asyncio
import json
from datetime import datetime, timedelta

# Discord bot token
TOKEN = 'BOT TOKEN HERE'
CHANNEL_ID = 52435234523452345  # Replace with the channel ID where you want to post updates

# URL to the XML feed
XML_URL = 'http://10.0.0.94:8081/feed/dedicated-server-stats.xml?code=4e1df0b7c70af54127f062408cbf3736'
# File to store player states
STATE_FILE = "player_states.json"

# Initialize client
intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

# Load or initialize player states from file
def load_player_states():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Save player states to file
def save_player_states(states):
    with open(STATE_FILE, "w") as f:
        json.dump(states, f)

# Convert in-game time (milliseconds) to HH:MM format
def get_in_game_time(dayTime):
    total_seconds = dayTime // 1000
    hours = (total_seconds // 3600) % 24
    minutes = (total_seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"

# Track player states
player_states = load_player_states()

async def fetch_and_check_players():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    while not client.is_closed():
        try:
            response = requests.get(XML_URL)
            response.raise_for_status()
            xml_content = response.content
            root = ET.fromstring(xml_content)

            # Extract dayTime and convert it to in-game time
            dayTime = int(root.get("dayTime", 0))
            in_game_time = get_in_game_time(dayTime)

            # Find current players in the XML
            current_players = set()
            for player in root.findall(".//Slots/Player[@isUsed='true']"):
                player_name = player.text
                uptime_minutes = int(player.get("uptime", 0))
                current_players.add(player_name)

                # Check if player is joining for the first time in this session
                if player_name not in player_states or not player_states[player_name]["is_online"]:
                    player_states[player_name] = {
                        "is_online": True,
                        "joined_at": datetime.now().isoformat(),
                        "uptime_start": uptime_minutes
                    }
                    await channel.send(
                        f"{player_name} has joined the Server. \n"
                        f"Current In-game time is {in_game_time} \n"
                        f"The total number of players online now is {len(current_players)}"
                    )

            # Identify players who left the server
            for player_name, info in list(player_states.items()):
                if info["is_online"] and player_name not in current_players:
                    # Calculate connection duration
                    uptime_minutes = info.get("uptime_start", 0)
                    connection_duration = timedelta(minutes=uptime_minutes)
                    hours, minutes = divmod(connection_duration.seconds // 60, 60)

                    await channel.send(
                        f"{player_name} has left the server after being connected for {hours} hours and {minutes} minutes. \n"
                        f"Current In-game time is {in_game_time} \n"
                        f"The total number of players online now is {len(current_players)}"
                    )

                    # Mark the player as offline
                    player_states[player_name]["is_online"] = False

            # Save updated states
            save_player_states(player_states)

        except Exception as e:
            print(f"Error fetching XML: {e}")

        # Wait 60 seconds before checking again
        await asyncio.sleep(5)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    client.loop.create_task(fetch_and_check_players())

client.run(TOKEN)
