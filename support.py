import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import time

# --- 1. कॉन्फ़िगरेशन (CONFIGURATION) ---
API_TOKEN = os.getenv('SUPPORT_BOT_TOKEN') 
ADMIN_GROUP_ID = os.getenv('ADMIN_GROUP_ID') 

bot = telebot.TeleBot(API_TOKEN)
DATA_FILE = 'support_data.json'

# --- 2. डेटा मैनेजर (DATA MANAGER) ---
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

# --- 3. स्टार्ट कमांड (Bio Data Capture) ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = str(message.chat.id)
    name = message.from_user.first_name
    username = message.from_user.username
    data = load_data()

    # लिंक से डेटा डिकोड करना (Sales, Balance, Status, Date)
    args = message.text.split()
    sales, balance, status, join_date = "N/A", "N/A", "Unknown", "N/A"

    if len(args) > 1:
        try:
            payload = args[1].split('_')
            if len(payload) >= 4:
                sales, balance, status, join_date = payload[0], payload[1], payload[2], payload[3]
        except:
            pass

    if user_id not in data:
        try:
            # नया टॉपिक बनाना
            topic = bot.create_forum_topic(ADMIN_GROUP_ID, f"{name} | {status.upper()}")
            
            data[user_id] = topic.message_thread_id
            data[f"topic_{topic.message_thread_id}"] = user_id 
            save_data(data)

            # बायोडाटा कार्ड भेजना
            bio_msg = (
                f"👤 **NEW TICKET OPENED**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📛 **Name:** {name}\n"
                f"🆔 **User ID:** `{user_id}`\n"
                f"🔗 **Username:** @{username if username else 'None'}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💰 **Wallet Balance:** ₹{balance}\n"
                f"🛒 **Total Sales:** {sales}\n"
                f"🏆 **Status:** {status.upper()}\n"
                f"📅 **Joined:** {join_date}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔔 *User is waiting for support...*"
            )

            sent = bot.send_message(ADMIN_GROUP_ID, bio_msg, message_thread_id=topic.message_thread_id, parse_mode="Markdown")
            bot.pin_chat_message(ADMIN_GROUP_ID, sent.message_id)

            bot.send_message(user_id, "✅ **Support Connected!**\n\nनमस्ते! एडमिन से आपकी चैट शुरू हो गई है। अपनी समस्या यहाँ लिखें।", parse_mode="Markdown")
        
        except Exception as e:
            bot.send_message(user_id, "❌ Support Group connection error.")
            print(f"Topic Error: {e}")
    else:
        bot.send_message(user_id, "👋 **Welcome Back!**\nहम आपकी कैसे सहायता कर सकते हैं?", parse_mode="Markdown")

# --- 4. यूजर मैसेज फॉरवर्डिंग (User -> Admin) ---
@bot.message_handler(func=lambda m: m.chat.type == 'private', content_types=['text', 'photo', 'video', 'document', 'voice', 'audio'])
def forward_to_group(message):
    user_id = str(message.chat.id)
    data = load_data()
    
    if user_id in data:
        topic_id = data[user_id]
        try:
            bot.copy_message(ADMIN_GROUP_ID, user_id, message.message_id, message_thread_id=topic_id)
        except:
            pass
    else:
        bot.send_message(user_id, "⚠️ Session Expired. Please click /start to reconnect.")

# --- 5. एडमिन रिप्लाई और टिकट क्लोज (Admin -> User) ---
@bot.message_handler(func=lambda m: str(m.chat.id) == str(ADMIN_GROUP_ID), content_types=['text', 'photo', 'video', 'document', 'voice', 'audio'])
def handle_admin_actions(message):
    if not message.is_topic_message:
        return

    topic_id = message.message_thread_id
    data = load_data()
    user_key = f"topic_{topic_id}"

    if user_key not in data:
        return

    user_id = data[user_key]

    # अगर एडमिन ने /close लिखा हो
    if message.text == "/close":
        try:
            bot.send_message(user_id, "✅ **Support Ticket Closed!**\n\nआपकी समस्या सुलझ गई है। अगर फिर मदद चाहिए तो /start दबाएं।", parse_mode="Markdown")
            
            # डेटा क्लीनअप
            del data[user_id]
            del data[user_key]
            save_data(data)
            
            bot.send_message(ADMIN_GROUP_ID, "🔴 **Ticket Closed & Topic Deleted.**", message_thread_id=topic_id)
            bot.delete_forum_topic(ADMIN_GROUP_ID, topic_id)
        except Exception as e:
            bot.send_message(ADMIN_GROUP_ID, f"❌ Close Error: {e}", message_thread_id=topic_id)
        return

    # सामान्य रिप्लाई यूजर को भेजना
    try:
        bot.copy_message(user_id, ADMIN_GROUP_ID, message.message_id)
    except:
        bot.send_message(ADMIN_GROUP_ID, "❌ Failed: User blocked the bot.", message_thread_id=topic_id)

# --- 6. वेब सर्वर (RENDER KEEP-ALIVE) ---
app = Flask('')
@app.route('/')
def home(): return "Support Bot Live"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    Thread(target=run_server).start()
    bot.remove_webhook()
    time.sleep(1)
    print("🚀 Support Bot Polling Started...")
    while True:
        try:
            bot.polling(none_stop=True, skip_pending=True)
        except Exception as e:
            print(f"Polling Error: {e}")
            time.sleep(5)
