import asyncio
import logging
import sqlite3
import random
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ================= ⚙️ CONFIGURATIONS (මෙහි වෙනස්කම් කරන්න) =================
API_TOKEN = '8205587502:AAEnWA_-TcEXm7qPyojU_7W04AmjTXxdCI8'
ADMIN_ID = 6221106415  # ඔයාගේ Telegram User ID එක
ADMIN_USERNAME = "prasa_z" # @ ලකුණ රහිතව
CHANNEL_ID = -1003131855993 # Force Subscribe අවශ්‍ය නම් Channel ID එක
CHANNEL_LINK = "https://t.me/sni_hunter"
DB_NAME = 'online_store_v2.db'

# ================= 🗄️ DATABASE SETUP =================
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()

def db_init():
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, is_verified INTEGER DEFAULT 0)')
    cursor.execute('CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, cat_id INTEGER, price REAL, desc TEXT, photo_id TEXT, stock INTEGER DEFAULT 1)')
    cursor.execute('CREATE TABLE IF NOT EXISTS cart (user_id INTEGER, prod_id INTEGER, qty INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, details TEXT, total REAL, name TEXT, phone TEXT, address TEXT, status TEXT DEFAULT "Pending")')
    conn.commit()

db_init()

# ================= 🤖 BOT SETUP =================
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.ERROR)

class AdminStates(StatesGroup):
    add_cat = State()
    add_prod_name = State()
    add_prod_price = State()
    add_prod_desc = State()
    add_prod_photo = State()
    broadcast = State()

class ShopStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_address = State()
    captcha = State()

# ================= 🎛️ KEYBOARDS =================
def get_main_kb(user_id):
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🛍️ Shop Now"), KeyboardButton(text="🛒 My Cart"))
    builder.row(KeyboardButton(text="📦 My Orders"), KeyboardButton(text="🆘 Support"))
    if user_id == ADMIN_ID:
        builder.row(KeyboardButton(text="⚙️ Admin Dashboard"))
    return builder.as_markup(resize_keyboard=True)

def get_admin_kb():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="➕ Add Category"), KeyboardButton(text="🎁 Add Product"))
    builder.row(KeyboardButton(text="📑 View Orders"), KeyboardButton(text="📊 Stats"))
    builder.row(KeyboardButton(text="📢 Broadcast"), KeyboardButton(text="🏠 Back to Shop"))
    return builder.as_markup(resize_keyboard=True)

# ================= 👤 USER HANDLERS =================

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    cursor.execute("SELECT is_verified FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, message.from_user.username))
        conn.commit()
    
    if not user or user[0] == 0:
        n1, n2 = random.randint(1, 12), random.randint(1, 12)
        await state.update_data(ans=n1+n2)
        await message.answer(f"🛡️ **Security Check**\n\nWelcome! Please solve this to continue: \n👉 **{n1} + {n2} = ?**")
        await state.set_state(ShopStates.captcha)
        return

    await message.answer(f"👋 Welcome to **{message.bot.get_me().full_name}**!\nHow can we help you today?", reply_markup=get_main_kb(user_id))

@dp.message(ShopStates.captcha)
async def captcha_verify(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if message.text == str(data.get('ans')):
        cursor.execute("UPDATE users SET is_verified=1 WHERE user_id=?", (message.from_user.id,))
        conn.commit()
        await message.answer("✅ Verification Successful!", reply_markup=get_main_kb(message.from_user.id))
        await state.clear()
    else:
        await message.answer("❌ Wrong answer, please try again.")

# --- SHOPPING ---

@dp.message(F.text == "🛍️ Shop Now")
async def show_cats(message: types.Message):
    cursor.execute("SELECT * FROM categories")
    cats = cursor.fetchall()
    if not cats: return await message.answer("😔 Sorry, no categories available right now.")
    
    kb = InlineKeyboardBuilder()
    for cat in cats:
        kb.button(text=cat[1], callback_data=f"cat_{cat[0]}")
    kb.adjust(2)
    await message.answer("📁 Choose a category to browse:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("cat_"))
async def show_prods(call: types.CallbackQuery):
    cat_id = call.data.split("_")[1]
    cursor.execute("SELECT id, name, price FROM products WHERE cat_id=?", (cat_id,))
    prods = cursor.fetchall()
    if not prods: return await call.answer("No products found in this category.", show_alert=True)
    
    kb = InlineKeyboardBuilder()
    for p in prods:
        kb.button(text=f"{p[1]} - Rs.{p[2]}", callback_data=f"view_{p[0]}")
    kb.button(text="⬅️ Back to Categories", callback_data="back_to_cats")
    kb.adjust(1)
    await call.message.edit_text("🎁 Select a product for details:", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "back_to_cats")
async def back_to_cats(call: types.CallbackQuery):
    cursor.execute("SELECT * FROM categories")
    cats = cursor.fetchall()
    kb = InlineKeyboardBuilder()
    for cat in cats: kb.button(text=cat[1], callback_data=f"cat_{cat[0]}")
    kb.adjust(2)
    await call.message.edit_text("📁 Select a Category:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("view_"))
async def view_prod(call: types.CallbackQuery):
    p_id = call.data.split("_")[1]
    cursor.execute("SELECT * FROM products WHERE id=?", (p_id,))
    p = cursor.fetchone()
    
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Add to Cart", callback_data=f"addcart_{p[0]}")
    kb.button(text="⬅️ Back", callback_data=f"cat_{p[2]}")
    
    text = f"📦 **{p[1]}**\n\n📝 {p[4]}\n\n💰 Price: **Rs.{p[3]}**"
    await call.message.delete()
    await call.message.answer_photo(photo=p[5], caption=text, reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("addcart_"))
async def add_to_cart(call: types.CallbackQuery):
    p_id = call.data.split("_")[1]
    cursor.execute("SELECT user_id FROM cart WHERE user_id=? AND prod_id=?", (call.from_user.id, p_id))
    if cursor.fetchone():
        cursor.execute("UPDATE cart SET qty = qty + 1 WHERE user_id=? AND prod_id=?", (call.from_user.id, p_id))
    else:
        cursor.execute("INSERT INTO cart VALUES (?, ?, 1)", (call.from_user.id, p_id))
    conn.commit()
    await call.answer("✅ Item added to your cart!", show_alert=False)

# --- CART ---

@dp.message(F.text == "🛒 My Cart")
async def view_cart(message: types.Message):
    cursor.execute("""SELECT p.name, p.price, c.qty, p.id FROM cart c 
                      JOIN products p ON c.prod_id = p.id WHERE c.user_id=?""", (message.from_user.id,))
    items = cursor.fetchall()
    if not items: return await message.answer("🛒 Your cart is currently empty.")
    
    text = "🛒 **Shopping Cart Contents:**\n\n"
    total = 0
    for i in items:
        sub = i[1] * i[2]
        total += sub
        text += f"• {i[0]} (x{i[2]}) - Rs.{sub}\n"
    
    text += f"\n💳 **Grand Total: Rs.{total}**"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Checkout Now", callback_data="checkout")
    kb.button(text="🗑️ Empty Cart", callback_data="clear_cart")
    await message.answer(text, reply_markup=kb.as_markup())

@dp.callback_query(F.data == "clear_cart")
async def clear_cart(call: types.CallbackQuery):
    cursor.execute("DELETE FROM cart WHERE user_id=?", (call.from_user.id,))
    conn.commit()
    await call.message.edit_text("🛒 Cart cleared.")

@dp.callback_query(F.data == "checkout")
async def checkout_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("🚚 To proceed, please enter your **Full Name**:")
    await state.set_state(ShopStates.waiting_name)

@dp.message(ShopStates.waiting_name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📞 Thank you! Now enter your **Phone Number**:")
    await state.set_state(ShopStates.waiting_phone)

@dp.message(ShopStates.waiting_phone)
async def get_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("🏠 Finally, enter your complete **Delivery Address**:")
    await state.set_state(ShopStates.waiting_address)

@dp.message(ShopStates.waiting_address)
async def finish_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    
    cursor.execute("""SELECT p.name, c.qty, p.price FROM cart c 
                      JOIN products p ON c.prod_id = p.id WHERE c.user_id=?""", (user_id,))
    items = cursor.fetchall()
    
    order_details = "\n".join([f"{i[0]} x{i[1]}" for i in items])
    total = sum([i[1]*i[2] for i in items])
    
    cursor.execute("INSERT INTO orders (user_id, details, total, name, phone, address) VALUES (?,?,?,?,?,?)",
                   (user_id, order_details, total, data['name'], data['phone'], message.text))
    conn.commit()
    cursor.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    
    await message.answer("🎉 **Success! Order Placed.**\nOur team will contact you shortly.", reply_markup=get_main_kb(user_id))
    
    # Notify Admin
    alert = (f"🔔 **NEW ORDER RECEIVED!**\n\n👤 Name: {data['name']}\n📞 Phone: {data['phone']}\n"
             f"📍 Address: {message.text}\n\n📦 Items:\n{order_details}\n\n💰 **Total: Rs.{total}**")
    await bot.send_message(ADMIN_ID, alert)
    await state.clear()

@dp.message(F.text == "🆘 Support")
async def support(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💬 Chat with Admin", url=f"https://t.me/{ADMIN_USERNAME}"))
    await message.answer("Need help? Click below to contact our support team.", reply_markup=kb.as_markup())

# ================= 👨‍✈️ ADMIN HANDLERS =================

@dp.message(F.text == "⚙️ Admin Dashboard")
async def admin_db(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🛠️ **Admin Control Panel**\nManage your store settings here.", reply_markup=get_admin_kb())

@dp.message(F.text == "➕ Add Category")
async def add_cat_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Enter new category name:")
        await state.set_state(AdminStates.add_cat)

@dp.message(AdminStates.add_cat)
async def add_cat_done(message: types.Message, state: FSMContext):
    cursor.execute("INSERT INTO categories (name) VALUES (?)", (message.text,))
    conn.commit()
    await message.answer(f"✅ Category '{message.text}' added.", reply_markup=get_admin_kb())
    await state.clear()

@dp.message(F.text == "🎁 Add Product")
async def add_prod_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        cursor.execute("SELECT * FROM categories")
        cats = cursor.fetchall()
        if not cats: return await message.answer("Create a category first!")
        kb = InlineKeyboardBuilder()
        for c in cats: kb.button(text=c[1], callback_data=f"selcat_{c[0]}")
        await message.answer("Select category for the new product:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("selcat_"))
async def sel_cat_for_prod(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(cat_id=call.data.split("_")[1])
    await call.message.answer("Enter Product Name:")
    await state.set_state(AdminStates.add_prod_name)

@dp.message(AdminStates.add_prod_name)
async def p_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Enter Price (e.g., 1500):")
    await state.set_state(AdminStates.add_prod_price)

@dp.message(AdminStates.add_prod_price)
async def p_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Price must be a number.")
    await state.update_data(price=message.text)
    await message.answer("Enter Product Description:")
    await state.set_state(AdminStates.add_prod_desc)

@dp.message(AdminStates.add_prod_desc)
async def p_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await message.answer("Upload Product Photo:")
    await state.set_state(AdminStates.add_prod_photo)

@dp.message(AdminStates.add_prod_photo, F.photo)
async def p_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("INSERT INTO products (name, cat_id, price, desc, photo_id) VALUES (?,?,?,?,?)",
                   (data['name'], data['cat_id'], data['price'], data['desc'], message.photo[-1].file_id))
    conn.commit()
    await message.answer("✅ Product listed successfully!", reply_markup=get_admin_kb())
    await state.clear()

@dp.message(F.text == "📊 Stats")
async def bot_stats(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        cursor.execute("SELECT COUNT(*) FROM users")
        total_u = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM orders")
        total_o = cursor.fetchone()[0]
        await message.answer(f"📊 **Store Stats**\n\n👥 Total Users: {total_u}\n📦 Total Orders: {total_o}")

@dp.message(F.text == "🏠 Back to Shop")
async def back_to_shop(message: types.Message):
    await message.answer("Returning to main menu...", reply_markup=get_main_kb(message.from_user.id))

# ================= 🚀 EXECUTION =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Bot stopped!")