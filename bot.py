# bot.py
import telebot
from telebot import types
import os
import json

# start small web server so hosting platform can health-check
from keep_alive import keep_alive

# ---------------- ENV ----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not TOKEN:
    raise RuntimeError("Missing TOKEN environment variable.")
if not ADMIN_ID:
    raise RuntimeError("Missing ADMIN_ID environment variable.")

ADMIN_ID = int(ADMIN_ID)
bot = telebot.TeleBot(TOKEN)

# ---------------- JSON helpers ----------------
def load_json(filename):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write("{}")
    with open(filename, "r") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

users = load_json("users.json")
tasks = load_json("tasks.json")
pending = load_json("pending.json")

# ---------------- MESSAGES ----------------
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
        "language_updated": "भाषा सफलतापूर्वक अपडेट हो गई!"
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
        "language_updated": "Language updated successfully!"
    }
}

# ---------------- USER registration ----------------
def register_user(user_id):
    if str(user_id) not in users:
        users[str(user_id)] = {
            "points": 0,
            "language": "Hindi",
            "withdraw": [],
            "current_task": 0
        }
        save_json("users.json", users)

# ---------------- MAIN MENU ----------------
def main_menu(lang):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📋 Tasks", "💰 Balance")
    markup.add("📤 Withdraw", "🌐 Language")
    return markup

# ---------------- /start ----------------
@bot.message_handler(commands=['start'])
def start(message):
    register_user(message.chat.id)
    lang = users[str(message.chat.id)]["language"]
    bot.send_message(message.chat.id, MESSAGES[lang]["welcome"], reply_markup=main_menu(lang))

# ---------------- Language ----------------
@bot.message_handler(func=lambda m: m.text == "🌐 Language")
def change_language(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_hi"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    bot.send_message(message.chat.id, "Select language:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def set_language(call):
    lang = "Hindi" if call.data == "lang_hi" else "English"
    users[str(call.message.chat.id)]["language"] = lang
    save_json("users.json", users)
    bot.answer_callback_query(call.id, MESSAGES[lang]["language_updated"])
    bot.send_message(call.message.chat.id, MESSAGES[lang]["welcome"], reply_markup=main_menu(lang))

# ---------------- Balance ----------------
@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def balance(message):
    user_id = str(message.chat.id)
    lang = users[user_id]["language"]
    pts = users[user_id]["points"]
    bot.send_message(message.chat.id, MESSAGES[lang]["balance"].format(points=pts))

# ---------------- Tasks (one by one) ----------------
@bot.message_handler(func=lambda m: m.text == "📋 Tasks")
def show_task_one_by_one(message):
    user_id = str(message.chat.id)
    register_user(message.chat.id)
    users[user_id]["current_task"] = 0
    save_json("users.json", users)
    send_task_by_index(message, 0)

def send_task_by_index(message, index):
    user_id = str(message.chat.id)
    lang = users[user_id]["language"]
    task_ids = list(tasks.keys())

    if len(task_ids) == 0:
        bot.send_message(message.chat.id, MESSAGES[lang]["no_tasks"])
        return

    if index >= len(task_ids):
        bot.send_message(message.chat.id, "No more tasks.")
        return

    task_id = task_ids[index]
    task = tasks[task_id]

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔗 Open Link", url=task["link"]),
        types.InlineKeyboardButton("📤 Upload Screenshot", callback_data=f"upload_{task_id}")
    )

    if index + 1 < len(task_ids):
        markup.add(types.InlineKeyboardButton("➡ Next Task", callback_data=f"next_{index+1}"))

    bot.send_message(
        message.chat.id,
        f"📝 Task: {task['title']}\nReward: +1 point",
        reply_markup=markup
    )

    users[user_id]["current_task"] = index
    save_json("users.json", users)

@bot.callback_query_handler(func=lambda call: call.data.startswith("next_"))
def next_task(call):
    index = int(call.data.split("_")[1])
    send_task_by_index(call.message, index)
    bot.answer_callback_query(call.id)

# ---------------- Upload flow ----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("upload_"))
def ask_screenshot(call):
    task_id = call.data.split("_")[1]
    bot.answer_callback_query(call.id)
    lang = users[str(call.message.chat.id)]["language"]
    msg = bot.send_message(call.message.chat.id, MESSAGES[lang]["screenshot_prompt"])
    bot.register_next_step_handler(msg, receive_screenshot, task_id)

def receive_screenshot(message, task_id):
    lang = users[str(message.chat.id)]["language"]
    if message.content_type != 'photo':
        bot.send_message(message.chat.id, MESSAGES[lang]["image_only"])
        return
    file_id = message.photo[-1].file_id
    pending_item = {"user": message.chat.id, "task": task_id, "file_id": file_id}
    pending_id = str(len(pending) + 1)
    pending[pending_id] = pending_item
    save_json("pending.json", pending)
    bot.send_message(message.chat.id, MESSAGES[lang]["submitted"])
    bot.send_message(ADMIN_ID,
                     f"📥 New submission pending\nUser: {message.chat.id}\nTask: {task_id}")

# ---------------- Withdraw ----------------
@bot.message_handler(func=lambda m: m.text == "📤 Withdraw")
def withdraw(message):
    lang = users[str(message.chat.id)]["language"]
    msg = bot.send_message(message.chat.id, MESSAGES[lang]["withdraw_prompt"])
    bot.register_next_step_handler(msg, save_withdraw)

def save_withdraw(message):
    user = str(message.chat.id)
    upi = message.text
    users[user]["withdraw"].append(upi)
    save_json("users.json", users)
    lang = users[user]["language"]
    bot.send_message(message.chat.id, MESSAGES[lang]["withdraw_sent"])
    bot.send_message(ADMIN_ID,
                     f"💸 New withdraw request\nUser: {user}\nUPI: {upi}")

# ---------------- Admin panel ----------------
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != ADMIN_ID:
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Add Task", "🗑 Remove Task")
    markup.add("✔ Approve Screenshots", "📊 Users")
    markup.add("⬅ Back")
    bot.send_message(message.chat.id, "Admin Panel:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "➕ Add Task")
def add_task_title(message):
    if message.chat.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, "Send task title:")
    bot.register_next_step_handler(msg, add_task_link)

def add_task_link(message):
    title = message.text
    msg = bot.send_message(message.chat.id, "Send task link:")
    bot.register_next_step_handler(msg, save_task, title)

def save_task(message, title):
    link = message.text
    task_id = str(len(tasks) + 1)
    tasks[task_id] = {"title": title, "link": link}
    save_json("tasks.json", tasks)
    bot.send_message(message.chat.id, "✅ Task added successfully!")

@bot.message_handler(func=lambda m: m.text == "🗑 Remove Task")
def remove_task(message):
    if message.chat.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, "Send Task ID to remove:")
    bot.register_next_step_handler(msg, delete_task)

def delete_task(message):
    task_id = message.text
    if task_id in tasks:
        del tasks[task_id]
        save_json("tasks.json", tasks)
        bot.send_message(message.chat.id, "❌ Task removed.")
    else:
        bot.send_message(message.chat.id, "Invalid Task ID.")

@bot.message_handler(func=lambda m: m.text == "✔ Approve Screenshots")
def approve_panel(message):
    if message.chat.id != ADMIN_ID:
        return
    if len(pending) == 0:
        bot.send_message(message.chat.id, "No pending submissions.")
        return
    for pid, item in list(pending.items()):
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✔ Approve", callback_data=f"ok_{pid}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"no_{pid}")
        )
        bot.send_photo(message.chat.id,
                       item["file_id"],
                       caption=f"Pending ID: {pid}\nUser: {item['user']}\nTask: {item['task']}",
                       reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ok_") or c.data.startswith("no_"))
def handle_approval(call):
    pid = call.data.split("_")[1]
    if pid not in pending:
        return
    entry = pending[pid]
    user = str(entry["user"])
    lang = users[user]["language"]

    if call.data.startswith("ok"):
        users[user]["points"] += 1
        bot.send_message(user, "🎉 Your screenshot has been approved! +1 point")
        bot.edit_message_caption("Approved ✔", call.message.chat.id, call.message.message_id)
    else:
        bot.send_message(user, "❌ Your screenshot was rejected.")
        bot.edit_message_caption("Rejected ❌", call.message.chat.id, call.message.message_id)

    del pending[pid]
    save_json("pending.json", pending)
    save_json("users.json", users)

# ---------------- START server + bot ----------------
if __name__ == "__main__":
    # start webserver for health checks
    keep_alive()
    print("BOT IS RUNNING...")
    bot.infinity_polling()
    
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot Running Successfully!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()
