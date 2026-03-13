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
API_TOKEN = '8370578722:AAHm1POdG3teNLxYmmTQPdRzEiyrg_49HxU'
ADMIN_ID = 123456789  # ඔයාගේ Telegram User ID එක
ADMIN_USERNAME = "prasa_z" # ඔයාගේ Telegram Username එක (උදා: @ නැතුව)
GROUP_ID = --1003131855993 # ඔයාගේ Group එකේ ID එක (Force Subscribe සඳහා)
GROUP_LINK = "https://t.me/sni_hunter"

# ================= 🗄️ DATABASE SETUP =================
conn = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, ref_by INTEGER, ref_count INTEGER DEFAULT 0)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS files 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, photo_id TEXT, caption TEXT, status TEXT DEFAULT 'Available')''')
conn.commit()

# ================= 🤖 BOT & DISPATCHER =================
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# ================= 📝 STATES FOR ADMIN =================
class AdminStates(StatesGroup):
    adding_photo = State()
    adding_caption = State()
    broadcasting = State()
    removing_file = State()
    changing_status = State()

# ================= 🎛️ KEYBOARDS =================
def main_menu(user_id):
    kb = [[KeyboardButton(text="💎 Available Files"), KeyboardButton(text="🔗 My Referral")],
          [KeyboardButton(text="🎁 Get Free File"), KeyboardButton(text="🆘 Support")]]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_menu():
    kb = [[KeyboardButton(text="➕ Add New File"), KeyboardButton(text="🗑️ Remove File")],
          [KeyboardButton(text="🔄 Change Status"), KeyboardButton(text="📢 Broadcast")],
          [KeyboardButton(text="🏠 Back to User Menu")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def force_sub_kb():
    btn = InlineKeyboardBuilder()
    btn.button(text="📢 Join Our Group", url=GROUP_LINK)
    btn.button(text="🔄 Check Subscription", callback_data="check_sub")
    return btn.as_markup()

# ================= 🛡️ FORCE SUBSCRIBE CHECK =================
async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# ================= 👤 USER HANDLERS =================

@dp.message(CommandStart())
async def start_cmd(message: types.Message, command: CommandStart):
    user_id = message.from_user.id
    
    # Check if new user & handle referral
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        args = message.text.split()
        ref_by = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        
        cursor.execute("INSERT INTO users (user_id, ref_by) VALUES (?, ?)", (user_id, ref_by))
        if ref_by and ref_by != user_id:
            cursor.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id=?", (ref_by,))
            conn.commit()
            
            # Notify referrer
            cursor.execute("SELECT ref_count FROM users WHERE user_id=?", (ref_by,))
            count = cursor.fetchone()[0]
            try:
                await bot.send_message(ref_by, f"🎉 අලුත් කෙනෙක් ඔයාගේ ලින්ක් එකෙන් join වුණා! (Total: {count}/10)")
                if count == 10:
                    await bot.send_message(ref_by, "🎁 සුභපැතුම්! ඔයාගේ referrals 10 සම්පූර්ණයි. '🎁 Get Free File' ඔබන්න.")
            except: pass
        conn.commit()

    if not await is_subscribed(user_id):
        await message.answer("⚠️ **Bot භාවිතා කිරීමට පෙර අපගේ Group එකට සම්බන්ධ වන්න!**", reply_markup=force_sub_kb())
        return

    await message.answer("👋 **V2Ray Store එකට සාදරයෙන් පිළිගනිමු!**\nපහත මෙනුවෙන් අවශ්‍ය සේවාව තෝරන්න.", reply_markup=main_menu(user_id))

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("✅ ස්තූතියි! දැන් ඔබට Bot භාවිතා කළ හැක.", reply_markup=main_menu(callback.from_user.id))
    else:
        await callback.answer("❌ ඔබ තවමත් Group එකට Join වී නැත!", show_alert=True)

@dp.message(F.text == "💎 Available Files")
async def show_files(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    
    cursor.execute("SELECT id, photo_id, caption, status FROM files")
    files = cursor.fetchall()
    
    if not files:
        await message.answer("😔 දැනට කිසිදු File එකක් Stock එකේ නොමැත.")
        return

    await message.answer("🛒 **දැනට ලබාගත හැකි V2Ray Files:**")
    for f in files:
        f_id, photo, cap, status = f
        emoji = "✅" if status == "Available" else "❌"
        
        btn = InlineKeyboardBuilder()
        if status == "Available":
            btn.button(text="🛒 Buy Now", url=f"https://t.me/{ADMIN_USERNAME}?text=Hello,%20I%20want%20to%20buy%20File%20ID:%20{f_id}")
        else:
            btn.button(text="🚫 Out of Stock", callback_data="ignore")

        await message.answer_photo(photo=photo, caption=f"🆔 ID: {f_id}\n📌 {cap}\n\n📊 Status: {emoji} {status}", reply_markup=btn.as_markup())

@dp.message(F.text == "🔗 My Referral")
async def my_referral(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT ref_count FROM users WHERE user_id=?", (user_id,))
    count = cursor.fetchone()[0]
    
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    msg = (f"🔗 **ඔබේ Referral Link එක:**\n`{ref_link}`\n\n"
           f"👥 දැනට සම්බන්ධ කර ඇති පිරිස: **{count}**\n\n"
           f"💡 තව අයව සම්බන්ද කරලා 10ක් වුනාම Free File එකක් ලබාගන්න!")
    await message.answer(msg, parse_mode="Markdown")

@dp.message(F.text == "🎁 Get Free File")
async def get_free_file(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT ref_count FROM users WHERE user_id=?", (user_id,))
    count = cursor.fetchone()[0]
    
    if count >= 10:
        # Reset count or let them keep it (Here we deduct 10)
        cursor.execute("UPDATE users SET ref_count = ref_count - 10 WHERE user_id=?", (user_id,))
        conn.commit()
        await message.answer("🎉 **සුභපැතුම්!** ඔබේ Free File එක ලබාගැනීමට පහත Button එක ඔබා Admin ට Message එකක් දාන්න.", 
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👨‍💻 Contact Admin for Free File", url=f"https://t.me/{ADMIN_USERNAME}?text=I%20completed%2010%20referrals!%20My%20ID:%20{user_id}")]]))
    else:
        await message.answer(f"❌ ඔබට තවමත් ප්‍රමාණවත් Referrals නැත. තව **{10 - count}** ක් අවශ්‍යයි.")

@dp.message(F.text == "🏠 Back to User Menu")
async def back_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Main Menu", reply_markup=main_menu(message.from_user.id))

# ================= 👨‍✈️ ADMIN HANDLERS =================

@dp.message(F.text == "⚙️ Admin Panel")
async def open_admin(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("⚙️ Admin Panel එකට සාදරයෙන් පිළිගනිමු.", reply_markup=admin_menu())

@dp.message(F.text == "➕ Add New File")
async def add_file_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("📸 අලුත් File එකේ Photo එක එවන්න.")
        await state.set_state(AdminStates.adding_photo)

@dp.message(AdminStates.adding_photo, F.photo)
async def add_file_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await message.answer("📝 දැන් File එකේ විස්තරය (Caption) එවන්න.")
    await state.set_state(AdminStates.adding_caption)

@dp.message(AdminStates.adding_caption)
async def add_file_caption(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("INSERT INTO files (photo_id, caption) VALUES (?, ?)", (data['photo_id'], message.text))
    conn.commit()
    await state.clear()
    await message.answer("✅ අලුත් File එක සාර්ථකව ඇතුළත් කළා!", reply_markup=admin_menu())
    
    # Broadcast new file notification
    cursor.execute("SELECT user_id FROM users")
    for row in cursor.fetchall():
        try:
            await bot.send_message(row[0], "🔔 **New File Available!**\nඅලුත් File එකක් දැන් Store එකට ඇතුලත් කර ඇත. 💎 Available Files මගින් පරීක්ෂා කරන්න.")
        except: pass

@dp.message(F.text == "🔄 Change Status")
async def change_status_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔄 වෙනස් කළ යුතු File එකේ ID එක එවන්න.")
        await state.set_state(AdminStates.changing_status)

@dp.message(AdminStates.changing_status)
async def change_status_process(message: types.Message, state: FSMContext):
    f_id = message.text
    cursor.execute("SELECT status FROM files WHERE id=?", (f_id,))
    res = cursor.fetchone()
    if res:
        new_status = "Out of Stock" if res[0] == "Available" else "Available"
        cursor.execute("UPDATE files SET status=? WHERE id=?", (new_status, f_id))
        conn.commit()
        await message.answer(f"✅ ID: {f_id} හි තත්වය '{new_status}' ලෙස වෙනස් විය.")
    else:
        await message.answer("❌ වැරදි ID එකක්!")
    await state.clear()

@dp.message(F.text == "🗑️ Remove File")
async def remove_file_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🗑️ මකා දැමිය යුතු File එකේ ID එක එවන්න.")
        await state.set_state(AdminStates.removing_file)

@dp.message(AdminStates.removing_file)
async def remove_file_process(message: types.Message, state: FSMContext):
    cursor.execute("DELETE FROM files WHERE id=?", (message.text,))
    conn.commit()
    await message.answer(f"✅ ID: {message.text} File එක සාර්ථකව මකා දැමුවා.")
    await state.clear()

@dp.message(F.text == "📢 Broadcast")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("📢 සියලුම Users ලට යැවිය යුතු Message එක (Photo/Text/HTML) එවන්න.")
        await state.set_state(AdminStates.broadcasting)

@dp.message(AdminStates.broadcasting)
async def broadcast_process(message: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users")
    count = 0
    for row in cursor.fetchall():
        try:
            await message.copy_to(chat_id=row[0])
            count += 1
        except: pass
    await message.answer(f"✅ සාර්ථකව {count} දෙනෙකුට Broadcast කරන ලදී.")
    await state.clear()

# ================= 🚀 START BOT =================
async def main():
    print("Bot is successfully running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())