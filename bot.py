# Telegram Task Bot (Modern UI, Multiple Tasks, Admin Panel)
# Replace YOUR_BOT_TOKEN and ADMIN_ID before running.

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
import json, os

TOKEN = "8535439788:AAHw1peDOOTIU0tZ7AWeS4A5xf2Zh1ttnNU"
ADMIN_ID = 6111048950
bot = telebot.TeleBot(TOKEN)

### Load / Save JSON ###
def load(file):
    if not os.path.exists(file):
        with open(file, 'w') as f: json.dump({}, f)
    return json.load(open(file))

def save(file, data):
    with open(file, 'w') as f: json.dump(data, f, indent=4)

users = load("users.json")
tasks = load("tasks.json")
pending = load("pending.json")

### START ###
@bot.message_handler(commands=['start'])
def start(msg):
    uid = str(msg.chat.id)
    if uid not in users:
        users[uid] = {"balance":0, "language":"Hindi"}
        save("users.json", users)

    menu = ReplyKeyboardMarkup(resize_keyboard=True)
    menu.add("📋 Tasks", "💰 Balance")
    menu.add("📤 Withdraw", "🌐 Language")
    bot.send_message(msg.chat.id, "Welcome! Choose an option:", reply_markup=menu)

### BALANCE ###
@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def bal(msg):
    uid = str(msg.chat.id)
    bot.send_message(msg.chat.id, f"Your balance: {users[uid]['balance']} Points")

### SHOW TASKS ###
@bot.message_handler(func=lambda m: m.text == "📋 Tasks")
def show_tasks(msg):
    if len(tasks) == 0:
        bot.send_message(msg.chat.id, "No tasks available.")
        return

    for tid, t in tasks.items():
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Open Link", url=t["link"]))
        kb.add(InlineKeyboardButton("Upload Screenshot", callback_data=f"upload_{tid}"))

        bot.send_message(msg.chat.id,
            f"🔗 **{t['title']}**\n👉 Open the link and upload screenshot.",
            reply_markup=kb,
            parse_mode="Markdown")

### USER UPLOAD SCREENSHOT ###
@bot.callback_query_handler(func=lambda c: c.data.startswith("upload_"))
def ask_ss(c):
    tid = c.data.split("_")[1]
    pending[str(c.message.chat.id)] = {"task": tid}
    save("pending.json", pending)
    bot.send_message(c.message.chat.id, "Upload screenshot now:")

@bot.message_handler(content_types=['photo'])
def photo(msg):
    uid = str(msg.chat.id)
    if uid not in pending:
        bot.send_message(msg.chat.id, "You do not have any pending task.")
        return

    task_id = pending[uid]["task"]
    if "submissions" not in pending[uid]: pending[uid]["submissions"] = []
    pending[uid]["submissions"].append("screenshot")

    save("pending.json", pending)

    bot.send_message(msg.chat.id, "Screenshot submitted! Waiting for admin approval.")
    bot.send_message(ADMIN_ID, f"User {uid} submitted screenshot for task {task_id}.")

### WITHDRAW ###
@bot.message_handler(func=lambda m: m.text == "📤 Withdraw")
def withdraw(msg):
    bot.send_message(msg.chat.id, "Enter your UPI ID:")
    bot.register_next_step_handler(msg, get_upi)

def get_upi(msg):
    upi = msg.text
    bot.send_message(ADMIN_ID, f"Withdraw request from {msg.chat.id}: {upi}")
    bot.send_message(msg.chat.id, "Withdrawal request sent.")

### LANGUAGE ###
@bot.message_handler(func=lambda m: m.text == "🌐 Language")
def lang(msg):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Hindi", callback_data="lang_hi"))
    kb.add(InlineKeyboardButton("English", callback_data="lang_en"))
    bot.send_message(msg.chat.id, "Choose language:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("lang_"))
def set_lang(c):
    uid = str(c.message.chat.id)
    users[uid]["language"] = "Hindi" if c.data.endswith("hi") else "English"
    save("users.json", users)
    bot.send_message(c.message.chat.id, "Language updated.")

### ADMIN PANEL ###
@bot.message_handler(commands=['admin'])
def admin(msg):
    if msg.chat.id != ADMIN_ID:
        return

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Add Task", "🗑 Remove Task")
    kb.add("✔ Approve Screenshots", "📊 Users")
    kb.add("📢 Broadcast")

    bot.send_message(msg.chat.id, "Admin Panel:", reply_markup=kb)

### ADD TASK ###
@bot.message_handler(func=lambda m: m.text == "➕ Add Task")
def add_task(msg):
    if msg.chat.id != ADMIN_ID: return
    bot.send_message(msg.chat.id, "Send task title:")
    bot.register_next_step_handler(msg, get_title)

def get_title(msg):
    title = msg.text
    bot.send_message(msg.chat.id, "Send task link:")
    bot.register_next_step_handler(msg, lambda m: save_task(m, title))

def save_task(msg, title):
    link = msg.text
    tid = str(len(tasks) + 1)

    tasks[tid] = {"title": title, "link": link}
    save("tasks.json", tasks)

    bot.send_message(msg.chat.id, "Task Added!")

### REMOVE TASK ###
@bot.message_handler(func=lambda m: m.text == "🗑 Remove Task")
def remove_task(msg):
    if msg.chat.id != ADMIN_ID: return

    if len(tasks) == 0:
        bot.send_message(msg.chat.id, "No tasks to remove.")
        return

    text = "Tasks:\n"
    for tid, t in tasks.items(): text += f"{tid}. {t['title']}\n"
    bot.send_message(msg.chat.id, text + "\nSend task ID to remove:")
    bot.register_next_step_handler(msg, delete_tid)

def delete_tid(msg):
    tid = msg.text.strip()
    if tid in tasks:
        del tasks[tid]
        save("tasks.json", tasks)
        bot.send_message(msg.chat.id, "Task Removed.")
    else:
        bot.send_message(msg.chat.id, "Invalid ID.")

### APPROVE SCREENSHOTS ###
@bot.message_handler(func=lambda m: m.text == "✔ Approve Screenshots")
def approve_panel(msg):
    if msg.chat.id != ADMIN_ID: return

    if len(pending) == 0:
        bot.send_message(msg.chat.id, "No pending screenshots.")
        return

    for uid, data in pending.items():
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Approve", callback_data=f"ok_{uid}"))
        kb.add(InlineKeyboardButton("Reject", callback_data=f"no_{uid}"))
        bot.send_message(msg.chat.id, f"User: {uid}\nTask: {data['task']}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ok_"))
def approve(c):
    uid = c.data.split("_")[1]
    users[uid]["balance"] += 1
    save("users.json", users)

    del pending[uid]
    save("pending.json", pending)

    bot.send_message(uid, "Screenshot Approved! +1 Point")
    bot.send_message(c.message.chat.id, "Approved.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("no_"))
def reject(c):
    uid = c.data.split("_")[1]
    del pending[uid]
    save("pending.json", pending)

    bot.send_message(uid, "Screenshot Rejected.")
    bot.send_message(c.message.chat.id, "Rejected.")

### USERS LIST ###
@bot.message_handler(func=lambda m: m.text == "📊 Users")
def show_users(msg):
    if msg.chat.id != ADMIN_ID: return

    text = "Users List:\n"
    for uid, u in users.items():
        text += f"{uid} — {u['balance']} Points\n"

    bot.send_message(msg.chat.id, text)

### BROADCAST ###
@bot.message_handler(func=lambda m: m.text == "📢 Broadcast")
def bc(msg):
    if msg.chat.id != ADMIN_ID: return

    bot.send_message(msg.chat.id, "Send message to broadcast:")
    bot.register_next_step_handler(msg, send_bc)

def send_bc(msg):
    for uid in users:
        try: bot.send_message(uid, msg.text)
        except: pass
    bot.send_message(msg.chat.id, "Broadcast sent.")

### RUN ###
bot.infinity_polling()
  
