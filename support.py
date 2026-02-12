import telebot
import json, os, time
from flask import Flask
from threading import Thread

# --- CONFIG ---
SUPPORT_TOKEN = os.getenv('SUPPORT_BOT_TOKEN')
ADMIN_GROUP_ID = "-1003513803493" #

bot = telebot.TeleBot(SUPPORT_TOKEN)
app = Flask('')
DATA_FILE = 'support_data.json'

def load_data():
    if not os.path.exists(DATA_FILE): return {}
    with open(DATA_FILE, 'r') as f: return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f: json.dump(data, f, indent=4)

@bot.message_handler(commands=['start'])
def start_support(message):
    uid = str(message.chat.id)
    data = load_data()
    
    # Payload Parsing (Fixes N/A)
    args = message.text.split()
    sales, bal, status, date = "N/A", "N/A", "Unknown", "N/A"
    if len(args) > 1:
        parts = args[1].split('_')
        if len(parts) >= 4: 
            sales, bal, status, date = parts[0], parts[1], parts[2], parts[3]

    if uid not in data:
        try:
            topic = bot.create_forum_topic(ADMIN_GROUP_ID, f"{message.from_user.first_name} | {status}")
            data[uid] = topic.message_thread_id
            data[f"topic_{topic.message_thread_id}"] = uid
            save_data(data)
            
            bio = (f"👤 **NEW TICKET**\n🆔 User ID: `{uid}`\n💰 Balance: ₹{bal}\n🛒 Sales: {sales}\n🏆 Status: {status}\n📅 Joined: {date}")
            bot.send_message(ADMIN_GROUP_ID, bio, message_thread_id=topic.message_thread_id, parse_mode="Markdown")
        except: pass

    bot.send_message(uid, "✅ एडमिन से चैट शुरू हो गई है। अपनी समस्या लिखें।")

@bot.message_handler(func=lambda m: str(m.chat.id) == str(ADMIN_GROUP_ID))
def admin_reply(message):
    if not message.is_topic_message: return
    tid = message.message_thread_id
    data = load_data()
    uid = data.get(f"topic_{tid}")
    if not uid: return

    if message.text == "/close":
        bot.send_message(uid, "🔴 टिकट क्लोज कर दिया गया है।")
        bot.delete_forum_topic(ADMIN_GROUP_ID, tid)
        del data[uid], data[f"topic_{tid}"]
        save_data(data)
    else:
        bot.copy_message(uid, ADMIN_GROUP_ID, message.message_id)

@bot.message_handler(func=lambda m: m.chat.type == 'private')
def user_msg(message):
    uid = str(message.chat.id)
    data = load_data()
    if uid in data:
        bot.copy_message(ADMIN_GROUP_ID, uid, message.message_id, message_thread_id=data[uid])

@app.route('/')
def home(): return "Support Active"

def run(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

if __name__ == "__main__":
    Thread(target=run).start()
    bot.polling(none_stop=True)
