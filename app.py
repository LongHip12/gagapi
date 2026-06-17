import os
import re
import threading
import asyncio
import discord
from flask import Flask, jsonify
from datetime import datetime
import pytz

CHANNEL_ID = 1516342337771409498
MESSAGE_ID = 1516342676382023810
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

data = {"seed": {}, "gear": {}, "weather": []}
last_raw = ""

app = Flask(__name__)

def convert_timestamp(ts_str):
    dt = datetime.fromtimestamp(int(ts_str), tz=VN_TZ)
    return dt.strftime("%H:%M %d/%m/%Y")

def parse_content(full_text):
    seed_data = {}
    gear_data = {}
    weather_data = []
    current_section = None

    for line in full_text.split('\n'):
        line = line.strip()
        if not line:
            continue

        line_lower = line.lower()
        has_bold = '**' in line

        if not has_bold:
            if 'seed' in line_lower:
                current_section = 'seed'
                continue
            elif 'gear' in line_lower:
                current_section = 'gear'
                continue
            elif 'weather' in line_lower:
                current_section = 'weather'
                continue

        ts_match = re.search(r'\*\*(.+?)\*\*\s*[—\-]\s*<t:(\d+):R>(?:\s*\|\s*x(\d+))?', line)
        if not ts_match:
            ts_match = re.search(r'(?:<:[^>]+>\s*)(.+?)\s*[—\-]\s*<t:(\d+):R>(?:\s*\|\s*x(\d+))?', line)
        if not ts_match:
            ts_match = re.search(r'(.+?)\s*[—\-]\s*<t:(\d+):R>(?:\s*\|\s*x(\d+))?', line)

        if ts_match and current_section:
            raw_name = ts_match.group(1)
            ts = ts_match.group(2)
            qty = int(ts_match.group(3)) if ts_match.group(3) else 1
            name = re.sub(r'<:[^>]+>', '', raw_name)
            name = re.sub(r'\*+', '', name).strip()
            time_str = convert_timestamp(ts)

            if current_section == 'seed':
                seed_data[name] = {"time": time_str, "quantity": qty}
            elif current_section == 'gear':
                gear_data[name] = {"time": time_str, "quantity": qty}
            elif current_section == 'weather':
                weather_data.append({"name": name, "time": time_str})

    return seed_data, gear_data, weather_data

def extract_raw(embed):
    parts = []
    if embed.description:
        parts.append(embed.description)
    for field in embed.fields:
        if field.name:
            parts.append(field.name)
        if field.value:
            parts.append(field.value)
    return "\n".join(parts)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    asyncio.ensure_future(fetch_loop())

async def fetch_loop():
    global last_raw
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            channel = client.get_channel(CHANNEL_ID)
            if channel is None:
                channel = await client.fetch_channel(CHANNEL_ID)
            message = await channel.fetch_message(MESSAGE_ID)
            if message.embeds:
                raw = extract_raw(message.embeds[0])
                if raw != last_raw:
                    last_raw = raw
                    s, g, w = parse_content(raw)
                    data["seed"] = s
                    data["gear"] = g
                    data["weather"] = w
                    print(f"[{datetime.now(VN_TZ).strftime('%H:%M:%S')}] Updated")
        except Exception as e:
            print(f"Error: {e}")
        await asyncio.sleep(1)

@app.route('/')
def index():
    return 'discord lonely hub: https://dsc.gg/lonelyhub'

@app.route('/api/v1/gag/seed')
def seed():
    return jsonify(data['seed'])

@app.route('/api/v1/gag/gear')
def gear():
    return jsonify(data['gear'])

@app.route('/api/v1/gag/weather')
def weather():
    return jsonify(data['weather'])

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    client.run(os.environ.get('DISCORD_TOKEN'))
