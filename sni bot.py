import telebot
import requests
import socket
import ssl
import concurrent.futures
import threading
import sqlite3
import datetime
import time
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# --- 1. CONFIGURATION ---
BOT_TOKEN = '6454456940:AAFUAbZatEwrNvv75emY_376l7yJDmr5-48' 
ADMIN_USERNAME = '@prasa_z' 
ADMIN_ID = 6221106415 # 🚨 ඔබගේ Telegram User ID එක මෙහි ඇතුළත් කරන්න!

# Freemium/Scanning Settings
DEFAULT_PORTS = [80, 443, 8080, 8443]
CRITICAL_PORTS = [21, 23, 22, 3389, 5900] 
TIMEOUT = 1.0
MAX_WORKERS = 40
FREE_SCAN_LIMIT = 3
FREE_HOST_LIMIT = 50

# Database
DB_NAME = 'sni_bot_users.db'

# AI Wordlist
PREDICTIVE_WORDLIST = [
    "api", "dev", "test", "web", "cdn", "mail", "ftp", "admin", "proxy", "vpn", 
    "access", "live", "app", "static", "assets", "mobile", "staging", "server",
    "backup", "internal", "secure", "status"
]

# --- Bot Initialization ---
bot = telebot.TeleBot(BOT_TOKEN)

# ----------------------------------------------------
# --- DUAL LANGUAGE MESSAGES (Sinhala / English) ---
# ----------------------------------------------------

PREMIUM_MESSAGE = (
    f"👑 <b>Premium Access අවශ්‍යයි</b> 👑\n\n"
    f"ඔබගේ <b>Free Scan සීමාව ({FREE_SCAN_LIMIT})</b> අවසන් වී ඇත. අසීමිත Scans, සම්පූර්ණ ප්‍රතිඵල, **Advanced Filter** සහ **Risk Scoring** සඳහා Premium වෙත මාරු වන්න.\n"
    f"----------------------------------------\n"
    f"👑 <b>Premium Access Required</b> 👑\n\n"
    f"Your <b>Free Scan limit ({FREE_SCAN_LIMIT})</b> is exhausted. Upgrade to Premium for unlimited scans, full results, **Advanced Filter**, and **Risk Scoring**.\n\n"
    f"💵 <b>ගාස්තුව / Fee:</b> Rs. 500/Month\n\n"
    f"🏦 <b>Bank Details:</b>\n"
    f"  <b>Bank:</b> <code>BOC</code>\n"
    f"  <b>A/C Name:</b> <code>K.G.C.SILVA</code>\n"
    f"  <b>A/C No:</b> <code>93872075</code>\n\n"
    f"📤 <b>Pay කරන්නේ කෙසේද / How to Pay:</b>\n"
    f"ගෙවීම් කළ පසු, ඔබගේ <b>Payment Receipt</b> එක සහ ඔබගේ Telegram <b>User Name</b> එක {ADMIN_USERNAME} වෙත එවන්න.\n"
    f"Send your <b>Payment Receipt</b> and your Telegram <b>User Name</b> to {ADMIN_USERNAME} after payment."
)

WELCOME_MESSAGE = (
    f"🤖 <b>Advanced SNI Hunter Bot</b> වෙත සාදරයෙන් පිළිගනිමු!\n\n"
    f"✨ <b>Free Trial Offer:</b>\n"
    f"ඔබට කිසිදු ගාස්තුවක් නොමැතිව <b>සම්පූර්ණ Scans {FREE_SCAN_LIMIT}ක්</b> භාවිතා කළ හැක. සෑම Scan එකකදීම සොයාගත් Host <b>{FREE_HOST_LIMIT}ක්</b> පමණක් පෙන්වනු ලැබේ.\n"
    f"භාවිතා කරන ආකාරය: <code>/scan domain.com</code>\n"
    f"----------------------------------------\n"
    f"🤖 <b>Welcome to Advanced SNI Hunter Bot</b>!\n\n"
    f"✨ <b>Free Trial Offer:</b>\n"
    f"You can use <b>{FREE_SCAN_LIMIT} complete Scans</b> free of charge. Each scan will show only <b>{FREE_HOST_LIMIT} hosts</b> found.\n"
    f"Usage: <code>/scan domain.com</code>"
)

# ----------------------------------------------------------------------------------
# --- 2. DATABASE FUNCTIONS (NOW WITH SCAN LOGS) ---
# ----------------------------------------------------------------------------------

def setup_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT, 
            free_scans_used INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            premium_expiry TEXT
        )
    """)
    # Scan Logs table (NEW)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_logs (
            log_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            domain TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_scan_request(user_id, domain):
    """Logs the domain searched by the user."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("INSERT INTO scan_logs (user_id, domain, timestamp) VALUES (?, ?, ?)", 
                   (user_id, domain, timestamp))
    conn.commit()
    conn.close()

def revoke_premium_access(user_id, reason_si="Admin විසින්", reason_en="revoked by Admin"):
    """පරිශීලකයෙකුගේ Premium Access ඉවත් කරයි, ද්වි-භාෂා Notification යවයි."""
    
    revoke_msg = (
        f"⚠️ ඔබගේ **Premium Access** දැන් අවලංගු කර ඇත! හේතුව: {reason_si}.\nඔබව නැවත Free User ලෙස යාවත්කාලීන කරන ලදි. නැවත Premium ලබා ගැනීමට /premium යවන්න.\n"
        f"----------------------------------------\n"
        f"⚠️ Your **Premium Access** has been revoked! Reason: {reason_en}.\nYou have been updated to a Free User. Send /premium to get Premium Access again."
    )
    try:
        bot.send_message(user_id, revoke_msg, parse_mode='HTML')
    except Exception:
        pass 
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_premium = 0, premium_expiry = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def grant_premium_access(user_id, duration_days):
    """පරිශීලකයෙකුට Premium Access ලබා දේ සහ ද්වි-භාෂා Notification යවයි."""
    expiry_date = datetime.datetime.now() + datetime.timedelta(days=duration_days)
    expiry_date_str = expiry_date.strftime('%Y-%m-%d')

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET is_premium = 1, premium_expiry = ? 
        WHERE user_id = ?
    """, (expiry_date.strftime('%Y-%m-%d %H:%M:%S'), user_id))
    
    conn.commit()
    conn.close()
    
    grant_msg = (
        f"🎉 ඔබට දින <b>{duration_days}</b>ක් සඳහා **Premium Access** සාර්ථකව සක්‍රිය කරන ලදි!\nඑය {expiry_date_str} දින කල් ඉකුත් වනු ඇත.\n"
        f"----------------------------------------\n"
        f"🎉 Your **Premium Access** has been successfully activated for <b>{duration_days}</b> days!\nIt will expire on {expiry_date_str}."
    )
    try:
        bot.send_message(user_id, grant_msg, parse_mode='HTML')
    except Exception:
        pass

def get_id_by_username(identifier):
    """Username හෝ ID එක භාවිතයෙන් User ID එක සොයා ගනී."""
    if identifier.isdigit():
        return int(identifier)
    
    if identifier.startswith('@'):
        search_username = identifier
    else:
        search_username = f"@{identifier}" 
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE username=?", (search_username,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    return None

def check_premium_expiry(user_id):
    """Premium කාලය අවසන් දැයි පරීක්ෂා කර, අවසන් නම් revoke කරයි."""
    if user_id == ADMIN_ID:
        return False

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT is_premium, premium_expiry FROM users WHERE user_id = ?", (user_id,))
    data = cursor.fetchone()
    conn.close()

    if data and data[0] == 1 and data[1]:
        try:
            expiry_time = datetime.datetime.strptime(data[1], '%Y-%m-%d %H:%M:%S')
            
            if datetime.datetime.now() > expiry_time:
                revoke_premium_access(user_id, reason_si="කාලය අවසන්", reason_en="Expiry")
                return True 
        except ValueError:
            return False
            
    return False 

def get_user_status(user_id, username):
    """User ගේ තත්ත්වය DB එකෙන් ලබා ගනී. ADMIN_ID නම්, එය සැමවිටම Premium වේ."""
    if user_id == ADMIN_ID:
        return (0, 1, 'Never Expires') 

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT free_scans_used, is_premium, premium_expiry FROM users WHERE user_id=?", (user_id,))
    data = cursor.fetchone()
    
    if data is None:
        cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
        data = (0, 0, None)
    else:
        cursor.execute("UPDATE users SET username = ? WHERE user_id=?", (username, user_id))
        conn.commit()

    conn.close()
    return data

def update_scan_count(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET free_scans_used = free_scans_used + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# ----------------------------------------------------------------------------------
# --- 3. CORE UTILITY FUNCTIONS (Scanning/Data Retrieval) ---
# ----------------------------------------------------------------------------------

def get_isp_info(ip):
    try:
        url = f"http://ip-api.com/json/{ip}?fields=isp,org,as,countryCode"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            isp = data.get('isp', 'Unknown').replace('<', '&lt;').replace('>', '&gt;')
            country = data.get('countryCode', 'XX')
            return f"{isp} ({data.get('as', '')}) [🇨{country}]"
    except:
        return "Unknown ISP"
    return "Unknown ISP"

def generate_predictive_subdomains(domain, passive_list):
    new_hosts = set()
    for word in PREDICTIVE_WORDLIST:
        new_host = f"{word}.{domain}"
        if new_host not in passive_list:
             new_hosts.add(new_host)
    passive_list.extend(list(new_hosts))
    return passive_list

def fetch_subdomains(domain):
    subdomains = set()
    crt_url = f"https://crt.sh/?q=%.{domain}&output=json"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(crt_url, headers=headers, timeout=15)
        if response.status_code == 200 and response.text:
            data = response.json()
            for entry in data:
                name_value = entry.get('name_value', '')
                if name_value:
                    for sub in name_value.split('\n'):
                        if sub.strip() and "*" not in sub:
                            subdomains.add(sub.strip())
    except Exception:
        pass

    if not subdomains:
        hackertarget_url = f"https://api.hackertarget.com/hostsearch/?q={domain}"
        try:
            response = requests.get(hackertarget_url, timeout=10)
            if response.status_code == 200 and "API count exceeded" not in response.text:
                lines = response.text.splitlines()
                for line in lines:
                    parts = line.split(',')
                    if len(parts) > 0 and 'error' not in parts[0].lower() and '*' not in parts[0]:
                        subdomains.add(parts[0].strip())
        except Exception:
            pass
            
    return list(subdomains)

def scan_target(host):
    data = {
        "host": host, "ip": "N/A", "ports": [], "server": "Unknown", "status": "Offline", "isp": "N/A"
    }
    
    try:
        ip = socket.gethostbyname(host)
        data["ip"] = ip
        data["status"] = "Online"
        
        for port in DEFAULT_PORTS:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(TIMEOUT)
            result = sock.connect_ex((ip, port))
            
            if result == 0:
                data["ports"].append(port)
                if port in [80, 443] and data["server"] == "Unknown":
                     if port == 443:
                        context = ssl.create_default_context()
                        context.check_hostname = False
                        context.verify_mode = ssl.CERT_NONE
                        with socket.create_connection((ip, port), timeout=TIMEOUT) as s:
                            with context.wrap_socket(s, server_hostname=host) as ssock:
                                ssock.send(f"HEAD / HTTP/1.1\r\nHost: {host}\r\n\r\n".encode())
                                resp = ssock.read(1024).decode('utf-8', errors='ignore')
                     else:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(TIMEOUT)
                        s.connect((ip, port))
                        s.send(f"HEAD / HTTP/1.1\r\nHost: {host}\r\n\r\n".encode())
                        resp = s.recv(1024).decode('utf-8', errors='ignore')
                        s.close()
                     
                     for line in resp.split("\r\n"):
                            if line.lower().startswith("server:"):
                                data["server"] = line.split(":", 1)[1].strip()
            sock.close()
            
        if data["ports"]:
            data["isp"] = get_isp_info(ip)

    except:
        pass
        
    return data

# ----------------------------------------------------------------------------------
# --- 4. TELEGRAM BOT HANDLERS ---
# ----------------------------------------------------------------------------------

def create_main_keyboard(user_id):
    """ප්‍රධාන Reply Keyboard එක නිර්මාණය කරයි (Admin Buttons ඇතුළත්)."""
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_scan = KeyboardButton('/scan')
    btn_status = KeyboardButton('/status')
    btn_premium = KeyboardButton('/premium')
    markup.add(btn_scan)
    markup.add(btn_status, btn_premium)
    
    if user_id == ADMIN_ID:
        btn_grant = KeyboardButton('👑 Grant Access') 
        btn_revoke = KeyboardButton('🗑️ Revoke Access')
        markup.add(btn_grant, btn_revoke)
    
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    username = f"@{message.from_user.username}" if message.from_user.username else f"ID_{message.from_user.id}"
    setup_db() 
    get_user_status(message.from_user.id, username) 
    
    bot.reply_to(message, WELCOME_MESSAGE, parse_mode='HTML', reply_markup=create_main_keyboard(message.from_user.id))

@bot.message_handler(commands=['premium'])
def handle_premium_command(message):
    bot.reply_to(message, PREMIUM_MESSAGE, parse_mode='HTML')

@bot.message_handler(commands=['status'])
def handle_status_command(message):
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else f"ID_{message.from_user.id}"
    
    free_scans_used, is_premium, _ = get_user_status(user_id, username)
    
    status_msg = (
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
        f"🔥 <b>තත්ත්වය / Status:</b> {'👑 Premium User' if is_premium == 1 else '⚡️ Free User'}\n"
    )
    
    if is_premium == 0:
        remaining = FREE_SCAN_LIMIT - free_scans_used
        status_msg += (
            f"🔍 <b>ඉතිරි Scans / Scans Remaining:</b> <b>{remaining}</b> / {FREE_SCAN_LIMIT}\n\n"
        )
        if remaining <= 0:
            status_msg += "⚠️ ඔබගේ Free Scan සීමාව අවසන්. Premium වෙත මාරු වන්න! / Your Free Scan limit is exhausted. Upgrade to Premium!"
    else:
        status_msg += "✅ <b>Scans:</b> අසීමිතයි (Unlimited)"

    bot.reply_to(message, status_msg, parse_mode='HTML')


# ----------------------------------------------------
# 👑 ADMIN DASHBOARD (UPDATED with Scan Logs)
# ----------------------------------------------------

@bot.message_handler(commands=['admin'])
def handle_admin_command(message):
    
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "🚫 ඔබට මෙම විධානය භාවිත කළ නොහැක.")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Fetch ALL User Data 
    cursor.execute("SELECT user_id, username, is_premium, premium_expiry, free_scans_used FROM users WHERE user_id != ?", (ADMIN_ID,))
    all_users_data = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    premium_users_list = []
    normal_users_list = []
    premium_users_count = 0
    
    for data in all_users_data:
        user_id, username, is_premium, expiry, free_scans_used = data
        
        user_display_name = username if username and not username.startswith('ID_') else f"ID: {user_id}"
        clickable_link = f"<a href='tg://user?id={user_id}'>@{user_display_name}</a>"
        expiry_display = expiry.split()[0] if expiry else "N/A"
        
        # --- SCAN STATUS LOGIC ---
        if is_premium == 1:
            scan_status_display = "✅ Premium (Unlimited)"
        else:
            remaining = FREE_SCAN_LIMIT - free_scans_used
            if remaining <= 0:
                scan_status_display = f"🚫 Free Exhausted ({free_scans_used}/{FREE_SCAN_LIMIT})"
            else:
                scan_status_display = f"⚡️ Free Used: {free_scans_used}/{FREE_SCAN_LIMIT}"
        # --- END SCAN STATUS LOGIC ---

        user_line = f"  • {clickable_link} | Scans: {scan_status_display} | Expiry: {expiry_display}"
        
        if is_premium == 1:
            premium_users_list.append(user_line)
            premium_users_count += 1
        else:
            normal_users_list.append(user_line)


    admin_msg = f"👑 <b>Admin Dashboard</b>\n"
    admin_msg += f"----------------------------------------\n"
    admin_msg += f"👥 <b>Total Users (සියලුම):</b> {total_users}\n"
    admin_msg += f"🌟 <b>Premium Users:</b> {premium_users_count} (+ Admin)\n"
    admin_msg += f"----------------------------------------\n"
    
    # --- PREMIUM USER LIST ---
    admin_msg += f"📋 <b>Active Premium List ({len(premium_users_list)} Users):</b>\n"
    if premium_users_list:
        admin_msg += "\n".join(premium_users_list)
        admin_msg += "\n"
    else:
        admin_msg += "<i>❌ කිසිවෙක් නැත. / None.</i>\n"
        
    admin_msg += f"----------------------------------------\n"
    
    # --- NORMAL USER LIST ---
    admin_msg += f"📝 <b>Normal/Free Users ({len(normal_users_list)} Users):</b>\n"
    normal_display_limit = 20 
    
    if normal_users_list:
        admin_msg += "\n".join(normal_users_list[:normal_display_limit])
        
        if len(normal_users_list) > normal_display_limit:
             admin_msg += f"\n<i>... තවත් {len(normal_users_list) - normal_display_limit}ක් ඇත. / {len(normal_users_list) - normal_display_limit} more.</i>"
        
        admin_msg += "\n"
    else:
        admin_msg += "<i>❌ කිසිවෙක් නැත. / None.</i>\n"

    # 2. Fetch Recent Scan Logs (NEW SECTION)
    cursor.execute("""
        SELECT u.username, s.domain, s.timestamp 
        FROM scan_logs s
        JOIN users u ON s.user_id = u.user_id
        ORDER BY s.log_id DESC 
        LIMIT 15
    """)
    recent_logs = cursor.fetchall()
    
    conn.close() 

    admin_msg += f"\n\n\n🕵️ <b>Recent 15 Searches (නවතම Scans):</b>\n"
    if recent_logs:
        log_list = []
        for username, domain, timestamp in recent_logs:
            # Extract time for brevity
            time_only = timestamp.split(' ')[1][:5] 
            user_display = username if username else f"ID_{recent_logs.index((username, domain, timestamp))+1}"
            log_list.append(f"  • {time_only} | {user_display} ➡️ <code>{domain}</code>")
        
        admin_msg += "\n".join(log_list)
    else:
        admin_msg += "<i>❌ කිසිදු සෙවීමක් ලොග් වී නැත. / No searches logged.</i>"

    bot.reply_to(message, admin_msg, parse_mode='HTML')


# ----------------------------------------------------
# 👑 PREMIUM CONVERSATION HANDLERS (Unchanged)
# ----------------------------------------------------

@bot.message_handler(func=lambda message: message.text == '👑 Grant Access')
def grant_access_start(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "🚫 ඔබට මෙම විධානය භාවිත කළ නොහැක.")
        return

    msg = bot.reply_to(message, "👤 **Premium ලබා දීමට අවශ්‍ය පරිශීලකයාගේ Username (<code>@user</code>) හෝ User ID එක ඇතුළත් කරන්න:**\n(Enter the **Username** or **User ID** to grant Premium access. /start to cancel)", parse_mode='HTML')
    bot.register_next_step_handler(msg, get_username_grant)

def get_username_grant(message):
    if message.text == '/start':
        send_welcome(message)
        return
        
    target_identifier = message.text.strip()
    target_user_id = get_id_by_username(target_identifier)

    if not target_user_id:
        msg = bot.reply_to(message, f"❌ <b>'{target_identifier}'</b> සමඟ ගැලපෙන පරිශීලකයෙකු සොයා ගැනීමට නොහැක. නැවත උත්සාහ කරන්න. / User not found. Try again.", parse_mode='HTML')
        bot.register_next_step_handler(msg, get_username_grant)
        return
    
    msg = bot.reply_to(message, f"📅 <b>{target_identifier}</b> ට දින කීයක් (උදා: 30) සඳහා Access ලබා දිය යුතුද? / How many days (e.g. 30) access should be granted to <b>{target_identifier}</b>?", parse_mode='HTML')
    bot.register_next_step_handler(msg, get_days_grant, target_user_id)

def get_days_grant(message, target_user_id):
    if message.text == '/start':
        send_welcome(message)
        return
        
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        msg = bot.reply_to(message, "❌ කරුණාකර දින ගණන නිවැරදි ඉලක්කමකින් ඇතුළත් කරන්න. / Please enter a valid number for days.", parse_mode='HTML')
        bot.register_next_step_handler(msg, get_days_grant, target_user_id)
        return

    grant_premium_access(target_user_id, days)

    bot.reply_to(message, f"✅ **සාර්ථකයි! / Success!**\n<b>{target_user_id}</b> ට දින <b>{days}</b>ක් සඳහා Premium Access ලබා දෙන ලදි. (පරිශීලකයාට Notification එකක් යවන ලදි). / Premium Access granted to <b>{target_user_id}</b> for <b>{days}</b> days. (Notification sent to user).", parse_mode='HTML')


@bot.message_handler(func=lambda message: message.text == '🗑️ Revoke Access')
def revoke_access_start(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "🚫 ඔබට මෙම විධානය භාවිත කළ නොහැක.")
        return

    msg = bot.reply_to(message, "👤 **Premium Access ඉවත් කිරීමට අවශ්‍ය පරිශීලකයාගේ Username (<code>@user</code>) හෝ User ID එක ඇතුළත් කරන්න:**\n(Enter the **Username** or **User ID** to revoke Premium access.)", parse_mode='HTML')
    bot.register_next_step_handler(msg, get_username_revoke)

def get_username_revoke(message):
    if message.text == '/start':
        send_welcome(message)
        return
        
    target_identifier = message.text.strip()
    target_user_id = get_id_by_username(target_identifier)

    if not target_user_id:
        msg = bot.reply_to(message, f"❌ <b>'{target_identifier}'</b> සමඟ ගැලපෙන පරිශීලකයෙකු සොයා ගැනීමට නොහැක. නැවත උත්සාහ කරන්න. / User not found. Try again.", parse_mode='HTML')
        bot.register_next_step_handler(msg, get_username_revoke)
        return

    revoke_premium_access(target_user_id, reason_si="Admin විසින් අවලංගු කරන ලදි", reason_en="revoked by Admin")
    
    bot.reply_to(message, f"🗑️ **සාර්ථකයි! / Success!**\n<b>{target_identifier}</b> ගේ Premium Access වහාම ඉවත් කරන ලදි. (පරිශීලකයාට Notification එකක් යවන ලදි). / Premium Access revoked for <b>{target_identifier}</b>. (Notification sent to user).", parse_mode='HTML')

# ----------------------------------------------------
# --- SCAN COMMAND HANDLER (Now logs the request)
# ----------------------------------------------------

@bot.message_handler(commands=['scan'])
def handle_scan_command(message):
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else f"ID_{message.from_user.id}"
    
    check_premium_expiry(user_id)
    
    free_scans_used, is_premium, _ = get_user_status(user_id, username)
    
    if is_premium == 0 and free_scans_used >= FREE_SCAN_LIMIT:
        bot.reply_to(message, PREMIUM_MESSAGE, parse_mode='HTML')
        return

    try:
        command_parts = message.text.split()
        if len(command_parts) < 2:
            bot.reply_to(message, "කරුණාකර Domain නාමයක් ඇතුළත් කරන්න. උදා: <code>/scan zoom.us</code> / Please enter a Domain. E.g: <code>/scan zoom.us</code>", parse_mode='HTML')
            return
        
        target_domain = command_parts[1].strip()
        
        thread = threading.Thread(target=start_scan_task, args=(message, target_domain, is_premium))
        thread.start()

    except Exception as e:
        bot.reply_to(message, f"සමාවෙන්න! විධානය ක්‍රියාත්මක කිරීමේදී දෝෂයක් සිදුවිය: {e} / Sorry! An error occurred while executing the command.", parse_mode='HTML')

def start_scan_task(message, target_domain, is_premium):
    user_id = message.from_user.id
    output_results = []
    final_sni_list = [] 

    # --- NEW: Log the scan request ---
    log_scan_request(user_id, target_domain)
    
    try:
        status_msg = bot.reply_to(message, f"🔎 <b>{target_domain}</b> සඳහා SNI සහ Port Scan කිරීම ආරම්භ කරයි. කරුණාකර රැදී සිටින්න... / Starting SNI and Port Scan for <b>{target_domain}</b>. Please wait...", parse_mode='HTML')
        
        passive_sni_list = fetch_subdomains(target_domain)
        final_sni_list = generate_predictive_subdomains(target_domain, passive_sni_list)
        
        if not final_sni_list:
            bot.edit_message_text("❌ කිසිදු SNI Host එකක් සොයා ගැනීමට නොහැකි විය. / No SNI Hosts found.", message.chat.id, status_msg.message_id)
            return

        bot.edit_message_text(f"✅ Host <b>{len(final_sni_list)}</b> ක් සොයා ගන්නා ලදී. දැන් Port Scanning ආරම්භ වේ... / <b>{len(final_sni_list)}</b> Hosts found. Starting Port Scanning...", message.chat.id, status_msg.message_id, parse_mode='HTML')
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            results = list(executor.map(scan_target, final_sni_list))

            for res in results:
                if res["status"] == "Online" and res["ports"]:
                    cdn_status = "☁️ CDN/Proxy" if "cloud" in res['server'].lower() or "akamai" in res['server'].lower() else "💻 Direct/Local"
                    ports_str = ", ".join(map(str, res['ports']))
                    
                    risk_flag = "⚠️ <b>High Risk Port Detected!</b>" if any(port in res['ports'] for port in CRITICAL_PORTS) else ""
                    
                    formatted_result_string = (
                        f"<b>{res['host']}</b>\n"
                        f"  IP: <code>{res['ip']}</code>\n"
                        f"  Ports: <code>{ports_str}</code>\n"
                        f"  Server: {res['server'][:20]} ({cdn_status})\n"
                        f"  ISP: {res['isp']}\n"
                        f"  {risk_flag}\n"
                    )
                    output_results.append(formatted_result_string)

        limit_message = ""
        
        if is_premium == 0:
            update_scan_count(user_id)
            
            if len(output_results) > FREE_HOST_LIMIT:
                output_results = output_results[:FREE_HOST_LIMIT]
                limit_message = f"\n⚠️ <b>සොයාගත් Hosts</b> සම්පූර්ණ ප්‍රමාණය Premium හිදී දැකිය හැක. <b>Free Trial</b> සීමාව නිසා <b>Hosts {FREE_HOST_LIMIT}ක්</b> පමණක් පෙන්වයි. / Full results are available in Premium. Showing only <b>{FREE_HOST_LIMIT} hosts</b> due to Free Trial limit."
            
        
        if not output_results:
            final_message = "🤷‍♂️ ස්කෑන් කිරීම අවසන්. කිසිදු විවෘත Host එකක් සොයා ගැනීමට නොහැකි විය. / Scan complete. No open hosts found."
            bot.edit_message_text(final_message, message.chat.id, status_msg.message_id, parse_mode='HTML')
            return

        header = f"🔥 <b>{target_domain}</b> සඳහා සොයාගත් Hosts ({len(output_results)}/{len(final_sni_list)} Online)\n" + ("="*30) + "\n"
        footer = limit_message + "\n" + ("="*30) + "\n<i>Scan complete.</i>"
        
        chunks = []
        current_chunk = header
        
        for result_line in output_results:
            if len(current_chunk) + len(result_line) + 500 > 4096: 
                chunks.append(current_chunk) 
                current_chunk = result_line
            else:
                current_chunk += result_line

        current_chunk += footer
        chunks.append(current_chunk)

        first_message = True
        for chunk in chunks:
            if first_message:
                bot.edit_message_text(chunk, message.chat.id, status_msg.message_id, parse_mode='HTML')
                first_message = False
            else:
                bot.send_message(message.chat.id, chunk, parse_mode='HTML')
        
    except Exception as e:
        bot.send_message(message.chat.id, f"සමාවෙන්න! ස්කෑන් කිරීමේදී බරපතල දෝෂයක් සිදුවිය: {e} / Sorry! A serious error occurred during the scan.", parse_mode='HTML')

# ----------------------------------------------------
# --- 6. START THE BOT ---
# ----------------------------------------------------

if __name__ == '__main__':
    setup_db() 
    print("Telegram Bot ආරම්භ විය / Telegram Bot started...")
    try:
        bot.set_my_commands([
            telebot.types.BotCommand("/scan", "Domain Scan"),
            telebot.types.BotCommand("/status", "Current Scan Status"),
            telebot.types.BotCommand("/premium", "Get Premium Access Details"),
            telebot.types.BotCommand("/admin", "Admin Dashboard (Admin only)"),
            telebot.types.BotCommand("/start", "Restart the Bot") 
        ])
        bot.polling()
    except Exception as e:
        print(f"Bot ආරම්භ කිරීමේ දෝෂය / Bot startup error: {e}")