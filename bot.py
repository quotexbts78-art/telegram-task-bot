import os
import json
from traceback import format_exc
from flask import Flask, request
import telebot
from telebot import types

# ---------------- ENVIRONMENT -----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Render ka URL

if not TOKEN:
    raise RuntimeError("Missing TOKEN environment variable.")
if not ADMIN_ID:
    raise RuntimeError("Missing ADMIN_ID environment variable.")
if not WEBHOOK_URL:
    raise RuntimeError("Missing WEBHOOK_URL environment variable.")

ADMIN_ID = int(ADMIN_ID)

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

app = Flask(__name__)


# ---------------- JSON HELPERS ----------------
DATA_FILES = {
    "users": "users.json",
    "tasks": "tasks.json",
    "pending": "pending.json"
}

def safe_load(filename):
    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}

    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except:
        os.rename(filename, filename + ".bak")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}

def safe_save(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


users = safe_load(DATA_FILES["users"])
tasks = safe_load(DATA_FILES["tasks"])
pending = safe_load(DATA_FILES["pending"])


# ---------------- LANGUAGE TEXTS ----------------
MESSAGES = {
    "Hindi": {
        "welcome": "👋 स्वागत है! एक विकल्प चुनें:",
        "balance": "💰 आपका बैलेंस: {points} पॉइंट्स",
        "no_tasks": "अभी कोई टास्क उपलब्ध नहीं है।",
        "screenshot_prompt": "कृपया स्क्रीनशॉट अपलोड करें:",
        "image_only": "❌ कृपया केवल इमेज भेजें।",
        "submitted": "⌛ स्क्रीनशॉट स्वीकृति के लिए भेजा गया।",
        "withdraw_prompt": "अपना UPI ID दर्ज करें:",
        "withdraw_sent": "✅ Withdraw अनुरोध एडमिन को भेजा गया!",
        "language_selected": "भाषा सफलतापूर्वक अपडेट हो गई!"
    },
    "English": {
        "welcome": "👋 Welcome! Choose an option:",
        "balance": "💰 Your Balance: {points} points",
        "no_tasks": "No tasks available right now.",
        "screenshot_prompt": "Please upload the screenshot:",
        "image_only": "❌ Please send an image only.",
        "submitted": "⌛ Screenshot submitted for approval.",
        "withdraw_prompt": "Enter your UPI ID:",
        "withdraw_sent": "✅ Withdraw request sent to admin!",
        "language_selected": "Language updated successfully!"
    }
}



# ---------------- HELPERS ----------------
def register_user(uid):
    key = str(uid)
    if key not in users:
        users[key] = {
            "points": 0,
            "language": "Hindi",
            "withdraw": [],
            "current_task": 0
        }
        safe_save(DATA_FILES["users"], users)

def get_lang(uid):
    register_user(uid)
    return users[str(uid)]["language"]

def main_menu(lang):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("📋 Tasks", "💰 Balance")
    m.add("📤 Withdraw", "🌐 Language")
    return m


# ---------------- START HANDLER ----------------
@bot.message_handler(commands=["start"])
def start_handler(message):
    register_user(message.chat.id)
    lang = get_lang(message.chat.id)
    bot.send_message(message.chat.id, MESSAGES[lang]["welcome"], reply_markup=main_menu(lang))


# ---------------- LANGUAGE CHANGE ----------------
@bot.message_handler(func=lambda m: m.text == "🌐 Language")
def change_language(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_hi"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    bot.send_message(message.chat.id, "Select language:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("lang_"))
def set_language(call):
    lang = "Hindi" if call.data == "lang_hi" else "English"
    users[str(call.message.chat.id)]["language"] = lang
    safe_save(DATA_FILES["users"], users)
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, MESSAGES[lang]["welcome"], reply_markup=main_menu(lang))



# ---------------- BALANCE ----------------
@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def balance(message):
    lang = get_lang(message.chat.id)
    pts = users[str(message.chat.id)]["points"]
    bot.send_message(message.chat.id, MESSAGES[lang]["balance"].format(points=pts))



# ---------------- TASKS ----------------
@bot.message_handler(func=lambda m: m.text == "📋 Tasks")
def show_tasks(message):
    users[str(message.chat.id)]["current_task"] = 0
    safe_save(DATA_FILES["users"], users)
    send_task(message.chat.id, 0)

def send_task(chat_id, index):
    lang = get_lang(chat_id)
    ids = list(tasks.keys())

    if not ids:
        return bot.send_message(chat_id, MESSAGES[lang]["no_tasks"])

    if index >= len(ids):
        return bot.send_message(chat_id, "No more tasks.")

    tid = ids[index]
    task = tasks[tid]

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🔗 Open Link", url=task["link"]),
        types.InlineKeyboardButton("📤 Upload Screenshot", callback_data=f"up_{tid}")
    )
    if index + 1 < len(ids):
        kb.add(types.InlineKeyboardButton("➡ Next Task", callback_data=f"next_{index+1}"))

    bot.send_message(chat_id, f"📝 {task['title']}\nReward: +1 point", reply_markup=kb)

    users[str(chat_id)]["current_task"] = index
    safe_save(DATA_FILES["users"], users)

@bot.callback_query_handler(func=lambda c: c.data.startswith("next_"))
def next_task(call):
    index = int(call.data.split("_")[1])
    send_task(call.message.chat.id, index)
    bot.answer_callback_query(call.id)



# ---------------- SCREENSHOT UPLOAD ----------------
@bot.callback_query_handler(func=lambda c: c.data.startswith("up_"))
def ask_ss(call):
    tid = call.data.split("_")[1]
    lang = get_lang(call.message.chat.id)

    msg = bot.send_message(call.message.chat.id, MESSAGES[lang]["screenshot_prompt"])
    bot.register_next_step_handler(msg, receive_screenshot, tid)
    bot.answer_callback_query(call.id)

def receive_screenshot(message, tid):
    lang = get_lang(message.chat.id)

    if message.content_type != "photo":
        return bot.send_message(message.chat.id, MESSAGES[lang]["image_only"])

    file_id = message.photo[-1].file_id
    pid = str(len(pending) + 1)

    pending[pid] = {"user": message.chat.id, "task": tid, "file_id": file_id}
    safe_save(DATA_FILES["pending"], pending)

    bot.send_message(message.chat.id, MESSAGES[lang]["submitted"])

    try:
        bot.send_message(ADMIN_ID, f"📥 New Submission\nID: {pid}\nUser: {message.chat.id}\nTask: {tid}")
    except:
        pass



# ---------------- WITHDRAW ----------------
@bot.message_handler(func=lambda m: m.text == "📤 Withdraw")
def withdraw(message):
    lang = get_lang(message.chat.id)
    msg = bot.send_message(message.chat.id, MESSAGES[lang]["withdraw_prompt"])
    bot.register_next_step_handler(msg, save_withdraw)

def save_withdraw(message):
    uid = str(message.chat.id)
    upi = message.text.strip()

    users[uid]["withdraw"].append(upi)
    safe_save(DATA_FILES["users"], users)

    lang = get_lang(message.chat.id)
    bot.send_message(message.chat.id, MESSAGES[lang]["withdraw_sent"])

    try:
        bot.send_message(ADMIN_ID, f"💸 Withdraw Request\nUser: {uid}\nUPI: {upi}")
    except:
        pass



# ---------------- ADMIN PANEL ----------------
@bot.message_handler(commands=["admin"])
def admin(message):
    if message.chat.id != ADMIN_ID:
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Add Task", "🗑 Remove Task")
    kb.add("✔ Approve Screenshots", "📊 Users")
    kb.add("⬅ Back")
    bot.send_message(message.chat.id, "Admin Panel:", reply_markup=kb)



# ---------------- FLASK WEBHOOK ----------------
@app.route("/", methods=["GET"])
def home():
    return "Bot Running via Webhook!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_str = request.get_data().decode("UTF-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "OK", 200
    return "Invalid", 400



# ---------------- RUN ----------------
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + "/webhook")
    app.run(host="0.0.0.0", port=10000)
