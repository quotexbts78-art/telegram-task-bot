import telebot
from telebot import types
import os
import json

# -------------------------------------
# ENVIRONMENT VARIABLES (Render.com)
# -------------------------------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not TOKEN:
    raise RuntimeError("Missing TOKEN environment variable.")

if not ADMIN_ID:
    raise RuntimeError("Missing ADMIN_ID environment variable.")

ADMIN_ID = int(ADMIN_ID)

bot = telebot.TeleBot(TOKEN)

# -------------------------------------
# JSON FILE HANDLING
# -------------------------------------

def load_json(filename):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write("{}")
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

users = load_json("users.json")
tasks = load_json("tasks.json")
pending = load_json("pending.json")

# -------------------------------------
# USER REGISTRATION
# -------------------------------------

def register_user(user_id):
    if str(user_id) not in users:
        users[str(user_id)] = {
            "points": 0,
            "language": "Hindi",
            "withdraw": []
        }
        save_json("users.json", users)

# -------------------------------------
# MAIN MENU
# -------------------------------------

def main_menu(lang):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if lang == "Hindi":
        markup.add("📋 Tasks", "💰 Balance")
        markup.add("📤 Withdraw", "🌐 Language")
    else:
        markup.add("📋 Tasks", "💰 Balance")
        markup.add("📤 Withdraw", "🌐 Language")
    return markup

# -------------------------------------
# START COMMAND
# -------------------------------------

@bot.message_handler(commands=['start'])
def start(message):
    register_user(message.chat.id)
    lang = users[str(message.chat.id)]["language"]
    bot.send_message(message.chat.id,
                     "👋 Welcome! Choose an option:",
                     reply_markup=main_menu(lang))

# -------------------------------------
# LANGUAGE CHANGE
# -------------------------------------

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
    bot.answer_callback_query(call.id, "Language updated!")
    bot.edit_message_text("Language updated successfully!",
                          call.message.chat.id,
                          call.message.message_id)

# -------------------------------------
# SHOW BALANCE
# -------------------------------------

@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def balance(message):
    user_id = str(message.chat.id)
    pts = users[user_id]["points"]
    bot.send_message(message.chat.id, f"💰 Your Balance: {pts} points")

# -------------------------------------
# TASKS LIST
# -------------------------------------

@bot.message_handler(func=lambda m: m.text == "📋 Tasks")
def show_tasks(message):
    if len(tasks) == 0:
        bot.send_message(message.chat.id, "No tasks available right now.")
        return

    for task_id, task in tasks.items():
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔗 Open Link", url=task["link"]),
            types.InlineKeyboardButton("📤 Upload Screenshot",
                                       callback_data=f"upload_{task_id}")
        )
        bot.send_message(message.chat.id,
                         f"📝 Task: {task['title']}\n"
                         f"Reward: +1 point",
                         reply_markup=markup)

# -------------------------------------
# HANDLE SCREENSHOT UPLOAD
# -------------------------------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("upload_"))
def ask_screenshot(call):
    task_id = call.data.split("_")[1]
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
                           "Please upload the screenshot:")
    bot.register_next_step_handler(msg, receive_screenshot, task_id)

def receive_screenshot(message, task_id):
    if message.content_type != 'photo':
        bot.send_message(message.chat.id, "❌ Please send an image only.")
        return

    file_id = message.photo[-1].file_id

    pending_item = {
        "user": message.chat.id,
        "task": task_id,
        "file_id": file_id
    }

    pending_id = str(len(pending) + 1)
    pending[pending_id] = pending_item
    save_json("pending.json", pending)

    bot.send_message(message.chat.id, "⌛ Screenshot submitted for approval.")

    # Notify Admin
    bot.send_message(ADMIN_ID,
                     f"📥 New submission pending\nUser: {message.chat.id}\nTask: {task_id}")

# -------------------------------------
# WITHDRAW OPTION
# -------------------------------------

@bot.message_handler(func=lambda m: m.text == "📤 Withdraw")
def withdraw(message):
    msg = bot.send_message(message.chat.id, "Enter your UPI ID:")
    bot.register_next_step_handler(msg, save_withdraw)

def save_withdraw(message):
    user = str(message.chat.id)
    upi = message.text

    users[user]["withdraw"].append(upi)
    save_json("users.json", users)

    bot.send_message(message.chat.id, "✅ Withdraw request sent to admin!")

    bot.send_message(ADMIN_ID,
                     f"💸 New withdraw request\nUser: {user}\nUPI: {upi}")

# -------------------------------------
# ADMIN PANEL
# -------------------------------------

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != ADMIN_ID:
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Add Task", "🗑 Remove Task")
    markup.add("✔ Approve Screenshots", "📊 Users")
    markup.add("⬅ Back")
    bot.send_message(message.chat.id, "Admin Panel:", reply_markup=markup)

# -------------------------------------
# ADD TASK (ADMIN)
# -------------------------------------

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

# -------------------------------------
# REMOVE TASK
# -------------------------------------

@bot.message_handler(func=lambda m: m.text == "🗑 Remove Task")
def remove_task(message):
    if message.chat.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id,
                           "Send Task ID to remove:")
    bot.register_next_step_handler(msg, delete_task)

def delete_task(message):
    task_id = message.text
    if task_id in tasks:
        del tasks[task_id]
        save_json("tasks.json", tasks)
        bot.send_message(message.chat.id, "❌ Task removed.")
    else:
        bot.send_message(message.chat.id, "Invalid Task ID.")

# -------------------------------------
# APPROVE SCREENSHOTS
# -------------------------------------

@bot.message_handler(func=lambda m: m.text == "✔ Approve Screenshots")
def approve_panel(message):
    if message.chat.id != ADMIN_ID:
        return

    if len(pending) == 0:
        bot.send_message(message.chat.id, "No pending submissions.")
        return

    for pid, item in pending.items():
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

    if call.data.startswith("ok"):
        users[user]["points"] += 1
        save_json("users.json", users)
        bot.send_message(user, "🎉 Your screenshot has been approved! +1 point")
        bot.edit_message_caption("Approved ✔", call.message.chat.id, call.message.message_id)
    else:
        bot.send_message(user, "❌ Your screenshot was rejected.")
        bot.edit_message_caption("Rejected ❌", call.message.chat.id, call.message.message_id)

    del pending[pid]
    save_json("pending.json", pending)

# -------------------------------------
# BOT LOOP
# -------------------------------------

print("BOT IS RUNNING...")
bot.infinity_polling()
    
