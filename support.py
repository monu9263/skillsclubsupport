import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import time

# --- कॉन्फ़िगरेशन (CONFIGURATION) ---
API_TOKEN = os.getenv('SUPPORT_BOT_TOKEN') 
ADMIN_GROUP_ID = os.getenv('ADMIN_GROUP_ID') 

bot = telebot.TeleBot(API_TOKEN)
DATA_FILE = 'support_data.json'

# --- डेटा मैनेजर (Fixed Indentation) ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- 1. START COMMAND ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = str(message.chat.id)
    name = message.from_user.first_name
    username = message.from_user.username
    data = load_data()

    # URL से डेटा निकालें
    args = message.text.split()
    sales_count = "N/A"
    join_date = "N/A"
    
    if len(args) > 1:
        try:
            payload = args[1].split('_')
            sales_count = payload[0]
            join_date = payload[1]
        except:
            pass

    # --- TOPIC बनाना ---
    if user_id not in data:
        try:
            # ग्रुप में टॉपिक बनाएं
            topic = bot.create_forum_topic(ADMIN_GROUP_ID, f"{name} | {user_id}")
            
            # डेटा सेव करें
            data[user_id] = topic.message_thread_id
            data[f"topic_{topic.message_thread_id}"] = user_id 
            save_data(data)

            # BIO DATA मैसेज
            bio_msg = (
                f"👤 **NEW USER TICKET**\n"
                f"━━━━━━━━━━━━━━\n"
                f"📛 **Name:** {name}\n"
                f"🆔 **User ID:** `{user_id}`\n"
                f"🔗 **Username:** @{username if username else 'None'}\n"
                f"📅 **Join Date:** {join_date}\n"
                f"🛒 **Courses Sold:** {sales_count}\n"
                f"━━━━━━━━━━━━━━\n"
                f"🔔 *User is waiting for support.*"
            )

            # ग्रुप में भेजें
            bot.send_message(ADMIN_GROUP_ID, bio_msg, message_thread_id=topic.message_thread_id, parse_mode="Markdown")
            
            # यूजर को रिप्लाई
            bot.send_message(user_id, "✅ **Support Connected!**\n\nनमस्ते! आप एडमिन से जुड़ चुके हैं। अपनी समस्या यहाँ लिखें (Text, Photo या Video)।", parse_mode="Markdown")
        
        except Exception as e:
            bot.send_message(user_id, "❌ Error: Support System is offline.")
            print(f"Error Creating Topic: {e}")
    else:
        bot.send_message(user_id, "👋 **Welcome Back!**\nहम आपकी कैसे सहायता कर सकते हैं?", parse_mode="Markdown")

# --- 2. यूजर का मैसेज ग्रुप में भेजना ---
@bot.message_handler(func=lambda m: m.chat.type == 'private', content_types=['text', 'photo', 'video', 'document', 'voice', 'audio'])
def forward_to_group(message):
    user_id = str(message.chat.id)
    data = load_data()
    
    if user_id in data:
        topic_id = data[user_id]
        try:
            bot.copy_message(ADMIN_GROUP_ID, user_id, message.message_id, message_thread_id=topic_id)
        except Exception as e:
            print(f"Forward Error: {e}")
    else:
        bot.send_message(user_id, "⚠️ Session Expired. Please click /start")

# --- 3. एडमिन का रिप्लाई यूजर को भेजना ---
@bot.message_handler(func=lambda m: str(m.chat.id) == str(ADMIN_GROUP_ID), content_types=['text', 'photo', 'video', 'document', 'voice', 'audio'])
def reply_to_user(message):
    # Logs में ID प्रिंट करें ताकि आप देख सकें
    print(f"📢 Group Message ID: {message.chat.id}")

    if not message.is_topic_message:
        return
    
    topic_id = message.message_thread_id
    data = load_data()
    user_key = f"topic_{topic_id}"
    
    if user_key in data:
        user_id = data[user_key]
        try:
            bot.copy_message(user_id, ADMIN_GROUP_ID, message.message_id)
        except:
            bot.send_message(ADMIN_GROUP_ID, "❌ Failed: User blocked bot.", message_thread_id=topic_id)

# --- SERVER ---
app = Flask('')
@app.route('/')
def home():
    return "Support Bot Live"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    Thread(target=run).start()
    bot.remove_webhook()
    time.sleep(1)
    print("🚀 Support Bot Started...")
    while True:
        try:
            bot.polling(none_stop=True, skip_pending=True)
        except Exception as e:
            print(f"Polling Error: {e}")
            time.sleep(5)
