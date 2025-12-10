# bot.py
import os
import json
from traceback import format_exc
from time import sleep
import telebot
from telebot import types

# ---------------- KEEP ALIVE (Render Recommended) -----------------
try:
    from keep_alive import keep_alive
except:
    def keep_alive():
        pass


# ---------------- ENVIRONMENT -----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not TOKEN:
    raise RuntimeError("Missing TOKEN environment variable.")
if not ADMIN_ID:
    raise RuntimeError("Missing ADMIN_ID environment variable.")

try:
    ADMIN_ID = int(ADMIN_ID)
except:
    raise RuntimeError("ADMIN_ID must be an integer.")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")


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
        # corrupted file → create new
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


# ---------------- TASKS SYSTEM ----------------
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

# Add Task
@bot.message_handler(func=lambda m: m.text == "➕ Add Task")
def add_task_title(message):
    if message.chat.id != ADMIN_ID: return
    msg = bot.send_message(message.chat.id, "Send task title:")
    bot.register_next_step_handler(msg, add_task_link)

def add_task_link(message):
    title = message.text.strip()
    msg = bot.send_message(message.chat.id, "Send task link:")
    bot.register_next_step_handler(msg, save_task, title)

def save_task(message, title):
    link = message.text.strip()
    tid = str(len(tasks) + 1)
    tasks[tid] = {"title": title, "link": link}
    safe_save(DATA_FILES["tasks"], tasks)
    bot.send_message(message.chat.id, "✅ Task added!")

# Remove Task
@bot.message_handler(func=lambda m: m.text == "🗑 Remove Task")
def remove_task(message):
    if message.chat.id != ADMIN_ID: return
    msg = bot.send_message(message.chat.id, "Send Task ID to delete:")
    bot.register_next_step_handler(msg, delete_task)

def delete_task(message):
    tid = message.text.strip()
    if tid in tasks:
        del tasks[tid]
        safe_save(DATA_FILES["tasks"], tasks)
        bot.send_message(message.chat.id, "❌ Task removed.")
    else:
        bot.send_message(message.chat.id, "Invalid Task ID.")

# Approve Screenshots
@bot.message_handler(func=lambda m: m.text == "✔ Approve Screenshots")
def approve_ss(message):
    if message.chat.id != ADMIN_ID:
        return

    if not pending:
        return bot.send_message(message.chat.id, "No pending submissions.")

    for pid, item in list(pending.items()):
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("✔ Approve", callback_data=f"ok_{pid}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"no_{pid}")
        )

        try:
            bot.send_photo(
                message.chat.id,
                item["file_id"],
                caption=f"ID: {pid}\nUser: {item['user']}\nTask: {item['task']}",
                reply_markup=kb
            )
        except:
            bot.send_message(
                message.chat.id,
                f"ID: {pid}\nUser: {item['user']}\nTask: {item['task']}",
                reply_markup=kb
            )

@bot.callback_query_handler(func=lambda c: c.data.startswith(("ok_", "no_")))
def approve_reject(call):
    pid = call.data.split("_")[1]

    if pid not in pending:
        return bot.answer_callback_query(call.id, "Already processed.")

    item = pending[pid]
    uid = str(item["user"])

    approved = call.data.startswith("ok_")

    if approved:
        users[uid]["points"] += 1
        safe_save(DATA_FILES["users"], users)
        bot.send_message(uid, "🎉 Screenshot approved! +1 point")
        new_caption = "Approved ✔"
    else:
        bot.send_message(uid, "❌ Screenshot rejected.")
        new_caption = "Rejected ❌"

    # Update admin message (safe)
    try:
        bot.edit_message_caption(
            caption=new_caption,
            chat_id=call.message.chat.id,
            message_id=call.message.id
        )
    except:
        pass

    del pending[pid]
    safe_save(DATA_FILES["pending"], pending)
    bot.answer_callback_query(call.id, "Processed.")


# ---------------- SAFE POLLING ----------------
def run_bot():
    bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)

# ---------------- START BOT ----------------
if __name__ == "__main__":
    keep_alive()
    print("BOT IS RUNNING...")
    run_bot()
