import telebot
import requests
import threading
import time
import random
import string
import os
import json
import uuid
import logging
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from flask import Flask
from fake_useragent import UserAgent

# ==========================================
# ⚙️ CONFIGURATION SECTION
# ==========================================
BOT_TOKEN = "8468244120:AAGXjaczSUzqCF9xTRtoShEzhmx406XEhCE"  # <--- PASTE YOUR TOKEN HERE
OWNER_ID = 5963548505              # <--- REPLACE WITH YOUR TELEGRAM USER ID

# Monster Settings
MAX_THREADS = 40                   # Optimized for Render Free Tier (Don't go too high or it crashes)
BATCH_SIZE = 100                   # Send file after this many hits
REQUEST_TIMEOUT = 20               # Seconds to wait for a site
USER_AGENT_ROTATOR = UserAgent()

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Bot
bot = telebot.TeleBot(BOT_TOKEN)

# Global State Dictionary
active_jobs = {}

# ==========================================
# 🌐 RENDER KEEPER (FLASK SERVER)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "👹 MONSTER BOT IS ALIVE AND HUNTING 👹", 200

def run_web_server():
    # Render assigns the PORT environment variable
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
    """Generates realistic fake identity for checkout."""
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
    streets = ["Main St", "Park Ave", "Oak St", "Pine St", "Maple Ave", "Cedar Ln"]
    
    return {
        "first_name": random.choice(first_names),
        "last_name": random.choice(last_names),
        "email": f"shop{random.randint(10000,99999)}@gmail.com",
        "address": f"{random.randint(100,9999)} {random.choice(streets)}",
        "city": "New York",
        "state": "NY",
        "zip": "10001",
        "country": "US",
        "phone": f"555{random.randint(1000000,9999999)}"
    }

def create_monster_session():
    """Creates a requests session optimized for speed and resilience."""
    session = requests.Session()
    
    # Retry logic to handle network blips on free tier
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=MAX_THREADS, pool_maxsize=MAX_THREADS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    return session

def clean_url(url):
    """Cleans and standardizes the URL."""
    url = url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"
    # Remove trailing slash
    if url.endswith("/"):
        url = url[:-1]
    return url

def find_between(data, first, last):
    """Helper to extract strings between two delimiters."""
    try:
        start = data.index(first) + len(first)
        end = data.index(last, start)
        return data[start:end]
    except ValueError:
        return None

# ==========================================
# 🧠 THE MONSTER CHECKER LOGIC
# ==========================================

def check_site_ultimate(site_url):
    """
    The Ultimate Checking Logic.
    Returns: (Status, Message, Gateway)
    Status: 'LIVE', 'DEAD', 'CAPTCHA'
    """
    session = create_monster_session()
    site_url = clean_url(site_url)
    identity = get_random_identity()
    
    # Random User Agent to avoid simple blocking
    headers = {
        'User-Agent': USER_AGENT_ROTATOR.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

    try:
        # ---------------------------------------------------------
        # STEP 1: FIND A PRODUCT (The Entry Point)
        # ---------------------------------------------------------
        variant_id = None
        
        # Method A: Try products.json (Fastest)
        try:
            prod_req = session.get(f"{site_url}/products.json?limit=3", headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
            if prod_req.status_code == 200:
                products = prod_req.json().get('products', [])
                for product in products:
                    for variant in product.get('variants', []):
                        if variant.get('available'):
                            variant_id = variant['id']
                            break
                    if variant_id: break
        except:
            pass

        # Method B: Scrape Homepage (Fallback)
        if not variant_id:
            try:
                home_req = session.get(site_url, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
                soup = BeautifulSoup(home_req.text, 'html.parser')
                # Try to find a link to a product
                for link in soup.find_all('a', href=True):
                    if '/products/' in link['href']:
                        prod_page_url = f"{site_url}{link['href']}" if link['href'].startswith('/') else link['href']
                        prod_page = session.get(prod_page_url, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
                        # Extract variant ID from page source
                        if 'variantId' in prod_page.text:
                            variant_id = find_between(prod_page.text, 'variantId":', ',')
                        if not variant_id:
                            variant_id = find_between(prod_page.text, 'variantId = ', ';')
                        if variant_id: break
            except:
                pass

        if not variant_id:
            return "DEAD", "No Products Found", "N/A"

        # ---------------------------------------------------------
        # STEP 2: ADD TO CART
        # ---------------------------------------------------------
        cart_url = f"{site_url}/cart/add.js"
        payload = {'id': variant_id, 'quantity': 1}
        
        # Add Ajax Header
        cart_headers = headers.copy()
        cart_headers['X-Requested-With'] = 'XMLHttpRequest'
        
        cart_req = session.post(cart_url, data=payload, headers=cart_headers, timeout=REQUEST_TIMEOUT, verify=False)
        
        if cart_req.status_code not in [200, 201]:
            return "DEAD", "Cart Error", "N/A"

        # ---------------------------------------------------------
        # STEP 3: INITIATE CHECKOUT
        # ---------------------------------------------------------
        checkout_req = session.get(f"{site_url}/checkout", headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
        final_url = checkout_req.url

        # 🚨 CAPTCHA CHECK 1 🚨
        if "challenge" in final_url or "recaptcha" in final_url or "checkpoint" in final_url:
            return "CAPTCHA", "Captcha Detected (Redirect)", "N/A"

        # Extract Authenticity Token
        soup = BeautifulSoup(checkout_req.text, 'html.parser')
        auth_token = soup.find('input', {'name': 'authenticity_token'})
        
        if not auth_token:
            # Try Regex
            token_val = find_between(checkout_req.text, 'name="authenticity_token" value="', '"')
            if not token_val:
                return "DEAD", "No Token Found", "N/A"
            auth_token = {'value': token_val}
            
        auth_token = auth_token['value']

        # ---------------------------------------------------------
        # STEP 4: SUBMIT CUSTOMER INFO
        # ---------------------------------------------------------
        info_payload = {
            '_method': 'patch',
            'authenticity_token': auth_token,
            'previous_step': 'contact_information',
            'step': 'shipping_method',
            'checkout[email]': identity['email'],
            'checkout[buyer_accepts_marketing]': '0',
            'checkout[shipping_address][first_name]': identity['first_name'],
            'checkout[shipping_address][last_name]': identity['last_name'],
            'checkout[shipping_address][address1]': identity['address'],
            'checkout[shipping_address][address2]': '',
            'checkout[shipping_address][city]': identity['city'],
            'checkout[shipping_address][country]': identity['country'],
            'checkout[shipping_address][province]': identity['state'],
            'checkout[shipping_address][zip]': identity['zip'],
            'checkout[shipping_address][phone]': identity['phone'],
            'checkout[remember_me]': '0',
            'checkout[client_details][browser_width]': '1920',
            'checkout[client_details][javascript_enabled]': '1'
        }

        ship_req = session.post(final_url, data=info_payload, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
        
        # 🚨 CAPTCHA CHECK 2 🚨
        if "challenge" in ship_req.url or "recaptcha" in ship_req.text.lower():
            return "CAPTCHA", "Captcha Detected (After Info)", "N/A"

        # ---------------------------------------------------------
        # STEP 5: SUBMIT SHIPPING METHOD
        # ---------------------------------------------------------
        # Try to extract a valid shipping rate
        shipping_rate = "shopify-Standard-0.00" # Default guess
        
        # Try to find actual rate in HTML
        if 'data-shipping-method="' in ship_req.text:
            shipping_rate = find_between(ship_req.text, 'data-shipping-method="', '"')

        ship_method_payload = {
            '_method': 'patch',
            'authenticity_token': auth_token,
            'previous_step': 'shipping_method',
            'step': 'payment_method',
            'checkout[shipping_rate][id]': shipping_rate
        }

        pay_req = session.post(final_url, data=ship_method_payload, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)

        # ---------------------------------------------------------
        # STEP 6: EXTRACT GATEWAY & PREPARE PAYMENT
        # ---------------------------------------------------------
        soup_pay = BeautifulSoup(pay_req.text, 'html.parser')
        
        # Find Gateway ID
        gateway_input = soup_pay.find('input', {'name': 'checkout[payment_gateway]'})
        if not gateway_input:
             # Sometimes it's in a different format
             gateway_id = find_between(pay_req.text, 'name="checkout[payment_gateway]" value="', '"')
        else:
             gateway_id = gateway_input['value']

        if not gateway_id:
            return "DEAD", "No Gateway Found", "N/A"

        # Find Total Price
        price_input = soup_pay.find('input', {'name': 'checkout[total_price]'})
        total_price = price_input['value'] if price_input else "1000"

        # ---------------------------------------------------------
        # STEP 7: TOKENIZE CARD (Shopify Vault)
        # ---------------------------------------------------------
        # Use Test Card: 4000 0000 0000 0000
        # This determines if the gateway is talking to the processor
        
        payment_session_scope = urlparse(site_url).netloc
        
        vault_payload = {
            "credit_card": {
                "number": "4000000000000000",
                "name": f"{identity['first_name']} {identity['last_name']}",
                "month": "12",
                "year": "2029",
                "verification_value": "123"
            },
            "payment_session_scope": payment_session_scope
        }

        vault_headers = {
            'User-Agent': headers['User-Agent'],
            'Content-Type': 'application/json',
            'Origin': 'https://checkout.shopifycs.com',
            'Referer': 'https://checkout.shopifycs.com/'
        }

        vault_req = session.post('https://deposit.us.shopifycs.com/sessions', json=vault_payload, headers=vault_headers, timeout=REQUEST_TIMEOUT, verify=False)
        
        if vault_req.status_code != 200:
            return "DEAD", "Tokenization Failed", gateway_id

        payment_token = vault_req.json().get('id')

        # ---------------------------------------------------------
        # STEP 8: FINAL CHARGE ATTEMPT
        # ---------------------------------------------------------
        final_payload = {
            '_method': 'patch',
            'authenticity_token': auth_token,
            'previous_step': 'payment_method',
            'step': '',
            's': payment_token,
            'checkout[payment_gateway]': gateway_id,
            'checkout[credit_card][vault]': 'false',
            'checkout[total_price]': total_price,
            'complete': '1',
            'checkout[client_details][browser_width]': '1920',
            'checkout[client_details][javascript_enabled]': '1',
            'checkout[client_details][color_depth]': '24',
            'checkout[client_details][java_enabled]': 'false'
        }

        final_req = session.post(final_url, data=final_payload, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
        
        # ---------------------------------------------------------
        # STEP 9: RESULT ANALYSIS
        # ---------------------------------------------------------
        response_text = final_req.text.lower()
        response_url = final_req.url

        # Check for Polling (Processing Page)
        if "/processing" in response_url:
            time.sleep(2)
            poll_req = session.get(f"{response_url}?from_processing_page=1", headers=headers, verify=False)
            response_text = poll_req.text.lower()

        # 🚨 CAPTCHA CHECK 3 🚨
        if "challenge" in response_url or "recaptcha" in response_text:
             return "CAPTCHA", "Captcha on Charge", gateway_id

        # LIVE INDICATORS
        # If the gateway returns a specific decline, it means the site is LIVE and processed the request.
        live_keywords = [
            "security code",
            "declined",
            "insufficient funds",
            "card was declined",
            "zip code",
            "cvv",
            "does not match",
            "cannot be processed"
        ]

        if any(key in response_text for key in live_keywords):
            return "LIVE", "Card Declined (Gateway Alive)", gateway_id
        elif "thank you" in response_text or "confirmed" in response_text:
            return "LIVE", "Charged Successfully (Insane!)", gateway_id
        else:
            # Dead or Soft Decline
            return "DEAD", "Unknown Response / Generic Error", gateway_id

    except Exception as e:
        return "DEAD", f"Error: {str(e)}", "N/A"

# ==========================================
# 🧵 THREAD MANAGER & REPORTING
# ==========================================

def run_checker_job(message, sites):
    """Manages the checking threads and batch reporting."""
    job_id = str(uuid.uuid4())[:8]
    
    # Initialize Job Stats
    active_jobs[job_id] = {
        'total': len(sites),
        'checked': 0,
        'live': 0,
        'captcha': 0,
        'dead': 0,
        'start_time': time.time()
    }

    bot.reply_to(message, 
        f"👺 <b>MONSTER JOB STARTED</b>\n\n"
        f"🆔 Job ID: <code>{job_id}</code>\n"
        f"🎯 Target: {len(sites)} sites\n"
        f"🚀 Threads: {MAX_THREADS}\n\n"
        f"<i>Igniting engines...</i>", 
        parse_mode='HTML'
    )

    status_msg = bot.send_message(message.chat.id, "📊 <b>Initializing Dashboard...</b>", parse_mode='HTML')

    live_buffer = []
    checked_count = 0
    
    # Thread Pool
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(check_site_ultimate, site): site for site in sites}
        
        last_edit_time = time.time()

        for future in as_completed(futures):
            site = futures[future]
            try:
                status, msg, gateway = future.result()
                
                # Update Stats
                active_jobs[job_id]['checked'] += 1
                checked_count += 1
                
                if status == "LIVE":
                    active_jobs[job_id]['live'] += 1
                    formatted_line = f"{site} | {gateway} | {msg}"
                    live_buffer.append(formatted_line)
                elif status == "CAPTCHA":
                    active_jobs[job_id]['captcha'] += 1
                else:
                    active_jobs[job_id]['dead'] += 1

                # 📦 BATCH REPORTING LOGIC 📦
                # If buffer hits 100, save and send IMMEDIATELY
                if len(live_buffer) >= BATCH_SIZE:
                    send_batch_file(message.chat.id, live_buffer, checked_count)
                    live_buffer = [] # Clear buffer after sending

                # 📊 DASHBOARD UPDATE (Every 5 seconds)
                if time.time() - last_edit_time > 5:
                    update_dashboard(message.chat.id, status_msg.message_id, job_id)
                    last_edit_time = time.time()

            except Exception as e:
                logger.error(f"Thread Error: {e}")

    # Final Cleanup
    # Send remaining buffer
    if live_buffer:
        send_batch_file(message.chat.id, live_buffer, checked_count, final=True)

    update_dashboard(message.chat.id, status_msg.message_id, job_id, final=True)

def update_dashboard(chat_id, message_id, job_id, final=False):
    """Updates the Telegram live status message."""
    stats = active_jobs[job_id]
    elapsed = time.time() - stats['start_time']
    cpm = int((stats['checked'] / elapsed) * 60) if elapsed > 0 else 0
    
    # Progress Bar
    percent = round((stats['checked'] / stats['total']) * 100, 1)
    bar_len = 15
    filled = int(bar_len * percent / 100)
    bar = "█" * filled + "░" * (bar_len - filled)

    header = "🏁 <b>JOB COMPLETED</b>" if final else "👺 <b>MONSTER HUNTING</b>"

    text = (
        f"{header}\n"
        f"<code>{bar}</code> {percent}%\n\n"
        f"✅ <b>Live:</b> {stats['live']}\n"
        f"🛡️ <b>Captcha (Skipped):</b> {stats['captcha']}\n"
        f"💀 <b>Dead:</b> {stats['dead']}\n"
        f"⚡ <b>Speed:</b> {cpm} CPM\n"
        f"📉 <b>Progress:</b> {stats['checked']}/{stats['total']}"
    )
    
    try:
        bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML')
    except:
        pass

def send_batch_file(chat_id, lines, count, final=False):
    """Sends a text file with working sites."""
    try:
        timestamp = int(time.time())
        filename = f"Live_Sites_Batch_{count}_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("========== MONSTER BOT WORKING SITES ==========\n")
            f.write("\n".join(lines))
        
        caption = f"📦 <b>Batch Hit!</b> Found {len(lines)} working sites."
        if final:
            caption = f"✅ <b>Final Batch!</b> Last {len(lines)} working sites."

        with open(filename, 'rb') as f:
            bot.send_document(chat_id, f, caption=caption, parse_mode='HTML')
        
        os.remove(filename) # Clean up disk
    except Exception as e:
        logger.error(f"Error sending file: {e}")

# ==========================================
# 🤖 BOT COMMAND HANDLERS
# ==========================================

@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, 
        "👺 <b>I AM THE MONSTER BOT</b> 👺\n\n"
        "I hunt Shopify sites. I bypass bad ones.\n"
        "<b>Drag and drop your .txt file to start.</b>\n\n"
        "⚡ Rules:\n"
        "1. Captcha sites = TRASH 🗑️\n"
        "2. Live Gateways = SAVED ✅\n"
        "3. Speed = MAXIMAL 🚀",
        parse_mode='HTML'
    )

@bot.message_handler(content_types=['document'])
def handle_doc(message):
    if str(message.from_user.id) != str(OWNER_ID):
        bot.reply_to(message, "🚫 <b>You are not the Monster Master.</b>")
        return

    if not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "❌ <b>Only .txt files are food for the monster.</b>")
        return

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        content = downloaded.decode('utf-8', errors='ignore')
        
        # Parse Sites
        sites = [line.strip() for line in content.split('\n') if len(line.strip()) > 5]
        sites = list(set(sites)) # Deduplicate
        
        if not sites:
            bot.reply_to(message, "❌ <b>File is empty.</b>")
            return

        # Start Job in Thread
        threading.Thread(target=run_checker_job, args=(message, sites)).start()

    except Exception as e:
        bot.reply_to(message, f"❌ <b>Error loading file:</b> {e}")

# ==========================================
# 🚀 ENTRY POINT
# ==========================================
if __name__ == "__main__":
    # 1. Start Keep-Alive Server (For Render)
    print("🌍 Starting Render Keep-Alive Server...")
    start_keep_alive()
    
    # 2. Start Bot
    print("👺 Monster Bot is polling...")
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=10)
    except Exception as e:
        print(f"❌ Critical Bot Error: {e}")