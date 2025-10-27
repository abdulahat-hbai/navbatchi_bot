import os
import json
import random
from datetime import datetime, timedelta, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from dotenv import load_dotenv
import os


# Fayllar
DATA_FILE = 'navbat_data.json'
CONFIG_FILE = 'config.json'
EDIT_USER, EDIT_DURATION = range(2)


class NavbatBot:
    def __init__(self):
        self.data = self.load_data()
        self.config = self.load_config()
        if 'duty_history' not in self.data:
            self.data['duty_history'] = []

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        config = {'admins': [], 'duty_duration_days': 7}
        self.save_config(config)
        return config

    def save_config(self, config=None):
        if config:
            self.config = config
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def load_data(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'users': [], 'available_users': [], 'current_duty': [], 'next_duty_date': None, 'duty_history': []}

    def save_data(self):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def is_admin(self, user_id):
        return user_id in self.config['admins']

    def add_user(self, user_id, username, first_name):
        existing = next((u for u in self.data['users'] if u['id'] == user_id), None)
        if existing:
            if existing not in self.data['available_users']:
                self.data['available_users'].append(existing)
            self.save_data()
            return False
        user = {'id': user_id, 'username': username or '', 'first_name': first_name or 'Foydalanuvchi', 'joined_date': datetime.now().isoformat()}
        self.data['users'].append(user)
        self.data['available_users'].append(user)
        self.save_data()
        return True

    def remove_user(self, user_id):
        for key in ['users', 'available_users', 'current_duty']:
            self.data[key] = [u for u in self.data[key] if u['id'] != user_id]
        self.save_data()

    def edit_user(self, user_id, new_name):
        for section in ['users', 'available_users', 'current_duty']:
            for user in self.data[section]:
                if user['id'] == user_id:
                    user['first_name'] = new_name
        self.save_data()

    def select_duty_officers(self):
        if not self.data['available_users']:
            self.data['available_users'] = self.data['users'].copy()
        selected = random.sample(self.data['available_users'], min(2, len(self.data['available_users'])))
        self.data['available_users'] = [u for u in self.data['available_users'] if u['id'] not in [s['id'] for s in selected]]
        self.data['current_duty'] = selected
        next_date = datetime.now() + timedelta(days=self.config['duty_duration_days'])
        self.data['next_duty_date'] = next_date.isoformat()
        self.data['duty_history'].append({'date': datetime.now().isoformat(), 'officers': selected})
        self.save_data()
        return selected

    def get_user_display_name(self, user):
        return f"@{user['username']}" if user.get('username') else user.get('first_name', 'Foydalanuvchi')

    def get_user_by_id(self, user_id):
        return next((u for u in self.data['users'] if u['id'] == user_id), None)


navbat_bot = NavbatBot()

def get_main_keyboard(user_id):
    if navbat_bot.is_admin(user_id):
        keyboard = [
            [KeyboardButton("➕ Qo'shilish"), KeyboardButton("👥 A'zolar")],
            [KeyboardButton("📋 Hozirgi navbat"), KeyboardButton("🎲 Yangi navbat")],
            [KeyboardButton("⚙️ Admin panel"), KeyboardButton("❌ Chiqish")]
        ]
    else:
        keyboard = [[KeyboardButton("➕ Qo'shilish"), KeyboardButton("📋 Hozirgi navbat")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    is_admin = navbat_bot.is_admin(user_id)
    text = f"🤖 <b>Navbat Bot</b>ga xush kelibsiz!\n👋 Salom, {first_name}!"
    if is_admin:
        text += "\n\n👑 Siz adminsiz!"
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=get_main_keyboard(user_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    user_id, username, first_name = user.id, user.username, user.first_name

    if text == "➕ Qo'shilish":
        added = navbat_bot.add_user(user_id, username, first_name)
        msg = "✅ Ro'yxatga qo'shildingiz!" if added else "ℹ️ Siz allaqachon ro'yxatdasiz!"
        await update.message.reply_text(msg, parse_mode='HTML', reply_markup=get_main_keyboard(user_id))

    elif text == "📋 Hozirgi navbat":
        if navbat_bot.data['current_duty']:
            duty_list = '\n'.join([f"{'👑' if i == 0 else '⭐'} {navbat_bot.get_user_display_name(u)}" for i, u in enumerate(navbat_bot.data['current_duty'])])
            next_date = navbat_bot.data.get('next_duty_date')
            if next_date:
                dt = datetime.fromisoformat(next_date)
                days_left = (dt - datetime.now()).days
                date_text = f"\n📅 Tugash sanasi: <b>{dt.strftime('%d.%m.%Y')}</b>\n⏰ Qolgan kun: <b>{days_left}</b>"
            else:
                date_text = ""
            await update.message.reply_text(f"👥 <b>Joriy navbatchilar:</b>\n\n{duty_list}{date_text}", parse_mode='HTML')
        else:
            await update.message.reply_text("❌ Navbatchilar hali tayinlanmagan.", parse_mode='HTML')

    elif text == "🎲 Yangi navbat":
        if not navbat_bot.is_admin(user_id):
            await update.message.reply_text("❌ Bu faqat adminlar uchun.", parse_mode='HTML')
            return
        selected = navbat_bot.select_duty_officers()
        duty_list = '\n'.join([f"{'👑' if i == 0 else '⭐'} {navbat_bot.get_user_display_name(u)}" for i, u in enumerate(selected)])
        next_date = datetime.fromisoformat(navbat_bot.data['next_duty_date'])
        await update.message.reply_text(f"🎉 <b>Yangi navbatchilar tanlandi!</b>\n\n{duty_list}\n📅 Tugash: <b>{next_date.strftime('%d.%m.%Y')}</b>", parse_mode='HTML')

    elif text == "👥 A'zolar" and navbat_bot.is_admin(user_id):
        members = '\n'.join([f"{i+1}. {navbat_bot.get_user_display_name(u)}" for i, u in enumerate(navbat_bot.data['users'])])
        await update.message.reply_text(f"👥 <b>A'zolar:</b>\n{members}", parse_mode='HTML')

    elif text == "⚙️ Admin panel" and navbat_bot.is_admin(user_id):
        await show_admin_panel(update, context)

    elif text == "❌ Chiqish":
        navbat_bot.remove_user(user_id)
        await update.message.reply_text("✅ Siz chiqdingiz.", parse_mode='HTML')

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👥 Foydalanuvchilar ro‘yxati", callback_data="admin_users")],
        [InlineKeyboardButton("🧭 Navbatchilikni qo‘lda belgilash", callback_data="manual_duty")],
        [InlineKeyboardButton("⬅️ Ortga", callback_data="back_main")]
    ]
    await update.message.reply_text("⚙️ <b>Admin panel</b>\nQuyidagilardan birini tanlang:", parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "admin_users":
        users = navbat_bot.data['users']
        if not users:
            await query.edit_message_text("❌ Foydalanuvchilar yo‘q.")
            return
        keyboard = [[InlineKeyboardButton(f"{u['first_name']} (@{u.get('username','')})", callback_data=f"edit_user_{u['id']}")] for u in users]
        keyboard.append([InlineKeyboardButton("⬅️ Ortga", callback_data="back_admin")])
        await query.edit_message_text("👥 Foydalanuvchilar ro‘yxati:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("edit_user_"):
        target_id = int(data.split("_")[2])
        target_user = navbat_bot.get_user_by_id(target_id)
        if not target_user:
            await query.edit_message_text("⚠️ Topilmadi.")
            return
        keyboard = [
            [InlineKeyboardButton("✏️ Ismini tahrirlash", callback_data=f"rename_{target_id}")],
            [InlineKeyboardButton("🗑 O‘chirish", callback_data=f"delete_{target_id}")],
            [InlineKeyboardButton("⬅️ Ortga", callback_data="admin_users")]
        ]
        await query.edit_message_text(f"👤 {target_user['first_name']} (@{target_user.get('username','')})", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("delete_"):
        uid = int(data.split("_")[1])
        navbat_bot.remove_user(uid)
        await query.edit_message_text("🗑 Foydalanuvchi o‘chirildi.")

    elif data.startswith("rename_"):
        uid = int(data.split("_")[1])
        context.user_data['edit_user'] = uid
        await query.edit_message_text("✏️ Yangi ismni yuboring:")
        return EDIT_USER

    elif data == "manual_duty":
        users = navbat_bot.data['users']
        if not users:
            await query.edit_message_text("⚠️ Foydalanuvchilar yo‘q.")
            return
        keyboard = [[InlineKeyboardButton(f"{u['first_name']}", callback_data=f"choose_duty_{u['id']}")] for u in users]
        keyboard.append([InlineKeyboardButton("✅ Tugatish", callback_data="finish_manual")])
        context.user_data['manual_duty'] = []
        await query.edit_message_text("🧭 Navbatchilarni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("choose_duty_"):
        uid = int(data.split("_")[2])
        if 'manual_duty' not in context.user_data:
            context.user_data['manual_duty'] = []
        if uid not in context.user_data['manual_duty']:
            context.user_data['manual_duty'].append(uid)
        await query.answer("✅ Tanlandi!")

    elif data == "finish_manual":
        selected_ids = context.user_data.get('manual_duty', [])
        selected_users = [navbat_bot.get_user_by_id(uid) for uid in selected_ids]
        navbat_bot.data['current_duty'] = selected_users
        navbat_bot.data['duty_history'].append({'date': datetime.now().isoformat(), 'officers': selected_users})
        navbat_bot.save_data()
        await query.edit_message_text("✅ Qo‘lda navbatchilar belgilandi:\n" + '\n'.join([u['first_name'] for u in selected_users]))

async def duty_reminder(context: ContextTypes.DEFAULT_TYPE):
    if not navbat_bot.data['current_duty']:
        return
    for user in navbat_bot.data['current_duty']:
        try:
            await context.bot.send_message(chat_id=user['id'], text="🔔 Bugun sizning navbatchilik kuningiz 💪")
        except Exception as e:
            print("Xato:", e)

def main():
    load_dotenv()  
    TOKEN = os.getenv("BOT_TOKEN") 
    if not TOKEN:
        print("❌ BOT_TOKEN topilmadi. .env faylni tekshiring.")
        return


    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Har kuni 9:00 da eslatma
    job_queue = app.job_queue
    job_queue.run_daily(duty_reminder, time=time(hour=9, minute=0), days=(1, 3, 5))

    print("✅ Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
