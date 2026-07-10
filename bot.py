import re
import requests
import urllib3
import urllib.parse
import telebot
from telebot import types

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = "8636160046:AAHNuuDo0H2bMYdpL86L8ukdM6TGfcmlKM8"
bot = telebot.TeleBot(BOT_TOKEN)

def extract_netflix_id(text):
    # Super strong extraction
    match = re.search(r'NetflixId=([^;,\s"]+)', text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    match = re.search(r'"value"\s*:\s*"([^"]+)"[^}]*"name"\s*:\s*"NetflixId"', text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    match = re.search(r'NetflixId["\s:=]+([^"\s,;]+)', text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None

def get_nftoken(netflix_id):
    if not netflix_id:
        return None
    try:
        headers = {
            "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
            "Cookie": f"NetflixId={netflix_id}"
        }
        r = requests.get(
            "https://ios.prod.ftl.netflix.com/iosui/user/15.48",
            params={"responseFormat": "json"},
            headers=headers,
            timeout=15,
            verify=False
        )
        if r.status_code == 200:
            data = r.json()
            tok = (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default", {}).get("token")
            if tok:
                return str(tok)
    except:
        pass
    return None

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 Paste your Netflix cookie. I will give only NFT Token Login Links.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    netflix_id = extract_netflix_id(message.text)
    if not netflix_id:
        bot.reply_to(message, "❌ NetflixId not found in your paste.")
        return

    bot.send_chat_action(message.chat.id, 'typing')
    tok = get_nftoken(netflix_id)

    if not tok:
        bot.reply_to(message, "❌ Could not generate NFT Token.")
        return

    safe_tok = urllib.parse.quote(tok)
    login_pc = f"https://netflix.com/?nftoken={safe_tok}"
    login_phone = f"https://netflix.com/unsupported?nftoken={safe_tok}"

    text = "🎬 **NFT Token Login Links**"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🖥 Open on PC", url=login_pc))
    markup.add(types.InlineKeyboardButton("📱 Open on Phone", url=login_phone))
    markup.add(types.InlineKeyboardButton("📺 Open on TV", url="https://www.netflix.com/tv2"))

    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

print("🚀 NFT Token Bot Running...")
bot.infinity_polling()
