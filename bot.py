# bot.py
import os
import json
import traceback
from threading import Thread
from time import sleep

import telebot
from telebot import types

# start a tiny webserver for host health checks
# keep_alive uses PORT env var (works on Render, Railway, Replit if needed)
try:
    from keep_alive import keep_alive
except Exception:
    # keep_alive may not exist locally; that's fine.
    def keep_alive():
        return None

# ------------------ Environment ------------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not TOKEN:
    raise RuntimeError("Missing TOKEN environment variable.")
if not ADMIN_ID:
    raise RuntimeError("Missing ADMIN_ID environment variable.")

try:
    ADMIN_ID = int(ADMIN_ID)
except Exception:
    raise RuntimeError("ADMIN_ID environment variable must be an integer (your Telegram ID).")

bot = telebot.TeleBot(TOKEN)

# ------------------ JSON helpers ------------------
DATA_FILES = {
    "users": "users.json",
    "tasks": "tasks.json",
    "pending": "pending.json"
}

def safe_load(filename):
    """Load JSON safely, return dict on error."""
    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        # if file corrupted, back it up and return empty dict
        try:
            os.rename(filename, filename + ".bak")
        except Exception:
            pass
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}

def safe_save(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

users = safe_load(DATA_FILES["users"])
tasks = safe_load(DATA_FILES["tasks"])
pending = safe_load(DATA_FILES["pending"])

# ------------------ Messages (i18n) ------------------
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

# ------------------ Helpers ------------------
def register_user(user_id):
    key = str(user_id)
    if key not in users:
        users[key] = {
            "points": 0,
            "language": "Hindi",
            "withdraw": [],
            "current_task": 0
        }
        safe_save(DATA_FILES["users"], users)

def get_lang(user_id):
    key = str(user_id)
    register_user(user_id)
    return users.get(key, {}).get("language", "Hindi")

def main_menu(lang):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📋 Tasks", "💰 Balance")
    markup.add("📤 Withdraw", "🌐 Language")
    return markup

# ------------------ Handlers ------------------
@bot.message_handler(commands=["start"])
def start_handler(message):
    register_user(message.chat.id)
    lang = get_lang(message.chat.id)
    bot.send_message(message.chat.id, MESSAGES[lang]["welcome"], reply_markup=main_menu(lang))

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
    safe_save(DATA_FILES["users"], users)
    bot.answer_callback_query(call.id, MESSAGES[lang]["language_selected"])
    bot.send_message(call.message.chat.id, MESSAGES[lang]["welcome"], reply_markup=main_menu(lang))

@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def balance(message):
    register_user(message.chat.id)
    lang = get_lang(message.chat.id)
    pts = users[str(message.chat.id)]["points"]
    bot.send_message(message.chat.id, MESSAGES[lang]["balance"].format(points=pts))

# Tasks one-by-one
@bot.message_handler(func=lambda m: m.text == "📋 Tasks")
def show_task_one_by_one(message):
    register_user(message.chat.id)
    user_key = str(message.chat.id)
    users[user_key]["current_task"] = 0
    safe_save(DATA_FILES["users"], users)
    send_task_by_index(message.chat.id, 0)

def send_task_by_index(chat_id, index):
    register_user(chat_id)
    user_key = str(chat_id)
    lang = get_lang(chat_id)
    task_ids = list(tasks.keys())
    if len(task_ids) == 0:
        bot.send_message(chat_id, MESSAGES[lang]["no_tasks"])
        return
    if index >= len(task_ids):
        bot.send_message(chat_id, "No more tasks.")
        return
    task_id = task_ids[index]
    task = tasks.get(task_id, {"title":"Untitled","link":"https://"})
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔗 Open Link", url=task["link"]),
        types.InlineKeyboardButton("📤 Upload Screenshot", callback_data=f"upload_{task_id}")
    )
    if index + 1 < len(task_ids):
        markup.add(types.InlineKeyboardButton("➡ Next Task", callback_data=f"next_{index+1}"))
    bot.send_message(chat_id, f"📝 Task: {task['title']}\nReward: +1 point", reply_markup=markup)
    users[user_key]["current_task"] = index
    safe_save(DATA_FILES["users"], users)

@bot.callback_query_handler(func=lambda call: call.data.startswith("next_"))
def next_task(call):
    try:
        index = int(call.data.split("_",1)[1])
    except:
        index = 0
    send_task_by_index(call.message.chat.id, index)
    bot.answer_callback_query(call.id)

# Upload screenshot flow
@bot.callback_query_handler(func=lambda call: call.data.startswith("upload_"))
def ask_screenshot(call):
    task_id = call.data.split("_",1)[1]
    bot.answer_callback_query(call.id)
    lang = get_lang(call.message.chat.id)
    msg = bot.send_message(call.message.chat.id, MESSAGES[lang]["screenshot_prompt"])
    bot.register_next_step_handler(msg, receive_screenshot, task_id)

def receive_screenshot(message, task_id):
    lang = get_lang(message.chat.id)
    if message.content_type != 'photo':
        bot.send_message(message.chat.id, MESSAGES[lang]["image_only"])
        return
    file_id = message.photo[-1].file_id
    # create pending entry
    pid = str(len(pending) + 1)
    pending[pid] = {"user": message.chat.id, "task": task_id, "file_id": file_id}
    safe_save(DATA_FILES["pending"], pending)
    bot.send_message(message.chat.id, MESSAGES[lang]["submitted"])
    # notify admin
    try:
        bot.send_message(ADMIN_ID, f"📥 New submission pending\nPending ID: {pid}\nUser: {message.chat.id}\nTask: {task_id}")
    except Exception:
        pass

# Withdraw flow
@bot.message_handler(func=lambda m: m.text == "📤 Withdraw")
def withdraw(message):
    register_user(message.chat.id)
    lang = get_lang(message.chat.id)
    msg = bot.send_message(message.chat.id, MESSAGES[lang]["withdraw_prompt"])
    bot.register_next_step_handler(msg, save_withdraw)

def save_withdraw(message):
    user_key = str(message.chat.id)
    upi = message.text.strip()
    users[user_key]["withdraw"].append(upi)
    safe_save(DATA_FILES["users"], users)
    lang = get_lang(message.chat.id)
    bot.send_message(message.chat.id, MESSAGES[lang]["withdraw_sent"])
    try:
        bot.send_message(ADMIN_ID, f"💸 New withdraw request\nUser: {user_key}\nUPI: {upi}")
    except Exception:
        pass

# Admin commands & panel
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != ADMIN_ID:
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Add Task", "🗑 Remove Task")
    markup.add("✔ Approve Screenshots", "📊 Users", "⬅ Back")
    bot.send_message(message.chat.id, "Admin Panel:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "➕ Add Task")
def add_task_title(message):
    if message.chat.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, "Send task title:")
    bot.register_next_step_handler(msg, add_task_link)

def add_task_link(message):
    title = message.text.strip()
    msg = bot.send_message(message.chat.id, "Send task link:")
    bot.register_next_step_handler(msg, save_task, title)

def save_task(message, title):
    link = message.text.strip()
    task_id = str(len(tasks) + 1)
    tasks[task_id] = {"title": title, "link": link}
    safe_save(DATA_FILES["tasks"], tasks)
    bot.send_message(message.chat.id, "✅ Task added successfully!")

@bot.message_handler(func=lambda m: m.text == "🗑 Remove Task")
def remove_task(message):
    if message.chat.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, "Send Task ID to remove:")
    bot.register_next_step_handler(msg, delete_task)

def delete_task(message):
    task_id = message.text.strip()
    if task_id in tasks:
        del tasks[task_id]
        safe_save(DATA_FILES["tasks"], tasks)
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
    # iterate on a snapshot of keys to avoid runtime change issues
    for pid in list(pending.keys()):
        item = pending.get(pid)
        if not item:
            continue
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✔ Approve", callback_data=f"ok_{pid}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"no_{pid}")
        )
        try:
            bot.send_photo(message.chat.id, item["file_id"],
                           caption=f"Pending ID: {pid}\nUser: {item['user']}\nTask: {item['task']}",
                           reply_markup=markup)
        except Exception:
            # could be file not present or invalid file id, just send message
            bot.send_message(message.chat.id, f"Pending ID: {pid}\nUser: {item['user']}\nTask: {item['task']}", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ok_") or c.data.startswith("no_"))
def handle_approval(call):
    pid = call.data.split("_",1)[1]
    if pid not in pending:
        bot.answer_callback_query(call.id, "Already processed.")
        return
    entry = pending[pid]
    user_key = str(entry["user"])
    lang = get_lang(entry["user"])
    if call.data.startswith("ok_"):
        # award point
        users[user_key]["points"] = users[user_key].get("points", 0) + 1
        safe_save(DATA_FILES["users"], users)
        try:
            bot.send_message(entry["user"], "🎉 Your screenshot has been approved! +1 point")
        except Exception:
            pass
        try:
            bot.edit_message_caption("Approved ✔", call.message.chat.id, call.message.message_id)
        except Exception:
            pass
    else:
        try:
            bot.send_message(entry["user"], "❌ Your screenshot was rejected.")
        except Exception:
            pass
        try:
            bot.edit_message_caption("Rejected ❌", call.message.chat.id, call.message.message_id)
        except Exception:
            pass
    # remove pending
    try:
        del pending[pid]
        safe_save(DATA_FILES["pending"], pending)
    except Exception:
        pass
    bot.answer_callback_query(call.id, "Processed.")

# ------------------ Start keep_alive and bot (main) ------------------
def run_polling():
    # small retry loop to keep bot alive on startup errors
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print("Polling error:", e)
            traceback.print_exc()
            sleep(5)  # retry after short delay

if __name__ == "__main__":
    # start keep_alive webserver (safe even if file missing)
    try:
        keep_alive()
    except Exception:
        pass

    print("BOT IS RUNNING...")
    # run polling in main thread (blocking) with exception/retry loop
    run_polling()
