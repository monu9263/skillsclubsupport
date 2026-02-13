import telebot
from telebot import types
import json
import os
import requests
from flask import Flask, request

# --- 1. CONFIGURATION ---
API_TOKEN = os.getenv('API_TOKEN')  # सपोर्ट बोट का टोकन
ADMIN_ID = os.getenv('ADMIN_ID', "8114779182")
# Group ID integer होना चाहिए
try:
    GROUP_ID = int(os.getenv('GROUP_ID')) 
except:
    GROUP_ID = None

MAIN_BOT_URL = os.getenv('MAIN_BOT_URL') # Main Bot का Render Link (Bridge)
WEBHOOK_URL = os.getenv('RENDER_EXTERNAL_URL') # इसका खुद का URL

if not API_TOKEN or not GROUP_ID:
    print("❌ ERROR: Config Missing! Check API_TOKEN and GROUP_ID")

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# LOCAL DATA (Topics Store करने के लिए)
TOPIC_DB = 'active_topics.json'

# --- 2. DATA MANAGER ---
def load_db():
    if not os.path.exists(TOPIC_DB):
        return {}
    try:
        with open(TOPIC_DB, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_db(data):
    try:
        with open(TOPIC_DB, 'w') as f:
            json.dump(data, f, indent=4)
    except:
        pass

# --- 3. BRIDGE: FETCH USER DATA ---
def fetch_user_stats(uid):
    """Main Bot से यूजर का डेटा मांगता है"""
    if not MAIN_BOT_URL:
        return "⚠️ Data Bridge Not Connected"
    
    try:
        # Main Bot को कॉल करो
        url = f"{MAIN_BOT_URL}/api/user/{uid}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            user = response.json()
            if not user: return "👤 New User (No Data)"
            
            # डेटा सजाकर भेजो
            return (f"📊 <b>USER DATA (From Bridge):</b>\n"
                    f"👤 Name: {user.get('name', 'Unknown')}\n"
                    f"🆔 ID: <code>{uid}</code>\n"
                    f"💰 Wallet: ₹{user.get('balance', 0)}\n"
                    f"👥 Referrals: {user.get('referrals', 0)}\n"
                    f"🛒 Purchases: {len(user.get('purchased', []))}")
        else:
            return "⚠️ User Data Not Found"
    except Exception as e:
        return f"❌ Bridge Error: {e}"

# --- 4. HANDLERS ---

# (A) USER MESSAGE -> CREATE/FIND TOPIC
@bot.message_handler(func=lambda m: m.chat.type == 'private', content_types=['text', 'photo', 'video', 'document', 'audio', 'voice'])
def handle_user(message):
    uid = str(message.chat.id)
    name = message.from_user.first_name
    
    db = load_db()
    topic_id = db.get(uid)

    # अगर टॉपिक नहीं है, तो नया बनाओ
    if not topic_id:
        try:
            # 1. टॉपिक बनाओ
            topic = bot.create_forum_topic(GROUP_ID, f"{name} | {uid}")
            topic_id = topic.message_thread_id
            
            # 2. Main Bot से डेटा मंगाओ (Bridge)
            stats = fetch_user_stats(uid)
            
            # 3. ग्रुप में सबसे ऊपर डेटा भेजो
            bot.send_message(GROUP_ID, stats, message_thread_id=topic_id, parse_mode="HTML")
            
            # 4. सेव करो
            db[uid] = topic_id
            save_db(db)
        except Exception as e:
            bot.reply_to(message, "❌ Support System Error. Make sure Bot is Admin in Group & Topics Enabled.")
            return

    # मैसेज फॉरवर्ड करो (User -> Group Topic)
    try:
        bot.copy_message(GROUP_ID, uid, message.message_id, message_thread_id=topic_id)
    except:
        bot.reply_to(message, "❌ Message not sent.")

# (B) ADMIN REPLY -> USER
@bot.message_handler(func=lambda m: m.chat.id == GROUP_ID and m.message_thread_id, content_types=['text', 'photo', 'video', 'document', 'audio', 'voice'])
def handle_admin(message):
    topic_id = message.message_thread_id
    db = load_db()
    
    # Topic ID से User ID ढूँढो
    user_id = None
    for uid, tid in db.items():
        if tid == topic_id:
            user_id = uid
            break
    
    if not user_id:
        return # टॉपिक शायद डेटाबेस में नहीं है

    # CLOSE COMMAND Logic
    if message.text and message.text.lower() == "/close":
        try:
            # 1. टॉपिक डिलीट करें
            bot.delete_forum_topic(GROUP_ID, topic_id)
            
            # 2. डेटाबेस से हटाएं
            del db[user_id]
            save_db(db)
            
            # 3. यूजर को फाइनल मैसेज भेजें (Updated)
            close_msg = (
                "✅ <b>Ticket Closed!</b>\n\n"
                "आपकी टिकट क्लोज कर दी गई है।\n"
                "Thanks for choosing <b>SkillsClub Support</b>. 🙏\n\n"
                "Feel free to ask anything again!"
            )
            bot.send_message(user_id, close_msg, parse_mode="HTML")
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error closing topic: {e}")
        return

    # सामान्य रिप्लाई (Admin -> User)
    try:
        bot.copy_message(user_id, GROUP_ID, message.message_id)
    except:
        bot.reply_to(message, "❌ Failed (User blocked bot?)")

# (C) START COMMAND (UPDATED MSG)
@bot.message_handler(commands=['start'])
def start(m):
    if m.chat.type == 'private':
        welcome_msg = (
            "👋 <b>Welcome to SkillsClub Support!</b>\n\n"
            "⏳ <b>Please Wait for Admin Reply.</b>\n"
            "Share your problem below 👇\n\n"
            "⏳ <b>कृपया एडमिन के रिप्लाई का इंतज़ार करें।</b>\n"
            "अपनी समस्या नीचे लिखें 👇"
        )
        bot.send_message(m.chat.id, welcome_msg, parse_mode="HTML")

# --- 5. WEBHOOK ---
@app.route('/' + API_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + "/" + API_TOKEN)
    return "Support Bridge Running!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    
