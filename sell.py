import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ================= ⚙️ CONFIGURATIONS =================
API_TOKEN = 'ඔයාගේ_BOT_TOKEN_එක_මෙතනට'
ADMIN_ID = 6221106415  # ඔයාගේ Telegram User ID එක
ADMIN_USERNAME = "prasa_z" # ඔයාගේ Username එක (@ නැතුව)
CHANNEL_ID = --1003131855993 # ඔයාගේ Channel එකේ ID එක (-100 සමඟ)
CHANNEL_LINK = "https://t.me/sni_hunter"

# ================= 🗄️ DATABASE SETUP =================
conn = sqlite3.connect('v2ray_store.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, ref_by INTEGER, ref_count INTEGER DEFAULT 0)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS files 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, photo_id TEXT, caption TEXT, status TEXT DEFAULT 'Available')''')
conn.commit()

# ================= 🤖 BOT SETUP =================
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

class AdminStates(StatesGroup):
    adding_photo = State()
    adding_caption = State()
    broadcasting = State()
    removing_file = State()
    changing_status = State()

# ================= 🎛️ KEYBOARDS =================
def main_menu(user_id):
    kb = [
        [KeyboardButton(text="💎 Available Files"), KeyboardButton(text="🔗 My Referral")],
        [KeyboardButton(text="🎁 Get Free File"), KeyboardButton(text="🆘 Support")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_menu():
    kb = [
        [KeyboardButton(text="➕ Add New File"), KeyboardButton(text="🗑️ Remove File")],
        [KeyboardButton(text="🔄 Change Status"), KeyboardButton(text="📢 Broadcast")],
        [KeyboardButton(text="🏠 Back to User Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def force_sub_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Join Our Channel", url=CHANNEL_LINK))
    builder.row(InlineKeyboardButton(text="🔄 Check Subscription", callback_data="check_sub"))
    return builder.as_markup()

# ================= 🛡️ SUBSCRIPTION CHECK =================
async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        # Status 'left' හෝ 'kicked' නොවේ නම් ඔහු member කෙනෙක්
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Sub Check Error: {e}")
        return False

# ================= 👤 USER HANDLERS =================

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    
    # Referral Logic
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not cursor.fetchone():
        args = message.text.split()
        ref_by = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        cursor.execute("INSERT INTO users (user_id, ref_by) VALUES (?, ?)", (user_id, ref_by))
        if ref_by and ref_by != user_id:
            cursor.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id=?", (ref_by,))
            try:
                await bot.send_message(ref_by, "🎉 අලුත් සාමාජිකයෙක් සම්බන්ධ වුණා!")
            except: pass
        conn.commit()

    if not await is_subscribed(user_id):
        await message.answer("⚠️ **Bot භාවිතා කිරීමට පෙර අපගේ Channel එකට සම්බන්ධ වන්න!**", reply_markup=force_sub_kb())
        return

    await message.answer("👋 **V2Ray Store එකට සාදරයෙන් පිළිගනිමු!**", reply_markup=main_menu(user_id))

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("✅ ස්තූතියි! දැන් ඔබට Bot භාවිතා කළ හැක.", reply_markup=main_menu(callback.from_user.id))
    else:
        await callback.answer("❌ ඔබ තවමත් Channel එකට Join වී නැත!", show_alert=True)

@dp.message(F.text == "💎 Available Files")
async def show_files(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    
    cursor.execute("SELECT id, photo_id, caption, status FROM files")
    files = cursor.fetchall()
    
    if not files:
        await message.answer("😔 දැනට කිසිදු File එකක් Stock එකේ නොමැත.")
        return

    for f_id, photo, cap, status in files:
        emoji = "✅" if status == "Available" else "❌"
        btn = InlineKeyboardBuilder()
        if status == "Available":
            btn.button(text="🛒 Buy Now", url=f"https://t.me/{ADMIN_USERNAME}?text=I_want_to_buy_ID_{f_id}")
        else:
            btn.button(text="🚫 Out of Stock", callback_data="none")
        
        await message.answer_photo(photo=photo, caption=f"🆔 ID: {f_id}\n📌 {cap}\n\n📊 Status: {emoji} {status}", reply_markup=btn.as_markup())

@dp.message(F.text == "🔗 My Referral")
async def my_referral(message: types.Message):
    cursor.execute("SELECT ref_count FROM users WHERE user_id=?", (message.from_user.id,))
    count = cursor.fetchone()[0]
    bot_user = await bot.get_me()
    ref_link = f"https://t.me/{bot_user.username}?start={message.from_user.id}"
    await message.answer(f"🔗 **ඔබේ Referral Link:**\n`{ref_link}`\n\n👥 සම්බන්ධ වූ පිරිස: **{count}**", parse_mode="Markdown")

@dp.message(F.text == "🎁 Get Free File")
async def get_free(message: types.Message):
    cursor.execute("SELECT ref_count FROM users WHERE user_id=?", (message.from_user.id,))
    count = cursor.fetchone()[0]
    if count >= 10:
        await message.answer("🎉 සුභපැතුම්! 10 සම්පූර්ණයි. Admin ට message එකක් දාන්න.", 
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👨‍💻 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}?text=Free_File_Request_ID_{message.from_user.id}")]]))
    else:
        await message.answer(f"❌ තව referrals {10-count} ක් අවශ්‍යයි.")

# ================= 👨‍✈️ ADMIN HANDLERS =================

@dp.message(F.text == "⚙️ Admin Panel")
async def admin_p(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("⚙️ Admin Panel", reply_markup=admin_menu())

@dp.message(F.text == "➕ Add New File")
async def add_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("📸 Photo එක එවන්න.")
        await state.set_state(AdminStates.adding_photo)

@dp.message(AdminStates.adding_photo, F.photo)
async def add_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await message.answer("📝 Caption එක එවන්න.")
    await state.set_state(AdminStates.adding_caption)

@dp.message(AdminStates.adding_caption)
async def add_done(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("INSERT INTO files (photo_id, caption) VALUES (?, ?)", (data['photo_id'], message.text))
    conn.commit()
    await state.clear()
    await message.answer("✅ සාර්ථකයි!", reply_markup=admin_menu())
    
    # Broadcast to all users
    cursor.execute("SELECT user_id FROM users")
    for row in cursor.fetchall():
        try: await bot.send_message(row[0], "🔔 **New File Available!**\nදැන්ම පරීක්ෂා කරන්න.")
        except: pass

@dp.message(F.text == "🔄 Change Status")
async def change_status_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔢 වෙනස් කළ යුතු File එකේ ID එක එවන්න.")
        await state.set_state(AdminStates.changing_status)

@dp.message(AdminStates.changing_status)
async def change_status_process(message: types.Message, state: FSMContext):
    cursor.execute("SELECT status FROM files WHERE id=?", (message.text,))
    res = cursor.fetchone()
    if res:
        new_status = "Out of Stock" if res[0] == "Available" else "Available"
        cursor.execute("UPDATE files SET status=? WHERE id=?", (new_status, message.text))
        conn.commit()
        await message.answer(f"✅ ID {message.text} තත්වය {new_status} ලෙස වෙනස් විය.")
    else:
        await message.answer("❌ ID එක වැරදියි.")
    await state.clear()

@dp.message(F.text == "📢 Broadcast")
async def broad_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("📢 පණිවිඩය එවන්න.")
        await state.set_state(AdminStates.broadcasting)

@dp.message(AdminStates.broadcasting)
async def broad_done(message: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users")
    for row in cursor.fetchall():
        try: await message.copy_to(chat_id=row[0])
        except: pass
    await message.answer("✅ නිමයි!")
    await state.clear()

@dp.message(F.text == "🏠 Back to User Menu")
async def back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Main Menu", reply_markup=main_menu(message.from_user.id))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
