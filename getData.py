import re
import certifi
import requests
import urllib3
from dataApp import coin_list_usdt, coin_list, LIMIT_ORDER_BOOK
import ccxt

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()

retry = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429,500,502,503,504],
)

adapter = HTTPAdapter(max_retries=retry)

session.mount("https://", adapter)
session.mount("http://", adapter)

# 1. Спот MEXC
# Отключаем предупреждения про SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
def get_mexc_spot_data():
    url = "https://api.mexc.com/api/v3/ticker/price"
    try:
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Ошибка API {url}: {e}")
            return {}
        response.raise_for_status()
        data = response.json()

        # print(data)

        result = {}
        for item in data:
            symbol = item["symbol"]            # Пример: "BTCUSDT"
            price = float(item["price"])       # Текущая цена

            # MEXC спот отдаёт "BTCUSDT" без разделителя — приводим к общему
            # формату BASE_USDT, иначе монеты не матчатся с остальными биржами
            if not symbol.endswith("USDT"):
                continue
            clean_symbol = symbol[:-4] + "_USDT"

            if price != 0:
                result[clean_symbol] = price

        return result

    except Exception as e:
        print("Ошибка при получении спот-данных:", e)
        return {}

# 2. Фьючерсы MEXC
def get_mexc_futures_data():
    url = "https://contract.mexc.com/api/v1/contract/ticker"
    try:
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Ошибка API {url}: {e}")
            return {}
        response.raise_for_status()
        data = response.json()

        # print(data)


        result = {}
        for item in data.get("data", []):
            symbol = item["symbol"]                 # Пример: "BTC_USDT"
            price = float(item["lastPrice"])        # Текущая цена
            volume = float(item["volume24"])        # Объём за 24 часа
            # funding_rate = float(item["fundingRate"])
            # if price == 0:
            #     print(price, "get_mexc_futures_data")



            # result[symbol] = {
            #     "price": price,
            #     "volume": volume,
            #     # "funding_rate": funding_rate
            # }


            if price != 0:
                result[symbol] = {
                    "price": price,
                    "volume": volume,
                    # "funding_rate": funding_rate
                }

        return result

    except Exception as e:
        print("Ошибка при получении данных:", e)
        return {}

# 3. Спот Gate.io
def get_gateio_spot_data():
    url = "https://api.gateio.ws/api/v4/spot/tickers"
    try:
        try:
            response = session.get(url, verify=False, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Ошибка API {url}: {e}")
            return {}
        response.raise_for_status()
        data = response.json()

        # print(data)


        result = {}
        for item in data:
            symbol = item["currency_pair"]   # Пример: BTC_USDT
            price = float(item["last"])      # Последняя цена
            # result[symbol] = price
            # if price == 0:
            #     print(price, "get_gateio_spot_data")

            if price != 0:
                result[symbol] = price

        return result

    except Exception as e:
        print("Ошибка при получении спота с Gate.io:", e)
        return {}

# 4. Фьючерсы Gate.io (USDT-Perpetual)
def get_gateio_futures_data():
    url = "https://api.gateio.ws/api/v4/futures/usdt/tickers"
    try:
        try:
            response = session.get(url, verify=False, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Ошибка API {url}: {e}")
            return {}
        response.raise_for_status()
        data = response.json()

        # print(data)


        result = {}
        for item in data:
            symbol = item["contract"]         # Пример: BTC_USDT
            price = float(item["last"])
            volume = float(item["volume_24h"])
            # funding_rate = float(item["funding_rate"])
            # if price == 0:
            #     print(price, "get_gateio_futures_data")

            # result[symbol] = {
            #     "price": price,
            #     "volume": volume,
            #     # "funding_rate": funding_rate
            # }

            if price != 0:
                result[symbol] = {
                    "price": price,
                    "volume": volume,
                    # "funding_rate": funding_rate
                }

        return result

    except Exception as e:
        print("Ошибка при получении фьючерсов с Gate.io:", e)
        return {}



# bindx
def get_spot_prices_bingx():
    url = "https://open-api.bingx.com/openApi/spot/v1/ticker/price"
    try:
        try:
            response = session.get(url, verify=False, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Ошибка API {url}: {e}")
            return {}
        response.raise_for_status()
        data = response.json()

        result = {}
        for item in data.get("data", []):
            symbol = item.get("symbol")        # Пример: "BTC-USDT"
            trades = item.get("trades", [])
            if not symbol or not trades:
                continue

            # BingX отдаёт символ через дефис ("BTC-USDT") — приводим к BASE_USDT
            clean_symbol = symbol.replace("-", "_")
            if not clean_symbol.endswith("_USDT"):
                continue

            price = trades[0].get("price")
            try:
                price = float(price)
            except (TypeError, ValueError):
                continue

            if price != 0:
                result[clean_symbol] = price

        return result

    except requests.RequestException as e:
        print("Ошибка запроса:", e)
        return {}

def get_futures_prices_with_real_price_bingx():
    url = "https://open-api.bingx.com/openApi/swap/v2/quote/price"
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Ошибка API {url}: {e}")
        return {}
    data = response.json()

    if data.get("code") != 0:
        raise Exception(f"API error: {data.get('msg')}")

    result = {}

    for item in data.get("data", []):
        raw_symbol = item["symbol"]
        price = float(item["price"])

        try:
            if price != 0:
                # Извлекаем множитель из начала (если он есть)
                match = re.match(r"(\d+)([A-Z]+-[A-Z]+)", raw_symbol)
                if match:
                    multiplier = int(match.group(1))
                    symbol = str(match.group(2)).replace("-", "_")
                    real_price = price / multiplier
                else:
                    symbol = str(raw_symbol).replace("-", "_")
                    real_price = price

                result[symbol] = {
                    "price": real_price,
                    "volume": 0
                }
        except Exception as e:
            continue
    return result



# для bybit
def get_spot_prices_bybit():
    url = "https://api.bybit.com/v5/market/tickers"
    params = {
        "category": "spot"
    }
    try:
        response = session.get(url, params=params, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Ошибка API {url}: {e}")
        return {}
    data = response.json()

    result = {}
    for ticker in data['result']['list']:
        try:
            symbol = ticker['symbol']
            price = float(ticker['lastPrice'])
            if price != 0:
                result[symbol.replace("USDT", "_USDT")] = price
        except:
            continue
    return result


def get_futures_data_bybit():

    url = "https://api.bybit.com/v5/market/tickers"

    result = {}

    for category in ["linear", "inverse"]:

        params = {"category": category}

        try:
            response = session.get(url, params=params, timeout=10)
            data = response.json()
        except Exception as e:
            print(f"Ошибка Bybit {category}: {e}")
            continue

        for ticker in data['result']['list']:

            try:

                raw_symbol = ticker['symbol']
                price = float(ticker['lastPrice'])

                match = re.match(r'^(\d+)([A-Z]+USDT)$', raw_symbol)

                if match:
                    scale = int(match.group(1))
                    clean_symbol = match.group(2)
                    price /= scale
                else:
                    clean_symbol = raw_symbol

                if price > 0:

                    result[clean_symbol.replace("USDT", "_USDT")] = {
                        "price": price,
                        "volume": 0
                    }

            except:
                continue

    return result


def get_spot_prices_bitget():
    try:
        url = "https://api.bitget.com/api/v2/spot/market/tickers"
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Ошибка API {url}: {e}")
            return {}
        data = response.json()

        result = {}

        for ticker in data['data']:
            try:
                symbol = ticker['symbol']
                price = float(ticker['lastPr'])

                if price != 0:
                    result[symbol.replace("USDT", "_USDT")] = price

            except Exception as e:
                print("ticker error:", e)
                continue

        # print(f"BitGet parsed: {result}")
        return result

    except Exception as e:
        print(f"BitGet ERROR: {e}")
        return {}


def get_futures_data_bitget():

    url = "https://api.bitget.com/api/v2/mix/market/tickers"
    result = {}

    print("start get_futures_data_bitget")

    for product_type in ["USDT-FUTURES", "COIN-FUTURES"]:

        params = {"productType": product_type}

        try:
            response = session.get(url, params=params, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Ошибка API {url}: {e}")
            return {}
        data = response.json()

        # print(data)

        if data.get("data") is None:
            continue

        for ticker in data["data"]:
            try:

                raw_symbol = ticker["symbol"]
                price = float(ticker["lastPr"])
                volume = float(ticker.get("baseVolume", 0))

                if price != 0:
                    result[raw_symbol.replace("USDT", "_USDT")] = {
                        "price": price,
                        "volume": volume
                    }

            except Exception as e:
                print("ticker error:", e)
                continue

    # print("Bitget futures parsed:", result)

    return result


def get_leveex_spot_coins():
    """
    Получает и возвращает массив всех спотовых монет и их цен с биржи LeveX.
    
    Returns:
        dict: Словарь, содержащий информацию о спотовых парах, ценах и объемах.
              Возвращает пустой словарь в случае ошибки.
    """
    # Замените 'https://api.leveex.com/v1/spot/markets' на актуальный URL API,
    # если он известен. Это пример.
    api_url = 'https://api.leveex.com/v1/spot/markets'
    
    try:
        response = requests.get(api_url)
        try:
            response = session.get(api_url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Ошибка API {api_url}: {e}")
            return {}
        # Проверка, что запрос был успешным (код состояния 200)
        response.raise_for_status()
        
        # Парсинг JSON-ответа
        data = response.json()
        
        # Вывод данных для отладки
        # print(json.dumps(data, indent=4))
        
        # Возвращаем данные
        return data

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении данных с LeveX API: {e}")
        return {}
    except json.JSONDecodeError as e:
        print(f"Ошибка при декодировании JSON: {e}")
        return {}

# Binance Spot
def get_binance_spot_data():
    url = "https://api.binance.com/api/v3/ticker/price"
    try:
        try:
            response = session.get(url,timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Ошибка API {url}: {e}")
            return {}
        response.raise_for_status()
        data = response.json()

        result = {}
        for item in data:
            symbol = item["symbol"]
            price = float(item["price"])
            
            # Фильтруем пары, заканчивающиеся на USDT и преобразуем "BTCUSDT" -> "BTC_USDT"
            if symbol.endswith("USDT"):
                clean_symbol = symbol.replace("USDT", "_USDT")
                if price != 0:
                    result[clean_symbol] = price
        return result

    except Exception as e:
        print(f"Ошибка при получении спот-данных Binance: {e}")
        return {}


# Binance Futures (USDT-M)
def get_binance_futures_data():
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    try:
        try:
            response = session.get(url,timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Ошибка API {url}: {e}")
            return {}
        response.raise_for_status()
        data = response.json()

        result = {}
        for item in data:
            symbol = item["symbol"]
            if symbol.endswith("USDT"): # Только USDT-контракты
                try:
                    price = float(item["lastPrice"])
                    # Volume в базовой валюте, но для сравнения это не критично,
                    # хотя вы собираете объем в USD. Используем объем в USDT.
                    volume = float(item.get("quoteVolume", 0)) 
                    
                    clean_symbol = symbol.replace("USDT", "_USDT")
                    
                    if price != 0:
                        result[clean_symbol] = {
                            "price": price,
                            "volume": volume,
                        }
                except (TypeError, ValueError):
                    continue
        return result

    except Exception as e:
        print(f"Ошибка при получении фьючерсных данных Binance: {e}")
        return {}
 

def get_hyperliquid_data_futures():
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "allMids"}
    headers = {"Content-Type": "application/json"}
    try:
        r = requests.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        result = {}
        for k, v in data.items():
            # фильтруем непонятные идентификаторы (начинающиеся с @ или цифр)
            if re.match(r'^[A-Z0-9]{2,}$', k):
                result[f"{k}_USDT"] = {"price": float(v), "volume": 0}
        return result
    except Exception as e:
        print(f"Ошибка Hyperliquid: {e}")
        return {}
    

def get_htx_spot_data():
    url = "https://api.huobi.pro/market/tickers"  # Спотовые котировки
    try:
        resp = requests.get(url, timeout=10, verify=certifi.where())
        resp.raise_for_status()
        js = resp.json()

        if js.get("status") != "ok" or "data" not in js:
            print("Unexpected response format:", js)
            return {}

        result = {}
        for item in js["data"]:
            symbol = item["symbol"]  # Например, 'btcusdt'
            price = float(item["close"])
            if symbol.endswith("usdt"):  # Huobi использует нижний регистр
                clean = symbol.upper().replace("USDT", "_USDT")
                if price != 0:
                    result[clean] = price
        return result

    except Exception as e:
        print(f"Ошибка при получении спот‑данных HTX: {e}")
        return {}
    
def get_htx_futures_data():
    url = "https://api.hbdm.com/linear-swap-ex/market/detail/batch_merged"  # исправленный эндпоинт
    try:
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Ошибка API {url}: {e}")
            return {}
        response.raise_for_status()
        data = response.json()

        # Проверяем ключи
        if "ticks" not in data:
            print("Unexpected futures response format:", data)
            return {}

        result = {}
        for item in data["ticks"]:
            symbol = item.get("contract_code", "")
            price_str = item.get("close")  # цена закрытия
            if symbol.endswith("-USDT") and price_str:
                clean_symbol = symbol.replace("-USDT", "_USDT")
                try:
                    price = float(price_str)
                    result[clean_symbol] = price
                except (ValueError, TypeError):
                    continue

        return result

    except Exception as e:
        print(f"Ошибка при получении фьючерсных данных HTX: {e}")
        return {}
    

def get_xt_futures_data() -> dict:
    """
    Получает все фьючерсные (бессрочные/linear swap) пары с XT.com и их последние цены, 
    используя надежный фильтр по типу рынка.
    
    Формат вывода: {'BTC_USDT': 68000.5, 'ETH_USDT': 3400.2, ...}
    """
    try:
        # 1. Инициализация биржи
        exchange = ccxt.xt()
        
        # 2. Загрузка всех рынков (маркетов)
        # Это более надежно, чем полагаться только на defaultType
        markets = exchange.load_markets()
        
        # 3. Фильтрация фьючерсных рынков (Futures/Swap)
        futures_symbols = [
            symbol for symbol, market in markets.items()
            if market['type'] == 'swap' or market['type'] == 'future'
        ]
        
        if not futures_symbols:
            print("⚠️ На XT.com не найдено активных фьючерсных/своповых символов.")
            return {}

        # 4. Получение цен (тикеров) только для отфильтрованных символов
        result = {}
        # Используем fetch_tickers с указанием списка символов для эффективности
        tickers = exchange.fetch_tickers(symbols=futures_symbols)
        
        # 5. Обработка данных и приведение к требуемому формату
        for symbol, ticker_data in tickers.items():
            price = ticker_data.get('last')
            
            # Проверка на наличие USDT в котируемой валюте и ненулевую цену
            if '/USDT' in symbol and price is not None and price != 0:
                # Приводим к формату 'КОИН_USDT'
                clean_symbol = symbol.split(':')[0].replace('/', '_')
                result[clean_symbol] = float(price)
        
        return result

    except Exception as e:
        print(f"❌ Ошибка при получении фьючерсных данных XT.com: {e}")
        return {}
    
def get_xt_spot_data() -> dict:
    """
    Получает все спотовые торговые пары с XT.com и их последние цены.
    
    Формат вывода: {'BTC_USDT': 68000.5, 'ETH_USDT': 3400.2, ...}
    """
    try:
        # 1. Инициализация биржи
        exchange = ccxt.xt()
        
        # 2. Получение всех тикеров (цен)
        # Устанавливаем тип по умолчанию как 'spot'
        exchange.options['defaultType'] = 'spot'
        
        # fetch_tickers возвращает данные для всех пар
        tickers = exchange.fetch_tickers()
        
        result = {}
        
        # 3. Обработка данных и приведение к требуемому формату
        for symbol, ticker_data in tickers.items():
            # Пример символа из CCXT: 'BTC/USDT'
            
            # Проверяем, что это пара к USDT (игнорируем другие базовые валюты, как в вашем примере)
            if '/USDT' in symbol:
                # Извлекаем цену
                price = ticker_data.get('last')
                
                if price is not None and price != 0:
                    # Приводим к формату 'КОИН_USDT'
                    clean_symbol = symbol.replace('/', '_')
                    result[clean_symbol] = float(price)
        
        return result

    except Exception as e:
        print(f"❌ Ошибка при получении спот-данных XT.com: {e}")
        return {}


def get_okx_spot_data() -> dict:
    """
    Получает все спотовые торговые пары OKX и их последние цены.
    Формат вывода: {'BTC_USDT': 68000.5, ...}
    """
    try:
        exchange = ccxt.okx()
        # 1. Загружаем все рынки для надежной фильтрации
        markets = exchange.load_markets()
        
        # 2. Фильтруем спотовые пары к USDT (или похожим стейблкоинам)
        spot_symbols = [s for s, m in markets.items() 
                        if m['type'] == 'spot' and 'USDT' in m['quote']]
        
        # 3. Получаем тикеры только для отфильтрованных символов
        tickers = exchange.fetch_tickers(symbols=spot_symbols)
        result = {}
        
        for symbol, ticker_data in tickers.items():
            price = ticker_data.get('last')
            if price is not None and price != 0:
                # OKX Spot: 'BASE/USDT' -> 'BASE_USDT'
                clean_symbol = symbol.replace('/', '_')
                result[clean_symbol] = float(price)
        
        return result
    except Exception as e:
        print(f"❌ Ошибка при получении спот-данных OKX: {e}")
        return {}


def get_okx_futures_data() -> dict:
    """
    Получает все бессрочные фьючерсные (Swap) пары OKX и их последние цены.
    Формат вывода: {'BTC_USDT': 68000.5, ...}
    """
    try:
        exchange = ccxt.okx()
        markets = exchange.load_markets()
        
        # Фильтруем бессрочные свопы (swap) с котированием к USDT
        swap_symbols = [s for s, m in markets.items() 
                        if m['type'] == 'swap' and 'USDT' in m['quote']]
        
        tickers = exchange.fetch_tickers(symbols=swap_symbols)
        result = {}
        
        for symbol, ticker_data in tickers.items():
            price = ticker_data.get('last')
            if price is not None and price != 0:
                # Символ OKX Swap может содержать лишние части, оставляем только BASE_QUOTE
                clean_symbol = symbol.split(':')[0].replace('/', '_')
                result[clean_symbol] = float(price)
        
        return result
    except Exception as e:
        print(f"❌ Ошибка при получении фьючерсных данных OKX: {e}")
        return {}
    
def get_coinex_spot_data() -> dict:
    """Получает все спотовые торговые пары CoinEx и их последние цены."""
    url = "https://api.coinex.com/v2/spot/ticker"
    try:
        try:
            response = session.get(url,timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Ошибка API {url}: {e}")
            return {}
        response.raise_for_status()
        data = response.json()

        # CoinEx отдаёт market как "BTCUSDT" без разделителя — приводим к BASE_USDT,
        # иначе монеты CoinEx не матчатся ни с одной другой биржей
        result = {}
        for item in data.get('data', []):
            market = item.get('market', '')
            if not market.endswith('USDT'):
                continue
            try:
                price = float(item['last'])
            except (TypeError, ValueError, KeyError):
                continue
            if price != 0:
                result[market[:-4] + '_USDT'] = price
        return result
    except Exception as e:
        print(f"Ошибка при получении спотовых данных: {e}")
        return {}

def get_coinex_futures_data() -> dict:
    """Получает все фьючерсные торговые пары CoinEx и их последние цены."""
    url = "https://api.coinex.com/v2/futures/ticker"
    try:
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Ошибка API {url}: {e}")
            return {}
        response.raise_for_status()
        data = response.json()

        # CoinEx фьючерс: market "BTCUSDT" -> BASE_USDT; формат как у других фьючерсов
        # (dict c price/volume), чтобы scan и возможный учёт объёма работали единообразно
        result = {}
        for item in data.get('data', []):
            market = item.get('market', '')
            if not market.endswith('USDT'):
                continue
            try:
                price = float(item['last'])
            except (TypeError, ValueError, KeyError):
                continue
            if price == 0:
                continue
            try:
                volume = float(item.get('value', item.get('volume', 0)) or 0)
            except (TypeError, ValueError):
                volume = 0
            result[market[:-4] + '_USDT'] = {"price": price, "volume": volume}
        return result
    except Exception as e:
        print(f"Ошибка при получении фьючерсных данных: {e}")
        return {}

# ==================== PHEMEX ====================
# Фьючерсы Phemex (USDT-M). Некоторые контракты называются с множителем
# ("u1000PEPEUSDT"), поэтому храним соответствие BASE_USDT -> (сырой символ, множитель),
# чтобы стакан запрашивался по правильному символу и цены делились на множитель.
PHEMEX_FUT_SYMBOLS = {}
ASTER_FUT_SYMBOLS = {}

_MULTIPLIER_RE = re.compile(r'^u?(1000000|100000|10000|1000)([A-Z0-9]+)USDT$')


def _split_multiplier(raw_symbol):
    """'1000PEPEUSDT' / 'u1000PEPEUSDT' -> ('PEPE_USDT', 1000); 'BTCUSDT' -> ('BTC_USDT', 1)."""
    m = _MULTIPLIER_RE.match(raw_symbol)
    if m:
        return m.group(2) + "_USDT", int(m.group(1))
    if raw_symbol.endswith("USDT") and len(raw_symbol) > 4:
        return raw_symbol[:-4] + "_USDT", 1
    return None, None


def get_phemex_futures_data():
    url = "https://api.phemex.com/md/v2/ticker/24hr/all"
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Ошибка API {url}: {e}")
        return {}

    result = {}
    for item in data.get("result", []) or []:
        try:
            raw_symbol = item.get("symbol", "")
            clean_symbol, mult = _split_multiplier(raw_symbol)
            if not clean_symbol:
                continue
            price = float(item.get("closeRp") or item.get("lastRp") or 0)
            if price == 0:
                continue
            volume = float(item.get("turnoverRv", 0) or 0)
            PHEMEX_FUT_SYMBOLS[clean_symbol] = (raw_symbol, mult)
            result[clean_symbol] = {"price": price / mult, "volume": volume}
        except (TypeError, ValueError):
            continue
    return result


# Спот Phemex: цены там передаются в масштабированном виде (Ep), масштаб зависит
# от пары, поэтому берём через ccxt — он сам загружает настройки пар и пересчитывает.
_phemex_ccxt = None


def _get_phemex_ccxt():
    global _phemex_ccxt
    if _phemex_ccxt is None:
        ex = ccxt.phemex({'timeout': 15000})
        ex.load_markets()
        _phemex_ccxt = ex
    return _phemex_ccxt


def get_phemex_spot_data():
    try:
        ex = _get_phemex_ccxt()
        tickers = ex.fetch_tickers(params={'type': 'spot'})
        result = {}
        for symbol, t in tickers.items():
            if not symbol.endswith('/USDT') or ':' in symbol:
                continue
            price = t.get('last')
            if price:
                result[symbol.replace('/', '_')] = float(price)
        return result
    except Exception as e:
        print(f"❌ Ошибка при получении спот-данных Phemex: {e}")
        return {}


# ==================== ASTER ====================
# API Aster повторяет API Binance (fapi / sapi).

def get_aster_futures_data():
    url = "https://fapi.asterdex.com/fapi/v1/ticker/24hr"
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Ошибка API {url}: {e}")
        return {}

    result = {}
    for item in data if isinstance(data, list) else []:
        try:
            raw_symbol = item.get("symbol", "")
            clean_symbol, mult = _split_multiplier(raw_symbol)
            if not clean_symbol:
                continue
            price = float(item.get("lastPrice", 0) or 0)
            if price == 0:
                continue
            volume = float(item.get("quoteVolume", 0) or 0)
            ASTER_FUT_SYMBOLS[clean_symbol] = (raw_symbol, mult)
            result[clean_symbol] = {"price": price / mult, "volume": volume}
        except (TypeError, ValueError):
            continue
    return result


def get_aster_spot_data():
    url = "https://sapi.asterdex.com/api/v1/ticker/price"
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Ошибка API {url}: {e}")
        return {}

    result = {}
    for item in data if isinstance(data, list) else []:
        try:
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT") or len(symbol) <= 4:
                continue
            price = float(item.get("price", 0) or 0)
            if price != 0:
                result[symbol[:-4] + "_USDT"] = price
        except (TypeError, ValueError):
            continue
    return result
