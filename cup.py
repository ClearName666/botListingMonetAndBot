import time
import ccxt

import certifi

import requests

from dataApp import LIMIT_ORDER_BOOK, MIN_VOLUME

import requests

# Кэш списка фьючерсных рынков XT.com
xt_futures_markets = set()
xt_markets_last_update = 0
XT_MARKETS_UPDATE_INTERVAL = 300  # 5 минут

HTX_SPOT_MARKETS = set()
HTX_LAST_UPDATE = 0
HTX_UPDATE_INTERVAL = 300  # 5 минут

# =============== КЭШ ===============
cach = {
    "MEXC":     {"spot": {}, "futures": {}},
    "Gate":     {"spot": {}, "futures": {}},
    "Bingx":    {"spot": {}, "futures": {}},
    "Bybit":    {"spot": {}, "futures": {}},
    "BitGet":   {"spot": {}, "futures": {}},
    "Binance":  {"spot": {}, "futures": {}},
    "HTX":      {"spot": {}, "futures": {}},
    "XT":       {"spot": {}, "futures": {}},
    "Hyperliquid": {"spot": {}, "futures": {}},
    "OKX":      {"spot": {}, "futures": {}},
    "Phemex":   {"spot": {}, "futures": {}},
    "Aster":    {"spot": {}, "futures": {}},
}

def cache_get(exchange: str, market_type: str, symbol: str):
    """Возвращает запись из кеша или None"""
    return cach.get(exchange, {}).get(market_type, {}).get(symbol)

def cache_set(exchange: str, market_type: str, symbol: str, data: dict):
    """Сохраняет данные в кеш"""
    cach[exchange][market_type][symbol] = data

def cache_clear():
    """Очищает весь кеш"""
    for ex in cach:
        cach[ex]["spot"].clear()
        cach[ex]["futures"].clear()
# ===================================

# Вспомогательные функции

def make_request(endpoint, params=None):

    base_url = "https://api.gateio.ws/api/v4"

    response = requests.get(base_url + endpoint, params=params)

    response.raise_for_status()

    return response.json()

def get_contract_multiplier_gate(symbol):

    endpoint = f"/futures/usdt/contracts/{symbol}"

    data = make_request(endpoint)

    return float(data['quanto_multiplier'])

def weighted_average(orders, flag_dollars = False):

    for i in range(len(orders)):

        volume = 0.

        volume_dollars = 0.



        for k in range(i):

            # Определяем формат данных

            if isinstance(orders[k], list) or isinstance(orders[k], tuple):

                price = float(orders[k][0])

                size = float(orders[k][1])

            elif isinstance(orders[k], dict):

                price = float(orders[k]['p'])

                size = float(orders[k]['s'])

            else:

                return 0, 0



            if not flag_dollars:

                volume_dollars += price * size

                volume += size

            else:

                volume_dollars += size

                volume += size / price



            if volume_dollars >= MIN_VOLUME:

                avg_price = volume_dollars / volume

                return avg_price, volume_dollars



    return 0, 0

def update_xt_futures_markets():
    """Обновляет список доступных фьючерсных рынков XT.com"""
    global xt_futures_markets, xt_markets_last_update

    try:
        exchange = ccxt.xt()
        exchange.options["defaultType"] = "future"

        markets = exchange.load_markets()

        # Фильтруем только фьючерсные пары
        xt_futures_markets = {
            m for m, info in markets.items()
            if info.get("type") in ("future", "futures")
        }

        xt_markets_last_update = time.time()
        print(f"🔄 XT Futures Markets обновлены ({len(xt_futures_markets)} пар)")

    except Exception as e:
        print(f"❌ Ошибка обновления списка рынков XT: {e}")


def xt_pair_exists_futures(symbol: str) -> bool:
    """Проверяет существует ли фьючерсная пара XT.com с кэшированием"""
    global xt_markets_last_update

    # Обновить список, если прошло более 5 минут
    if time.time() - xt_markets_last_update >= XT_MARKETS_UPDATE_INTERVAL:
        update_xt_futures_markets()

    # Если список ещё ни разу не загружался
    if not xt_futures_markets:
        update_xt_futures_markets()

    return symbol in xt_futures_markets

def update_htx_spot_markets():
    global HTX_SPOT_MARKETS, HTX_LAST_UPDATE

    try:
        url = "https://api.huobi.pro/v1/common/symbols"
        resp = requests.get(url, timeout=10)
        data = resp.json()

        if "data" not in data:
            print("❌ HTX вернула неожиданный ответ:", data)
            return

        markets = {
            item["symbol"]  # формат "btcusdt"
            for item in data["data"]
        }

        HTX_SPOT_MARKETS = markets
        HTX_LAST_UPDATE = time.time()

        print(f"🔄 HTX SPOT markets обновлены ({len(markets)} пар)")

    except Exception as e:
        print(f"❌ Ошибка обновления HTX markets: {e}")


def htx_symbol_exists(symbol):
    global HTX_LAST_UPDATE

    # Первое обновление или прошло > 5 минут
    if time.time() - HTX_LAST_UPDATE >= HTX_UPDATE_INTERVAL:
        update_htx_spot_markets()

    # Если ещё не загружено — загружаем
    if not HTX_SPOT_MARKETS:
        update_htx_spot_markets()

    return symbol in HTX_SPOT_MARKETS


# ==================== MEXC ====================



def get_order_book_mexc_spot(symbol):
    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("MEXC", "spot", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================


    symbol = symbol.replace("_", "")

    url = f"https://api.mexc.com/api/v3/depth?symbol={symbol}&limit={LIMIT_ORDER_BOOK}"

    try:

        response = requests.get(url)

        data = response.json()

        # print(data)



        bids = data['bids']

        asks = data['asks']



        average_bid, volume_bids = weighted_average(bids)

        average_ask, volume_asks = weighted_average(asks)

        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("MEXC", "spot", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })
        # ===========================

        return average_bid, average_ask, volume_asks, volume_bids

    except Exception as e:

        print(f"Ошибка при получении стакана mexc Spot: {e}")
        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("MEXC", "spot", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })
        # ===========================
        return None, None, None, None



def get_order_book_mexc_futures(symbol):
    clean_symbol = symbol.replace("_", "")    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("MEXC", "futures", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================
    symbol = symbol.replace("_", "_")

    url = f"https://contract.mexc.com/api/v1/contract/depth/{symbol}?limit={LIMIT_ORDER_BOOK}"



    try:

        response = requests.get(url)

        data = response.json()['data']

        # print(data)



        bids = data['bids']

        asks = data['asks']



        average_bid, volume_bids = weighted_average(bids, True)

        average_ask, volume_asks = weighted_average(asks, True)

        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("MEXC", "futures", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })
        # ===========================

        return average_bid, average_ask, volume_asks, volume_bids

    except Exception as e:

        print(f"Ошибка при получении стакана mexc futures: {e}")
        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("MEXC", "futures", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })
        # ===========================
        return None, None, None, None



# ==================== Gate ====================



def get_order_book_gate_spot(symbol):
    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("Gate", "spot", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================
    symbol = symbol.replace("_", "_")

    endpoint = "/spot/order_book"

    params = {

        'currency_pair': symbol,

        'limit': LIMIT_ORDER_BOOK

    }



    try:

        data = make_request(endpoint, params)

        # print(data)



        bids = data['bids']

        asks = data['asks']



        average_bid, volume_bids = weighted_average(bids)

        average_ask, volume_asks = weighted_average(asks)

        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Gate", "spot", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })
        # ===========================

        return average_bid, average_ask, volume_asks, volume_bids

    except Exception as e:

        print(f"Ошибка при получении стакана gate Spot: {e}")
        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Gate", "spot", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })
        # ===========================
        return None, None, None, None



def get_order_book_gate_futures(symbol):
    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("Gate", "futures", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================
    symbol = symbol.replace("_", "_")

    endpoint = "/futures/usdt/order_book"

    params = {

        'contract': symbol,

        'limit': LIMIT_ORDER_BOOK

    }



    try:

        data = make_request(endpoint, params)

        # print(data)



        bids = data['bids']

        asks = data['asks']



        multiplier = get_contract_multiplier_gate(symbol)



        average_bid, volume_bids = weighted_average(bids, True)

        average_ask, volume_asks = weighted_average(asks, True)

        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Gate", "futures", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })
        # ===========================

        return average_bid, average_ask, volume_asks, volume_bids

    except Exception as e:

        print(f"Ошибка при получении стакана gate futures: {e}")
        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Gate", "futures", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })
        return None, None, None, None



# ==================== BingX ====================



def get_order_book_bingx_spot(symbol):
    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("Bingx", "spot", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================
    symbol = symbol.replace("_", "-")

    url = 'https://open-api.bingx.com/openApi/spot/v1/market/depth'

    params = {

        'symbol': symbol,

        'limit': LIMIT_ORDER_BOOK

    }

    try:

        response = requests.get(url, params=params)

        data = response.json()

        # print("\n---------------------------------------------------------------")

        # print(data)



        bids = data['data']['bids']

        asks = data['data']['asks']

        asks.reverse() # тут исправление потому что плохо работало



        average_bid, volume_bids = weighted_average(bids)

        average_ask, volume_asks = weighted_average(asks)



        # print(symbol)

        # print("----------")

        # print(f"average_bid = {average_bid}, volume_bids = {volume_bids}")

        # print(f"average_ask = {average_ask}, volume_asks = {volume_asks}")


        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Bingx", "spot", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })
        # ===========================

        return average_bid, average_ask, volume_asks, volume_bids

    except Exception as e:

        print(f"Ошибка при получении стакана bingx spot: {e}")

        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Bingx", "spot", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })
        # ===========================
        return None, None, None, None



def get_order_book_bingx_futures(symbol):
    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("Bingx", "futures", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================
    symbol = symbol.replace("_", "-")

    url = 'https://open-api.bingx.com/openApi/swap/v2/quote/depth'

    params = {

        'symbol': symbol,

        'limit': LIMIT_ORDER_BOOK

    }

    try:

        response = requests.get(url, params=params)

        data = response.json()

        # print(data)



        bids = data['data']['bids']

        asks = data['data']['asks']



        average_bid, volume_bids = weighted_average(bids)

        average_ask, volume_asks = weighted_average(asks)

        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Bingx", "futures", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })
        # ===========================

        return average_bid, average_ask, volume_asks, volume_bids

    except Exception as e:

        print(f"Ошибка при получении стакана bingx futures: {e}")
        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Bingx", "futures", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })
        return None, None, None, None





def get_order_book_bybit_spot(symbol="BTC_USDT"):
    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("Bybit", "spot", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================
    url = "https://api.bybit.com/v5/market/orderbook"

    params = {

        "category": "spot",

        "symbol": symbol.replace("_", ""),  # Bybit требует без "_",

        'limit': LIMIT_ORDER_BOOK

    }



    try:

        response = requests.get(url, params=params, timeout=10)

        data = response.json()

        # print(data)



        # print(data)

        # print(symbol)



        if data.get("retCode") != 0:

            print(f"Ошибка API Bybit Spot: {data.get('retMsg', 'Unknown error')}")

            # print(data)

            # print(symbol)

            return None, None, None, None



        # order_book = data["result"]["orderBook"]  # ПРАВИЛЬНО

        # bids = [[float(p["price"]), float(p["size"])] for p in order_book if p["side"] == "Buy"][:LIMIT_ORDER_BOOK]

        # asks = [[float(p["price"]), float(p["size"])] for p in order_book if p["side"] == "Sell"][:LIMIT_ORDER_BOOK]

        bids = [[float(p[0]), float(p[1])] for p in data["result"]["b"]]

        asks = [[float(p[0]), float(p[1])] for p in data["result"]["a"]]



        average_bid, volume_bids = weighted_average(bids)

        average_ask, volume_asks = weighted_average(asks)

        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Bybit", "spot", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })
        # ===========================

        return average_bid, average_ask, volume_asks, volume_bids



    except Exception as e:

        print(f"Ошибка при получении стакана Bybit Spot: {e}")
        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Bybit", "spot", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })
        # ===========================
        return None, None, None, None





def get_order_book_bybit_futures(symbol="BTC_USDT"):
    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("Bybit", "futures", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================
    url = "https://api.bybit.com/v5/market/orderbook"

    params = {

        "category": "linear",  # для USDT контрактов

        "symbol": symbol.replace("_", "")  # Bybit требует без "_"

    }



    try:

        response = requests.get(url, params=params)

        data = response.json()

        # print(data)





        if data.get("retCode") != 0:

            print(f"Ошибка API Bybit Futures: {data.get('retMsg', 'Unknown error')}")

            return None, None, None, None



        # order_book = data["result"]["orderBook"]

        # bids = [[float(p["price"]), float(p["size"])] for p in order_book if p["side"] == "Buy"][:LIMIT_ORDER_BOOK]

        # asks = [[float(p["price"]), float(p["size"])] for p in order_book if p["side"] == "Sell"][:LIMIT_ORDER_BOOK]

        bids = [[float(p[0]), float(p[1])] for p in data["result"]["b"]]

        asks = [[float(p[0]), float(p[1])] for p in data["result"]["a"]]



        average_bid, volume_bids = weighted_average(bids)

        average_ask, volume_asks = weighted_average(asks)

        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Bybit", "futures", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })
        # ===========================

        return average_bid, average_ask, volume_asks, volume_bids



    except Exception as e:

        print(f"Ошибка при получении стакана Bybit Futures: {e}")
        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Bybit", "futures", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })
        return None, None, None, None





# def get_order_book_bitget_spot(symbol="BTC_USDT"):
#     clean_symbol = symbol.replace("_", "")

#     # ====== ПРОВЕРКА В КЭШЕ ======
#     cached = cache_get("BitGet", "spot", clean_symbol)
#     if cached:
#         return (
#             cached["average_bid"],
#             cached["average_ask"],
#             cached["volume_asks"],
#             cached["volume_bids"],
#         )
#     # ==============================
#     url = "https://api.bitget.com/api/spot/v1/market/depth"

#     params = {

#         "symbol": symbol.replace("_", "") + "_SPBL",

#         "limit": LIMIT_ORDER_BOOK

#     }



#     try:

#         response = requests.get(url, params=params)

#         data = response.json()

#         # print(data)



#         if data.get("code") != "00000":

#             print(f"Ошибка API Bitget Spot: {data.get('msg', 'Unknown error')}")

#             return None, None, None, None



#         bids = [[float(p[0]), float(p[1])] for p in data["data"]["bids"]]

#         asks = [[float(p[0]), float(p[1])] for p in data["data"]["asks"]]



#         average_bid, volume_bids = weighted_average(bids)

#         average_ask, volume_asks = weighted_average(asks)

#         # ====== ЗАПИСЬ В КЭШ ======
#         cache_set("BitGet", "spot", clean_symbol, {
#             "average_bid": average_bid,
#             "average_ask": average_ask,
#             "volume_asks": volume_asks,
#             "volume_bids": volume_bids
#         })
#         # ===========================

#         return average_bid, average_ask, volume_asks, volume_bids



#     except Exception as e:

#         print(f"Ошибка при получении стакана Bitget Spot: {e}")
#         # ====== ЗАПИСЬ В КЭШ ======
#         cache_set("BitGet", "spot", clean_symbol, {
#             "average_bid": None,
#             "average_ask": None,
#             "volume_asks": None,
#             "volume_bids": None
#         })
#         # ===========================
#         return None, None, None, None

def get_order_book_bitget_spot(symbol="BTC_USDT"):

    clean_symbol = symbol.replace("_", "")
    
    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("BitGet", "spot", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================

    url = "https://api.bitget.com/api/v2/spot/market/orderbook"

    params = {
        "symbol": clean_symbol,
        "limit": LIMIT_ORDER_BOOK
    }

    try:

        response = requests.get(url, params=params)
        data = response.json()

        if data.get("code") != "00000":
            print(f"Ошибка API Bitget Spot: {data.get('msg')}")
            return None, None, None, None

        bids = [[float(p[0]), float(p[1])] for p in data["data"]["bids"]]
        asks = [[float(p[0]), float(p[1])] for p in data["data"]["asks"]]

        average_bid, volume_bids = weighted_average(bids)
        average_ask, volume_asks = weighted_average(asks)

        # ====== КЭШ ======
        cache_set("BitGet", "spot", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })

        return average_bid, average_ask, volume_asks, volume_bids

    except Exception as e:

        print(f"Ошибка Bitget Spot OrderBook: {e}")

        cache_set("BitGet", "spot", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })

        return None, None, None, None




# def get_order_book_bitget_futures(symbol="BTC_USDT"):
#     clean_symbol = symbol.replace("_", "")

#     # ====== ПРОВЕРКА В КЭШЕ ======
#     cached = cache_get("BitGet", "futures", clean_symbol)
#     if cached:
#         return (
#             cached["average_bid"],
#             cached["average_ask"],
#             cached["volume_asks"],
#             cached["volume_bids"],
#         )
#     # ==============================
#     url = "https://api.bitget.com/api/mix/v1/market/depth"

#     params = {

#         "symbol": symbol.replace("_", "") + "_UMCBL",

#         "productType": "usdt",

#         "limit": LIMIT_ORDER_BOOK

#     }



#     try:

#         response = requests.get(url, params=params)

#         data = response.json()

#         # print(data)



#         if data.get("code") != "00000":

#             print(f"Ошибка API Bitget Futures: {data.get('msg', 'Unknown error')}")

#             return None, None, None, None



#         bids = [[float(p[0]), float(p[1])] for p in data["data"]["bids"]]

#         asks = [[float(p[0]), float(p[1])] for p in data["data"]["asks"]]



#         average_bid, volume_bids = weighted_average(bids)

#         average_ask, volume_asks = weighted_average(asks)


#         # ====== ЗАПИСЬ В КЭШ ======
#         cache_set("BitGet", "futures", clean_symbol, {
#             "average_bid": average_bid,
#             "average_ask": average_ask,
#             "volume_asks": volume_asks,
#             "volume_bids": volume_bids
#         })
#         # ===========================
#         return average_bid, average_ask, volume_asks, volume_bids



#     except Exception as e:

#         print(f"Ошибка при получении стакана Bitget Futures: {e}")
#         # ====== ЗАПИСЬ В КЭШ ======
#         cache_set("BitGet", "futures", clean_symbol, {
#             "average_bid": None,
#             "average_ask": None,
#             "volume_asks": None,
#             "volume_bids": None
#         })
#         return None, None, None, None
def get_order_book_bitget_futures(symbol="BTC_USDT"):

    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("BitGet", "futures", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================

    url = "https://api.bitget.com/api/v2/mix/market/orderbook"

    params = {
        "symbol": clean_symbol,
        "productType": "USDT-FUTURES",
        "limit": LIMIT_ORDER_BOOK
    }

    try:

        response = requests.get(url, params=params)
        data = response.json()

        if data.get("code") != "00000":
            print(f"Ошибка API Bitget Futures: {data.get('msg')}")
            return None, None, None, None

        bids = [[float(p[0]), float(p[1])] for p in data["data"]["bids"]]
        asks = [[float(p[0]), float(p[1])] for p in data["data"]["asks"]]

        average_bid, volume_bids = weighted_average(bids)
        average_ask, volume_asks = weighted_average(asks)

        cache_set("BitGet", "futures", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })

        return average_bid, average_ask, volume_asks, volume_bids

    except Exception as e:

        print(f"Ошибка Bitget Futures OrderBook: {e}")

        cache_set("BitGet", "futures", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })

        return None, None, None, None


# Binance Spot Order Book

def get_order_book_binance_spot(symbol="BTC_USDT"):
    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("Binance", "spot", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================
    # Binance использует формат "BTCUSDT"

    binance_symbol = symbol.replace("_", "")

    url = "https://api.binance.com/api/v3/depth"

    params = {

        "symbol": binance_symbol,

        "limit": LIMIT_ORDER_BOOK

    }



    try:

        response = requests.get(url, params=params)

        response.raise_for_status()

        data = response.json()



        # bids/asks: [[price, size], ...]

        bids = [[float(p[0]), float(p[1])] for p in data['bids']]

        asks = [[float(p[0]), float(p[1])] for p in data['asks']]



        # Для спота weighted_average без флага True

        average_bid, volume_bids = weighted_average(bids)

        average_ask, volume_asks = weighted_average(asks)


        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Binance", "spot", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })
        # ===========================
        return average_bid, average_ask, volume_asks, volume_bids



    except Exception as e:

        print(f"Ошибка при получении стакана Binance Spot: {e}")
        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Binance", "spot", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })
        # ===========================
        return None, None, None, None



# Binance Futures (USDT-M) Order Book - НЕЗАВИСИМЫЙ РАСЧЕТ

def get_order_book_binance_futures(symbol="BTC_USDT"):

    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("Binance", "futures", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================

    # 1. Подготовка

    binance_symbol = symbol.replace("_", "")

    url = "https://fapi.binance.com/fapi/v1/depth"

    params = {

        "symbol": binance_symbol,

        "limit": LIMIT_ORDER_BOOK

    }



    try:

        response = requests.get(url, params=params)

        response.raise_for_status()

        data = response.json()

        # print(data) # Убираем print(data) для чистоты вывода



        # 2. Преобразование данных

        # bids/asks: [[price, quantity], ...]

        bids = [[float(p[0]), float(p[1])] for p in data['bids']]

        asks = [[float(p[0]), float(p[1])] for p in data['asks']]



        # 3. Расчет для BIDS (Покупатели)

        total_value_bids = 0.0

        total_quantity_bids = 0.0



        for price, quantity in bids:

            total_quantity_bids += quantity

            total_value_bids += price * quantity # Стоимость = Цена * Количество

       

        # Средневзвешенная цена (VWAP) = Общая_Стоимость / Общее_Количество

        average_bid = total_value_bids / total_quantity_bids if total_quantity_bids > 0 else 0.0

        # Для фьючерсов объем в USD/USDT (Стоимость)

        volume_bids = total_value_bids



        # 4. Расчет для ASKS (Продавцы)

        total_value_asks = 0.0

        total_quantity_asks = 0.0



        for price, quantity in asks:

            total_quantity_asks += quantity

            total_value_asks += price * quantity

       

        average_ask = total_value_asks / total_quantity_asks if total_quantity_asks > 0 else 0.0

        # Для фьючерсов объем в USD/USDT (Стоимость)

        volume_asks = total_value_asks

        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Binance", "futures", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })
        # ===========================

        # 5. Возврат результата

        # average_bid, average_ask, volume_asks, volume_bids

        return average_bid, average_ask, volume_asks, volume_bids



    except Exception as e:

        # print(f"Ошибка при получении стакана Binance Futures: {e}") # Оставляем для отладки
        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Binance", "futures", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })
        return 0, 0, 0, 0





def get_order_book_hyperliquid_futures(symbol="BTC_USDT"):
    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("Hyperliquid", "futures", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================
    coin = symbol.replace("_USDT", "")

    url = "https://api.hyperliquid.xyz/info"

    payload = {"type": "l2Book", "coin": coin}

    headers = {"Content-Type": "application/json"}



    try:

        response = requests.post(url, headers=headers, json=payload)

        response.raise_for_status()

        data = response.json()



        if "levels" not in data or len(data["levels"]) < 2:

            print("Некорректный ответ:", data)

            return 0, 0, 0, 0



        bids_raw = data["levels"][0][:LIMIT_ORDER_BOOK]

        asks_raw = data["levels"][1][:LIMIT_ORDER_BOOK]



        # Преобразуем в [price, quantity]

        bids = [[float(order["px"]), float(order["sz"])] for order in bids_raw]

        asks = [[float(order["px"]), float(order["sz"])] for order in asks_raw]



        def calc_vwap(orders):

            total_value = sum(p * q for p, q in orders)

            total_qty = sum(q for _, q in orders)

            avg_price = total_value / total_qty if total_qty > 0 else 0.0

            return avg_price, total_value



        average_bid, volume_bids = calc_vwap(bids)

        average_ask, volume_asks = calc_vwap(asks)

        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Hyperliquid", "futures", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })
        # ===========================

        return average_bid, average_ask, volume_asks, volume_bids



    except Exception as e:

        print(f"Ошибка при получении стакана Hyperliquid: {e}")
        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("Hyperliquid", "futures", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })
        return 0, 0, 0, 0



# Список разделителей для извлечения базовой и котируемой валюты

SEPARATORS = ["_", "-", "/"]



def get_order_book_htx(symbol="BTC_USDT"):
    clean_symbol = symbol.replace("_", "")
    htx_symbol = symbol.replace("_", "").lower()

    # Проверяем, существует ли монета
    if not htx_symbol_exists(htx_symbol):
        print(f"❌ HTX не имеет спотовой пары {htx_symbol}")
        return 0, 0, 0, 0

    # Проверяем кэш стаканов
    cached = cache_get("HTX", "spot", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )

    # Получаем стакан
    url = f"https://api.huobi.pro/market/depth?symbol={htx_symbol}&type=step0"

    try:
        js = requests.get(url, timeout=10).json()

        tick = js.get("tick")
        if not tick:
            print(f"❌ HTX не вернула tick: {js}")
            return 0, 0, 0, 0

        bids = [[float(p[0]), float(p[1])] for p in tick.get("bids", [])]
        asks = [[float(p[0]), float(p[1])] for p in tick.get("asks", [])]

        def weighted(entries):
            total_volume = sum(price * qty for price, qty in entries)
            total_qty = sum(qty for _, qty in entries)
            return (total_volume / total_qty if total_qty else 0, total_volume)

        average_bid, volume_bids = weighted(bids)
        average_ask, volume_asks = weighted(asks)

        cache_set("HTX", "spot", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })

        return average_bid, average_ask, volume_asks, volume_bids

    except Exception as e:
        print(f"❌ Ошибка получения HTX orderbook: {e}")
        return 0, 0, 0, 0






# def get_xt_order_book_futures(symbol="BTC_USDT", limit=50):

#     """

#     Получает биржевой стакан для фьючерсной пары XT.com и рассчитывает VWAP.

   

#     :param symbol: Символ в формате 'КОИН_USDT' (например, 'BTC_USDT').

#     :param limit: Глубина стакана (количество ордеров).

#     :return: (avg_bid, avg_ask, volume_asks, volume_bids) или (0, 0, 0, 0)

#     """

#     # 1. Приведение символа к формату CCXT.

#     # Для фьючерсов CCXT часто требует символ в виде 'BTC/USDT' с указанием 'defaultType'
#     clean_symbol = symbol.replace("_", "")

#     # ====== ПРОВЕРКА В КЭШЕ ======
#     cached = cache_get("XT", "futures", clean_symbol)
#     if cached:
#         return (
#             cached["average_bid"],
#             cached["average_ask"],
#             cached["volume_asks"],
#             cached["volume_bids"],
#         )
#     # ==============================
#     ccxt_symbol = symbol.replace('_', '/')

   
#     # Проверяем доступность торговой пары
#     if not xt_pair_exists_futures(ccxt_symbol):
#         print(f"❌ XT Futures не имеет пары {ccxt_symbol}")
#         return 0, 0, 0, 0
#     try:

#         exchange = ccxt.xt()

#         exchange.options['defaultType'] = 'future' # Настройка для фьючерсов



#         # 2. Получение стакана

#         order_book = exchange.fetch_order_book(ccxt_symbol, limit=limit)

       

#         bids = order_book.get('bids', [])

#         asks = order_book.get('asks', [])



#         # 3. Функция для расчета VWAP и общего объема

#         def calculate_vwap_and_volume(orders):

#             total_value = sum(price * qty for price, qty in orders)

#             total_qty = sum(qty for _, qty in orders)

           

#             avg_price = (total_value / total_qty) if total_qty > 0 else 0.0

#             return avg_price, total_value



#         average_bid, volume_bids = calculate_vwap_and_volume(bids)

#         average_ask, volume_asks = calculate_vwap_and_volume(asks)

       

#         # ====== ЗАПИСЬ В КЭШ ======
#         cache_set("XT", "futures", clean_symbol, {
#             "average_bid": average_bid,
#             "average_ask": average_ask,
#             "volume_asks": volume_asks,
#             "volume_bids": volume_bids
#         })
#         # ===========================
#         # 4. Возврат в требуемом формате

#         return average_bid, average_ask, volume_asks, volume_bids



#     except Exception as e:

#         print(f"❌ Ошибка при получении фьючерсного стакана XT.com для {symbol}: {e}")
#         # ====== ЗАПИСЬ В КЭШ ======
#         cache_set("XT", "futures", clean_symbol, {
#             "average_bid": None,
#             "average_ask": None,
#             "volume_asks": None,
#             "volume_bids": None
#         })
#         return 0, 0, 0, 0

   



def get_xt_order_book_spot(symbol="BTC_USDT", limit=50):

    """

    Получает биржевой стакан для спотовой пары XT.com и рассчитывает VWAP (средневзвешенную цену).

   

    :param symbol: Символ в формате 'КОИН_USDT' (например, 'BTC_USDT').

    :param limit: Глубина стакана (количество ордеров).

    :return: (avg_bid, avg_ask, volume_asks, volume_bids) или (0, 0, 0, 0)

    """

    
    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("XT", "spot", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================
    # 1. Приведение символа к формату CCXT

    ccxt_symbol = symbol.replace('_', '/')

   

    try:

        exchange = ccxt.xt()

        exchange.options['defaultType'] = 'spot'



        # 2. Получение стакана

        order_book = exchange.fetch_order_book(ccxt_symbol, limit=limit)

       

        bids = order_book.get('bids', [])

        asks = order_book.get('asks', [])



        # 3. Функция для расчета VWAP и общего объема

        def calculate_vwap_and_volume(orders):

            # orders - список вида [[price, amount], [price, amount], ...]

            total_value = sum(price * qty for price, qty in orders)

            total_qty = sum(qty for _, qty in orders)

           

            avg_price = (total_value / total_qty) if total_qty > 0 else 0.0

            return avg_price, total_value # VWAP, Объем (в валюте котирования)



        average_bid, volume_bids = calculate_vwap_and_volume(bids)

        average_ask, volume_asks = calculate_vwap_and_volume(asks)

               # ====== ЗАПИСЬ В КЭШ ======
        cache_set("XT", "spot", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })
        # ===========================

        # 4. Возврат в требуемом формате

        return average_bid, average_ask, volume_asks, volume_bids # Обратите внимание на порядок volume



    except Exception as e:

        print(f"❌ Ошибка при получении спотового стакана XT.com для {symbol}: {e}")
        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("XT", "spot", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })
        # ===========================
        return 0, 0, 0, 0

   



def calculate_vwap_and_volume_okx(orders):

    """

    Вспомогательная функция для расчета VWAP и общего объема.

    Исправлено для обработки ордеров CCXT, которые могут содержать > 2 элементов

    (например, [price, amount, count] для OKX).

   

    :param orders: Список вида [[price, amount, ...], ...]

    :return: (VWAP, Общий объем в валюте котирования)

    """

    # Мы берем только price (p) и amount (q)

    total_value = sum(p * q for p, q, *rest in orders)

    total_qty = sum(q for p, q, *rest in orders)

   

    avg_price = (total_value / total_qty) if total_qty > 0 else 0.0

    # Возвращаем VWAP и Объем (в валюте котирования)

    return avg_price, total_value







def get_okx_order_book_spot(symbol="BTC_USDT", limit=50):

    """

    Получает биржевой стакан для спотовой пары OKX и рассчитывает VWAP.

    :return: (avg_bid, avg_ask, volume_asks, volume_bids)

    """
    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("OKX", "spot", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================
    ccxt_symbol = symbol.replace('_', '/')

    try:

        exchange = ccxt.okx()

        exchange.options['defaultType'] = 'spot'



        order_book = exchange.fetch_order_book(ccxt_symbol, limit=limit)

       

        bids = order_book.get('bids', [])

        asks = order_book.get('asks', [])



        average_bid, volume_bids = calculate_vwap_and_volume_okx(bids)

        average_ask, volume_asks = calculate_vwap_and_volume_okx(asks)

               # ====== ЗАПИСЬ В КЭШ ======
        cache_set("OKX", "spot", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })
        # ===========================

        return average_bid, average_ask, volume_asks, volume_bids



    except Exception as e:

        print(f"❌ Ошибка при получении спотового стакана OKX для {symbol}: {e}")
        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("OKX", "spot", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })
        # ===========================
        return 0, 0, 0, 0

   

def get_okx_order_book_futures(symbol="BTC_USDT", limit=50):

    """

    Получает биржевой стакан для бессрочных фьючерсов (Swap) OKX и рассчитывает VWAP.

    :return: (avg_bid, avg_ask, volume_asks, volume_bids)

    """
    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    cached = cache_get("OKX", "futures", clean_symbol)
    if cached:
        return (
            cached["average_bid"],
            cached["average_ask"],
            cached["volume_asks"],
            cached["volume_bids"],
        )
    # ==============================
    ccxt_symbol = symbol.replace('_', '/')

    try:

        exchange = ccxt.okx()

        exchange.options['defaultType'] = 'swap' # Настройка для бессрочных фьючерсов



        order_book = exchange.fetch_order_book(ccxt_symbol, limit=limit)

       

        bids = order_book.get('bids', [])

        asks = order_book.get('asks', [])



        average_bid, volume_bids = calculate_vwap_and_volume_okx(bids)

        average_ask, volume_asks = calculate_vwap_and_volume_okx(asks)

               # ====== ЗАПИСЬ В КЭШ ======
        cache_set("OKX", "futures", clean_symbol, {
            "average_bid": average_bid,
            "average_ask": average_ask,
            "volume_asks": volume_asks,
            "volume_bids": volume_bids
        })
        # ===========================


        return average_bid, average_ask, volume_asks, volume_bids



    except Exception as e:

        print(f"❌ Ошибка при получении фьючерсного стакана OKX для {symbol}: {e}")
        # ====== ЗАПИСЬ В КЭШ ======
        cache_set("OKX", "futures", clean_symbol, {
            "average_bid": None,
            "average_ask": None,
            "volume_asks": None,
            "volume_bids": None
        })
        return 0, 0, 0, 0


def calculate_vwap_and_volume_coinex(orders):
    """Рассчитывает средневзвешенную цену и объем."""
    if not orders:
        return 0, 0
    total_volume = sum(order[1] for order in orders)
    if total_volume == 0:
        return 0, 0
    weighted_sum = sum(order[0] * order[1] for order in orders)
    return weighted_sum / total_volume, total_volume

def get_coinex_order_book_spot(symbol="BTC_USDT", limit=50):
    """Получает стакан для спота CoinEx и рассчитывает VWAP."""
    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    try:
        cached = cache_get("COINEX", "spot", clean_symbol)
        if cached:
            return (
                cached["average_bid"],
                cached["average_ask"],
                cached["volume_asks"],
                cached["volume_bids"],
            )
    except Exception:
        pass # Защита от ошибки 'COINEX' в кэше
    # ==============================

    # CoinEx в CCXT использует формат BTC/USDT
    ccxt_symbol = symbol.replace('_', '/')

    try:
        exchange = ccxt.coinex()
        
        # print("start order_book")
        order_book = exchange.fetch_order_book(ccxt_symbol, limit=limit)
        # print("end order_book")

        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])
        
        # print(f"bids = {bids}")
        # print(f"asks = {asks}")

        average_bid, volume_bids = calculate_vwap_and_volume_coinex(bids)
        average_ask, volume_asks = calculate_vwap_and_volume_coinex(asks)

        # ====== ЗАПИСЬ В КЭШ ======
        try:
            cache_set("COINEX", "spot", clean_symbol, {
                "average_bid": average_bid,
                "average_ask": average_ask,
                "volume_asks": volume_asks,
                "volume_bids": volume_bids
            })
        except Exception:
            pass
        # ===========================

        return average_bid, average_ask, volume_asks, volume_bids

    except Exception as e:
        print(f"❌ Ошибка при получении спотового стакана CoinEx для {symbol}: {e}")
        try:
            cache_set("COINEX", "spot", clean_symbol, {
                "average_bid": 0, "average_ask": 0, "volume_asks": 0, "volume_bids": 0
            })
        except Exception:
            pass
        return 0, 0, 0, 0


def get_coinex_order_book_futures(symbol="BTC_USDT", limit=50):
    """Получает стакан для бессрочных фьючерсов CoinEx и рассчитывает VWAP."""
    clean_symbol = symbol.replace("_", "")

    # ====== ПРОВЕРКА В КЭШЕ ======
    try:
        cached = cache_get("COINEX", "futures", clean_symbol)
        if cached:
            return (
                cached["average_bid"],
                cached["average_ask"],
                cached["volume_asks"],
                cached["volume_bids"],
            )
    except Exception:
        pass
    # ==============================

    ccxt_symbol = symbol.replace('_', '/')

    try:
        # Указываем, что работаем с рынком свопов (фьючерсов)
        exchange = ccxt.coinex({
            'options': {'defaultType': 'swap'}
        })
        
        print("start order_book")
        order_book = exchange.fetch_order_book(ccxt_symbol, limit=limit)
        print("end order_book")

        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])
        
        print(f"bids = {bids}")
        print(f"asks = {asks}")

        average_bid, volume_bids = calculate_vwap_and_volume_coinex(bids)
        average_ask, volume_asks = calculate_vwap_and_volume_coinex(asks)

        # ====== ЗАПИСЬ В КЭШ ======
        try:
            cache_set("COINEX", "futures", clean_symbol, {
                "average_bid": average_bid,
                "average_ask": average_ask,
                "volume_asks": volume_asks,
                "volume_bids": volume_bids
            })
        except Exception:
            pass
        # ===========================

        return average_bid, average_ask, volume_asks, volume_bids

    except Exception as e:
        print(f"❌ Ошибка при получении фьючерсного стакана CoinEx для {symbol}: {e}")
        try:
            cache_set("COINEX", "futures", clean_symbol, {
                "average_bid": 0, "average_ask": 0, "volume_asks": 0, "volume_bids": 0
            })
        except Exception:
            pass
        return 0, 0, 0, 0


# ==================== Phemex / Aster ====================

def _book_result(exchange, market_type, clean_symbol, bids, asks):
    """Считает средние цены по стакану (как для остальных бирж) и кладёт в кэш."""
    average_bid, volume_bids = weighted_average(bids)
    average_ask, volume_asks = weighted_average(asks)
    cache_set(exchange, market_type, clean_symbol, {
        "average_bid": average_bid,
        "average_ask": average_ask,
        "volume_asks": volume_asks,
        "volume_bids": volume_bids,
    })
    return average_bid, average_ask, volume_asks, volume_bids


def _book_fail(exchange, market_type, clean_symbol):
    cache_set(exchange, market_type, clean_symbol, {
        "average_bid": None, "average_ask": None, "volume_asks": None, "volume_bids": None
    })
    return None, None, None, None


def _cached_book(exchange, market_type, clean_symbol):
    cached = cache_get(exchange, market_type, clean_symbol)
    if cached:
        return (cached["average_bid"], cached["average_ask"],
                cached["volume_asks"], cached["volume_bids"])
    return None


def get_order_book_phemex_futures(symbol="BTC_USDT"):
    from getData import PHEMEX_FUT_SYMBOLS
    clean_symbol = symbol.replace("_", "")
    cached = _cached_book("Phemex", "futures", clean_symbol)
    if cached:
        return cached

    raw_symbol, mult = PHEMEX_FUT_SYMBOLS.get(symbol, (clean_symbol, 1))
    try:
        response = requests.get("https://api.phemex.com/md/v2/orderbook",
                                params={"symbol": raw_symbol}, timeout=10)
        data = response.json()
        result = data.get("result") or {}
        book = result.get("orderbook_p") or result.get("book") or {}
        # цены и объёмы — строки в реальных единицах; учитываем множитель контракта
        bids = [[float(p[0]) / mult, float(p[1]) * mult] for p in book.get("bids", [])]
        asks = [[float(p[0]) / mult, float(p[1]) * mult] for p in book.get("asks", [])]
        if not bids or not asks:
            return _book_fail("Phemex", "futures", clean_symbol)
        return _book_result("Phemex", "futures", clean_symbol, bids, asks)
    except Exception as e:
        print(f"Ошибка при получении стакана Phemex futures: {e}")
        return _book_fail("Phemex", "futures", clean_symbol)


def get_order_book_phemex_spot(symbol="BTC_USDT"):
    from getData import _get_phemex_ccxt
    clean_symbol = symbol.replace("_", "")
    cached = _cached_book("Phemex", "spot", clean_symbol)
    if cached:
        return cached
    try:
        ex = _get_phemex_ccxt()
        ob = ex.fetch_order_book(symbol.replace("_", "/"), limit=30)
        bids = [[float(p[0]), float(p[1])] for p in ob.get("bids", [])]
        asks = [[float(p[0]), float(p[1])] for p in ob.get("asks", [])]
        if not bids or not asks:
            return _book_fail("Phemex", "spot", clean_symbol)
        return _book_result("Phemex", "spot", clean_symbol, bids, asks)
    except Exception as e:
        print(f"Ошибка при получении стакана Phemex spot: {e}")
        return _book_fail("Phemex", "spot", clean_symbol)


def get_order_book_aster_futures(symbol="BTC_USDT"):
    from getData import ASTER_FUT_SYMBOLS
    clean_symbol = symbol.replace("_", "")
    cached = _cached_book("Aster", "futures", clean_symbol)
    if cached:
        return cached

    raw_symbol, mult = ASTER_FUT_SYMBOLS.get(symbol, (clean_symbol, 1))
    try:
        response = requests.get("https://fapi.asterdex.com/fapi/v1/depth",
                                params={"symbol": raw_symbol, "limit": LIMIT_ORDER_BOOK}, timeout=10)
        data = response.json()
        bids = [[float(p[0]) / mult, float(p[1]) * mult] for p in data.get("bids", [])]
        asks = [[float(p[0]) / mult, float(p[1]) * mult] for p in data.get("asks", [])]
        if not bids or not asks:
            return _book_fail("Aster", "futures", clean_symbol)
        return _book_result("Aster", "futures", clean_symbol, bids, asks)
    except Exception as e:
        print(f"Ошибка при получении стакана Aster futures: {e}")
        return _book_fail("Aster", "futures", clean_symbol)


def get_order_book_aster_spot(symbol="BTC_USDT"):
    clean_symbol = symbol.replace("_", "")
    cached = _cached_book("Aster", "spot", clean_symbol)
    if cached:
        return cached
    try:
        response = requests.get("https://sapi.asterdex.com/api/v1/depth",
                                params={"symbol": clean_symbol, "limit": LIMIT_ORDER_BOOK}, timeout=10)
        data = response.json()
        if not isinstance(data, dict):
            print(f"Aster spot {clean_symbol}: неожиданный ответ стакана: {str(data)[:200]}")
            return _book_fail("Aster", "spot", clean_symbol)
        bids = [[float(p[0]), float(p[1])] for p in data.get("bids", [])]
        asks = [[float(p[0]), float(p[1])] for p in data.get("asks", [])]
        if not bids or not asks:
            return _book_fail("Aster", "spot", clean_symbol)
        return _book_result("Aster", "spot", clean_symbol, bids, asks)
    except Exception as e:
        print(f"Ошибка при получении стакана Aster spot: {e}")
        return _book_fail("Aster", "spot", clean_symbol)
