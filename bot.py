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

# ================== CONFIG ==================
BOT_TOKEN = "8636160046:AAHNuuDo0H2bMYdpL86L8ukdM6TGfcmlKM8"   # ← CHANGE THIS
bot = telebot.TeleBot(BOT_TOKEN)

# ================== HELPERS (Improved) ==================

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
    if not text:
        return {}

    # Try JSON first
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return {c["name"]: c["value"] for c in data if "name" in c and "value" in c}
        if isinstance(data, dict):
            return data
    except:
        pass

    # Try Netscape / Cookie string
    cookies = {}
    # Handle long single-line pastes
    if len(text) > 500 and "NetflixId" in text:
        # Try to extract NetflixId
        match = re.search(r'NetflixId=([^;,\s]+)', text)
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

    # Fallback: search for NetflixId in whole text
    if not cookies.get("NetflixId"):
        match = re.search(r'NetflixId=([^\s;]+)', text)
        if match:
            cookies["NetflixId"] = match.group(1)

    return cookies

# ================== NETFLIX CHECKER (Same as original) ==================

_IOS_API = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
_IOS_PARAMS = {
    "appVersion": "15.48.1",
    "config": ('{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false",'
               '"cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true",'
               '"billboardEnabled":"true","sharksEnabled":"true",'
               '"useCDSGalleryEnabled":"true","avifFormatEnabled":"false"}'),
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "path": '["account","token","default"]',
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}

_IOS_HEADERS = { ... }  # Keep your full _IOS_HEADERS dict here

UA_WEB = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
UA_ANDROID = "com.netflix.mediaclient/63884 (Linux; U; Android 13)"

# Paste your full COUNTRY_FLAGS and COUNTRY_NAMES here
COUNTRY_FLAGS = { ... }
COUNTRY_NAMES = { ... }

def generate_nftoken(netflix_id_raw, timeout=20):
    if not netflix_id_raw:
        return None
    # (Full function from your original code - copy it here)
    # ... paste full generate_nftoken ...

def check_account(cookies: dict, timeout=25):
    # (Full function from your original code - copy it here)
    # Make sure it includes NFT token generation at the end
    # ... paste full check_account ...

# ================== BOT HANDLERS ==================

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Check Netflix Cookie")
    bot.send_message(message.chat.id,
        "👋 <b>Netflix Cookie Checker Bot</b>\n\n"
        "Send me your Netflix cookies as text or upload .txt/.json file.\n"
        "I will check and give full details + login links.",
        parse_mode="HTML", reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == "🔍 Check Netflix Cookie":
        bot.send_message(message.chat.id, "📋 Paste your full cookie string now:")
        return

    cookies = load_cookies(message.text)
    if not cookies or not any(k in cookies for k in ["NetflixId", "SecureNetflixId"]):
        bot.reply_to(message, "❌ Could not find valid Netflix cookies.\nMake sure NetflixId is present.")
        return

    process_cookie(message, cookies, source="Pasted Text")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        text = downloaded.decode('utf-8', errors='ignore')
        cookies = load_cookies(text)
        if not cookies:
            bot.reply_to(message, "❌ Could not parse the file.")
            return
        process_cookie(message, cookies, source=message.document.file_name)
    except Exception as e:
        bot.reply_to(message, f"❌ Error reading file: {str(e)}")

def process_cookie(message, cookies, source="Unknown"):
    bot.send_chat_action(message.chat.id, 'typing')
    
    result = check_account(cookies)
    
    if not result:
        bot.reply_to(message, "❌ Invalid or Expired Cookie.")
        return

    cc = result.get("country_code", "XX")
    flag = COUNTRY_FLAGS.get(cc.upper(), "🌍")

    text = f"""
🎬 <b>✅ NETFLIX HIT</b>

👤 <b>{result['name']}</b>
📧 <code>{result['email']}</code>
🌍 {result['country']} {flag} ({cc})

📋 <b>{result['plan']}</b> • 💰 {result['price']}
📅 Since: {result['member_since']}
🗓 Next Billing: {result['next_billing']}
🎁 Free Trial: {'Yes' if result.get('free_trial') else 'No'}

🎥 {result['video_quality']} | 📺 {result['max_streams']} streams

💳 {result['card_brand']} *{result['card_last4']}
📞 {result['phone']} {'✅ Verified' if result.get('phone_verified') else '❌'}

👥 Profiles: {len(result.get('profiles', []))}
    """

    markup = types.InlineKeyboardMarkup(row_width=1)
    if result.get("login_pc") and result["login_pc"] != "N/A":
        markup.add(types.InlineKeyboardButton("🖥 Login on PC", url=result["login_pc"]))
    if result.get("login_phone") and result["login_phone"] != "N/A":
        markup.add(types.InlineKeyboardButton("📱 Login on Phone", url=result["login_phone"]))
    markup.add(types.InlineKeyboardButton("📺 Login on TV", url=result.get("login_tv", "https://www.netflix.com/tv2")))

    bot.send_message(message.chat.id, text.strip(), parse_mode="HTML", reply_markup=markup)

if __name__ == "__main__":
    print("🚀 Netflix Cookie Checker Bot Started...")
    bot.infinity_polling()
