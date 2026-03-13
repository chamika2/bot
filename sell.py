import asyncio
import logging
import sqlite3
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ================= ⚙️ CONFIGURATIONS =================
API_TOKEN = '8628254740:AAG9nvBN2wVCW7tM6YXzBOrb7eMUnWIsXfI'
ADMIN_ID = 6221106415  # ඔයාගේ Telegram ID එක
ADMIN_USERNAME = "prasa_z" 
CHANNEL_ID =  -1003131855993 
CHANNEL_LINK = "https://t.me/sni_hunter"

# ================= 🗄️ DATABASE SETUP =================
DB_NAME = 'v2ray_store.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    return conn

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, ref_by INTEGER, ref_count INTEGER DEFAULT 0)')
cursor.execute('CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, photo_id TEXT, caption TEXT, status TEXT DEFAULT "Available")')
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
    importing_db = State()

# ================= 🛠️ HELPER FUNCTIONS =================
def ensure_user(user_id):
    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (user_id, ref_count) VALUES (?, 0)", (user_id,))
        conn.commit()

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
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Add New File"), KeyboardButton(text="🗑️ Remove File")],
        [KeyboardButton(text="🔄 Change Status"), KeyboardButton(text="📢 Broadcast")],
        [KeyboardButton(text="📤 Export DB"), KeyboardButton(text="📥 Import DB")],
        [KeyboardButton(text="🏠 Back to User Menu")]
    ], resize_keyboard=True)

# ================= 🛡️ SUBSCRIPTION CHECK =================
async def is_subscribed(user_id):
    if user_id == ADMIN_ID: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

# ================= 👤 USER HANDLERS =================

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not cursor.fetchone():
        args = message.text.split()
        ref_by = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        cursor.execute("INSERT INTO users (user_id, ref_by, ref_count) VALUES (?, ?, 0)", (user_id, ref_by))
        if ref_by and ref_by != user_id:
            cursor.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id=?", (ref_by,))
            try: await bot.send_message(ref_by, "🎉 අලුත් Referral කෙනෙක් සම්බන්ධ වුණා!")
            except: pass
        conn.commit()

    if not await is_subscribed(user_id):
        btn = InlineKeyboardBuilder()
        btn.row(InlineKeyboardButton(text="📢 Join Our Channel", url=CHANNEL_LINK))
        btn.row(InlineKeyboardButton(text="🔄 Check Subscription", callback_data="check_sub"))
        await message.answer("⚠️ **Bot භාවිතා කිරීමට පෙර අපගේ Channel එකට සම්බන්ධ වන්න!**", reply_markup=btn.as_markup())
        return
    await message.answer("👋 **V2Ray Store එකට සාදරයෙන් පිළිගනිමු!**", reply_markup=main_menu(user_id))

@dp.callback_query(F.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    if await is_subscribed(call.from_user.id):
        ensure_user(call.from_user.id)
        await call.message.delete()
        await call.message.answer("✅ ස්තූතියි! දැන් ඔබට Bot භාවිතා කළ හැක.", reply_markup=main_menu(call.from_user.id))
    else:
        await call.answer("❌ ඔබ තවමත් Channel එකට Join වී නැත!", show_alert=True)

@dp.message(F.text == "💎 Available Files")
async def show_files(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    ensure_user(message.from_user.id)
    cursor.execute("SELECT id, photo_id, caption, status FROM files")
    files = cursor.fetchall()
    if not files: return await message.answer("😔 දැනට කිසිදු File එකක් නොමැත.")
    for f_id, photo, cap, status in files:
        emoji = "✅" if status == "Available" else "❌"
        btn = InlineKeyboardBuilder()
        if status == "Available":
            btn.button(text="🛒 Buy Now", url=f"https://t.me/{ADMIN_USERNAME}?text=I_want_to_buy_ID_{f_id}")
        else: btn.button(text="🚫 Out of Stock", callback_data="none")
        await message.answer_photo(photo=photo, caption=f"🆔 ID: {f_id}\n📌 {cap}\n\n📊 Status: {emoji} {status}", reply_markup=btn.as_markup())

@dp.message(F.text == "🔗 My Referral")
async def my_referral(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    ensure_user(message.from_user.id)
    cursor.execute("SELECT ref_count FROM users WHERE user_id=?", (message.from_user.id,))
    count = cursor.fetchone()[0]
    bot_me = await bot.get_me()
    await message.answer(f"🔗 **ඔබේ Link:** `https://t.me/{bot_me.username}?start={message.from_user.id}`\n👥 Referrals: **{count}**", parse_mode="Markdown")

@dp.message(F.text == "🎁 Get Free File")
async def get_free(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    ensure_user(message.from_user.id)
    cursor.execute("SELECT ref_count FROM users WHERE user_id=?", (message.from_user.id,))
    count = cursor.fetchone()[0]
    if count >= 10:
        await message.answer("🎉 10 සම්පූර්ණයි! පහත button එක ඔබා Free File එක ඉල්ලන්න.", 
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎁 Request Now", url=f"https://t.me/{ADMIN_USERNAME}?text=Free_File_ID_{message.from_user.id}")]]))
    else: await message.answer(f"❌ තවම referrals {10-count} ක් අවශ්‍යයි.")

@dp.message(F.text == "🆘 Support")
async def support(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="👨‍💻 Contact Admin", url=f"https://t.me/prasa_z"))
    await message.answer("ඕනෑම ගැටලුවකදී අපව සම්බන්ධ කරගන්න: 👇", reply_markup=kb.as_markup())

# ================= 👨‍✈️ ADMIN HANDLERS (DB BACKUP & RESTORE) =================

@dp.message(F.text == "⚙️ Admin Panel")
async def admin_p(message: types.Message):
    if message.from_user.id == ADMIN_ID: 
        await message.answer("⚙️ Admin Panel එකට සාදරයෙන් පිළිගනිමු.", reply_markup=admin_menu())

@dp.message(F.text == "📤 Export DB")
async def export_db(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        db_file = FSInputFile(DB_NAME)
        await message.answer_document(db_file, caption="📂 මෙය ඔබේ පරණ Users සහ Files සහිත Database එකයි. මෙය ආරක්ෂිතව තබාගන්න.")

@dp.message(F.text == "📥 Import DB")
async def import_db_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("📥 කරුණාකර පරණ `v2ray_store.db` file එක දැන් මට එවන්න.")
        await state.set_state(AdminStates.importing_db)

@dp.message(AdminStates.importing_db, F.document)
async def import_db_process(message: types.Message, state: FSMContext):
    if message.document.file_name == DB_NAME:
        file_info = await bot.get_file(message.document.file_id)
        await bot.download_file(file_info.file_path, DB_NAME)
        await message.answer("✅ Database එක සාර්ථකව Restore කළා! දැන් කරුණාකර Bot ව Restart කරන්න.", reply_markup=admin_menu())
        await state.clear()
    else:
        await message.answer(f"❌ වැරදි File එකක්. කරුණාකර `{DB_NAME}` නම සහිත file එකම එවන්න.")

# (අනෙකුත් Admin handlers - Add/Remove/Status/Broadcast) - ඉඩ මදි නිසා සාරාංශ කර ඇත
@dp.message(F.text == "➕ Add New File")
async def add_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("📸 Photo එක එවන්න."); await state.set_state(AdminStates.adding_photo)

@dp.message(AdminStates.adding_photo, F.photo)
async def add_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await message.answer("📝 Caption එක එවන්න."); await state.set_state(AdminStates.adding_caption)

@dp.message(AdminStates.adding_caption)
async def add_done(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("INSERT INTO files (photo_id, caption) VALUES (?, ?)", (data['photo_id'], message.text))
    conn.commit(); await state.clear(); await message.answer("✅ සාර්ථකයි!", reply_markup=admin_menu())

@dp.message(F.text == "🗑️ Remove File")
async def remove_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        cursor.execute("SELECT id, caption FROM files"); files = cursor.fetchall()
        txt = "\n".join([f"ID: {f[0]} | {f[1][:15]}..." for f in files])
        await message.answer(f"ID එක එවන්න:\n\n{txt}"); await state.set_state(AdminStates.removing_file)

@dp.message(AdminStates.removing_file)
async def remove_done(message: types.Message, state: FSMContext):
    cursor.execute("DELETE FROM files WHERE id=?", (message.text,))
    conn.commit(); await state.clear(); await message.answer("✅ මැකුවා!", reply_markup=admin_menu())

@dp.message(F.text == "🔄 Change Status")
async def status_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("ID එක එවන්න."); await state.set_state(AdminStates.changing_status)

@dp.message(AdminStates.changing_status)
async def status_done(message: types.Message, state: FSMContext):
    cursor.execute("SELECT status FROM files WHERE id=?", (message.text,))
    res = cursor.fetchone()
    if res:
        new = "Out of Stock" if res[0] == "Available" else "Available"
        cursor.execute("UPDATE files SET status=? WHERE id=?", (new, message.text))
        conn.commit(); await message.answer(f"✅ වෙනස් කළා.")
    await state.clear()

@dp.message(F.text == "📢 Broadcast")
async def broad_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("පණිවිඩය එවන්න."); await state.set_state(AdminStates.broadcasting)

@dp.message(AdminStates.broadcasting)
async def broad_done(message: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users")
    for row in cursor.fetchall():
        try: await message.copy_to(chat_id=row[0])
        except: pass
    await message.answer("✅ නිමයි!"); await state.clear()

@dp.message(F.text == "🏠 Back to User Menu")
async def back(message: types.Message, state: FSMContext):
    await state.clear(); await message.answer("🏠 Main Menu", reply_markup=main_menu(message.from_user.id))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
