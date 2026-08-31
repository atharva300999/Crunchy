import requests
import re
import json
import logging
import sqlite3
import threading
from datetime import datetime
import pytz
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)

EMAIL, PASSWORD, PROXY_URL, CHANNEL_ID_1, CHANNEL_ID_2 = range(5)

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
ADMIN_USERNAME = "@ego_exist"

telegram_app = None
last_health_check = datetime.now()

try:
    with open('emoji_pack.json', 'r') as f:
        EMOJI_PACK = json.load(f)
except:
    EMOJI_PACK = {'packs': {}}

def get_emoji(emoji_char):
    for pack_name, pack_data in EMOJI_PACK.get('packs', {}).items():
        for emoji_item in pack_data.get('emojis', []):
            if emoji_item['emoji'] == emoji_char:
                return f"<emoji id=\"{emoji_item['id']}\">"
    return emoji_char

EMOJIS = {
    'check': get_emoji('✅'),
    'cross': get_emoji('❌'),
    'rocket': get_emoji('🚀'),
    'fire': get_emoji('🔥'),
    'star': get_emoji('⭐'),
    'diamond': get_emoji('💎'),
    'lock': get_emoji('🔒'),
    'globe': get_emoji('🌍'),
    'key': get_emoji('🔑'),
    'crown': get_emoji('👑'),
    'danger': get_emoji('⛔'),
    'gear': get_emoji('⚙'),
    'warning': get_emoji('⚠'),
}

@flask_app.route('/health', methods=['GET'])
def health_check():
    global last_health_check
    last_health_check = datetime.now()
    return jsonify({'status': 'alive', 'timestamp': last_health_check.isoformat(), 'bot_active': True}), 200

@flask_app.route('/status', methods=['GET'])
def bot_status():
    return jsonify({'status': 'online', 'timestamp': datetime.now().isoformat()}), 200

@flask_app.route('/ping', methods=['GET', 'POST'])
def ping():
    return jsonify({'pong': True}), 200

@flask_app.route('/', methods=['GET'])
def root():
    return jsonify({'name': 'Crunchyroll Bot', 'status': 'running'}), 200

def init_db():
    conn = sqlite3.connect('bot_config.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS bot_config (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY, channel_type TEXT)''')
    conn.commit()
    conn.close()

def save_config(key, value):
    conn = sqlite3.connect('bot_config.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def get_config(key):
    conn = sqlite3.connect('bot_config.db')
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM bot_config WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def save_channel(channel_id, channel_type):
    conn = sqlite3.connect('bot_config.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO channels (channel_id, channel_type) VALUES (?, ?)', (channel_id, channel_type))
    conn.commit()
    conn.close()

def get_channels():
    conn = sqlite3.connect('bot_config.db')
    cursor = conn.cursor()
    cursor.execute('SELECT channel_id, channel_type FROM channels')
    results = cursor.fetchall()
    conn.close()
    return results

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"{EMOJIS['check']} Check Account", callback_data='check')],
        [InlineKeyboardButton(f"{EMOJIS['gear']} Settings", callback_data='settings')],
    ]
    
    username = update.effective_user.username or ""
    if username == ADMIN_USERNAME.lstrip('@'):
        keyboard.append([InlineKeyboardButton(f"{EMOJIS['crown']} Admin Panel", callback_data='admin')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"{EMOJIS['rocket']} <b>Crunchyroll Checker</b>\n\n"
        f"{EMOJIS['star']} Check your account\n"
        f"{EMOJIS['lock']} Secure & Fast",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def check_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        f"{EMOJIS['key']} Send your email:",
        parse_mode=ParseMode.HTML
    )
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    context.user_data['email'] = email
    
    await update.message.reply_text(
        f"{EMOJIS['lock']} Now send your password:",
        parse_mode=ParseMode.HTML
    )
    return PASSWORD

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    email = context.user_data.get('email')
    
    await update.message.reply_text(
        f"{EMOJIS['rocket']} Checking account...",
        parse_mode=ParseMode.HTML
    )
    
    result = verify_account(email, password)
    
    if result['success']:
        data = result['data']
        profiles = data.get('profiles', [])
        subs = data.get('subscriptions', [])
        
        profile_name = profiles[0].get('profile_name', 'Unknown') if profiles else 'Unknown'
        plan = subs[0].get('plan', {}).get('tier', {}).get('text', 'Unknown') if subs else 'Unknown'
        status = subs[0].get('status', 'Unknown') if subs else 'Unknown'
        
        msg = f"""<b>{EMOJIS['check']} CRUNCHYROLL HIT</b>

<b>Email:</b> <code>{email}</code>
<b>Password:</b> <code>{password}</code>

<b>Plan:</b> {plan}
<b>Status:</b> {status}
<b>Profile:</b> {profile_name}"""
        
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            f"{EMOJIS['cross']} Check Failed: {result['error']}",
            parse_mode=ParseMode.HTML
        )
    
    return ConversationHandler.END

def verify_account(email: str, password: str) -> dict:
    try:
        session = requests.Session()
        
        login_url = "https://sso.crunchyroll.com/api/login"
        login_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Content-Type": "application/json",
        }
        
        login_data = {
            "email": email,
            "password": password,
            "recaptchaToken": "",
            "eventSettings": {}
        }
        
        login_response = session.post(login_url, headers=login_headers, json=login_data, timeout=30)
        
        if login_response.status_code != 200:
            return {'success': False, 'error': 'Invalid credentials'}
        
        device_id = login_response.cookies.get("device_id", "")
        
        token_url = "https://www.crunchyroll.com/auth/v1/token"
        token_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Basic bm9haWhkZXZtXzZpeWcwYThsMHE6",
        }
        
        token_data = {
            "device_id": device_id,
            "device_type": "Firefox on Windows",
            "grant_type": "etp_rt_cookie"
        }
        
        token_response = session.post(token_url, headers=token_headers, data=token_data, timeout=30)
        
        if token_response.status_code != 200:
            return {'success': False, 'error': 'Token failed'}
        
        token_json = token_response.json()
        access_token = token_json.get('access_token', '')
        account_id = token_json.get('account_id', '')
        
        profile_url = "https://www.crunchyroll.com/accounts/v1/me/multiprofile"
        profile_headers = {
            "User-Agent": "Mozilla/5.0",
            "Authorization": f"Bearer {access_token}",
        }
        
        profile_response = session.get(profile_url, headers=profile_headers, timeout=30)
        profile_data = profile_response.json() if profile_response.status_code == 200 else {}
        
        sub_url = f"https://www.crunchyroll.com/subs/v4/accounts/{account_id}/subscriptions"
        sub_response = session.get(sub_url, headers=profile_headers, timeout=30)
        sub_data = sub_response.json() if sub_response.status_code == 200 else {}
        
        return {
            'success': True,
            'data': {
                'profiles': profile_data.get('profiles', []),
                'subscriptions': sub_data.get('subscriptions', [])
            }
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    keyboard = [
        [InlineKeyboardButton(f"{EMOJIS['gear']} Proxy Settings", callback_data='proxy_menu')],
        [InlineKeyboardButton(f"{EMOJIS['key']} Back", callback_data='start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        f"{EMOJIS['gear']} Settings",
        reply_markup=reply_markup
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    username = update.effective_user.username or ""
    
    if username != ADMIN_USERNAME.lstrip('@'):
        await update.callback_query.answer(f"{EMOJIS['cross']} Admin only!", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton(f"{EMOJIS['diamond']} Status", callback_data='admin_stats')],
        [InlineKeyboardButton(f"{EMOJIS['key']} Back", callback_data='start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        f"{EMOJIS['crown']} Admin Panel\n\nBot: Online",
        reply_markup=reply_markup
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        f"{EMOJIS['diamond']} Bot Stats\n\n"
        f"Status: Online\n"
        f"Uptime: 24/7\n"
        f"Health: Good"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"{EMOJIS['cross']} Cancelled")
    return ConversationHandler.END

def run_telegram_bot():
    global telegram_app
    
    app = Application.builder().token(BOT_TOKEN).build()
    telegram_app = app
    
    check_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(check_account_start, pattern='check')],
        states={
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(settings_menu, pattern='settings'))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern='admin'))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern='admin_stats'))
    app.add_handler(check_conv)
    
    logger.info("Telegram bot started...")
    app.run_polling(allowed_updates=__import__('telegram').Update.ALL_TYPES)

if __name__ == '__main__':
    init_db()
    
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    
    port = int(__import__('os').environ.get('PORT', 5000))
    logger.info(f"Flask starting on port {port}...")
    flask_app.run(host='0.0.0.0', port=port, debug=False)
