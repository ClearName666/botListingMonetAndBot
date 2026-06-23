# Хранилище последних отправленных сделок
import time

import dataApp
from cup import get_coinex_order_book_futures, get_coinex_order_book_spot, get_okx_order_book_futures, get_okx_order_book_spot, get_order_book_binance_futures, get_order_book_binance_spot, get_order_book_htx, get_order_book_hyperliquid_futures, get_order_book_mexc_spot, get_order_book_gate_spot, get_order_book_bingx_spot, \
    get_order_book_bybit_spot, get_order_book_bitget_spot, get_order_book_mexc_futures, get_order_book_gate_futures, \
    get_order_book_bingx_futures, get_order_book_bybit_futures, get_order_book_bitget_futures,  get_xt_order_book_spot # get_xt_order_book_futures,


import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
executor = ThreadPoolExecutor()


last_opportunities = {}

# Порог обновления — сделка считается "новой", если прибыль изменилась на более чем X%
REPEAT_THRESHOLD_PERCENT = 1.0



def should_send(deal):
    key = f"{deal['type']}::{deal['symbol']}"
    current_profit = deal['profit_percent']

    if key not in last_opportunities:
        last_opportunities[key] = current_profit
        return True

    prev_profit = last_opportunities[key]
    if abs(current_profit - prev_profit) >= REPEAT_THRESHOLD_PERCENT:
        last_opportunities[key] = current_profit
        return True

    return False



def scan_arbitrage_opportunities_test(
    mexc_spot, mexc_futures,
    gate_spot, gate_futures,
    bingx_spot, bingx_futures,
    bybit_spot, bybit_futures,
    bitget_spot, bitget_futures,
    binance_spot, binance_fut,
    hyperliquid_fut,
    htx_spot, htx_fut,
    xt_spot, # xt_fut,
    # okx_spot, okx_fut,
    coinex_spot, coinex_fut,
    min_diff_percent=1.0,
    max_diff_percent=100.0,
    min_usd_amount=100
):
    opportunities = []
    all_symbols = set(mexc_spot.keys()) | set(mexc_futures.keys()) | set(gate_spot.keys()) | set(gate_futures.keys()) \
                  | set(bingx_spot.keys()) | set(bingx_futures.keys()) | set(bybit_spot.keys()) | set(bybit_futures.keys()) \
                  | set(bitget_spot.keys()) | set(bitget_futures.keys()) | set(binance_spot.keys()) | set(binance_fut.keys()) \
                  | set(hyperliquid_fut.keys()) \
                  | set(htx_spot.keys()) | set(htx_fut.keys()) | set(xt_spot.keys())  | set(coinex_spot.keys()) | set(coinex_fut.keys()) # | set(xt_fut.keys()) | set(okx_spot.keys()) | set(okx_fut.keys())


    exchanges = {
        'MEXC': {'spot': mexc_spot, 'futures': mexc_futures},
        'Gate': {'spot': gate_spot, 'futures': gate_futures},
        'Bingx': {'spot': bingx_spot, 'futures': bingx_futures},
        'Bybit': {'spot': bybit_spot, 'futures': bybit_futures},
        'BitGet': {'spot': bitget_spot, 'futures': bitget_futures},
        'Binance': {'spot': binance_spot, 'futures': binance_fut},
        'Hyperliquid': {'futures': hyperliquid_fut},
        "XT": {'spot': xt_spot}, # , 'futures': xt_fut
        # 'OKX': {'spot': okx_spot, 'futures': okx_fut},
        'HTX': {'spot': htx_spot, 'futures': htx_fut},
        'Coinex': {'spot': coinex_spot, 'futures': coinex_fut},
    }

    def link(coin, type_, exchange):
        coin = coin.replace("_", "").lower()
        coin_dash = f"{coin}-usdt"
        if exchange == "MEXC":
            return f"https://www.mexc.com/exchange/{coin}" if type_ == "spot" else f"https://www.mexc.com/futures/contract/{coin}_USDT"
        elif exchange == "Gate":
            return f"https://www.gate.io/trade/{coin}_USDT" if type_ == "spot" else f"https://www.gate.io/futures_trade/USDT/{coin}_USDT"
        elif exchange == "Bingx":
            return f"https://bingx.com/en-us/spot/{coin}_USDT/" if type_ == "spot" else f"https://bingx.com/en-us/futures/{coin}_USDT/"
        elif exchange == "Bybit":
            return f"https://www.bybit.com/trade/spot/{coin.upper()}USDT" if type_ == "spot" else f"https://www.bybit.com/trade/usdt/{coin.upper()}USDT"
        elif exchange == "BitGet":
            return f"https://www.bitget.com/en/spot/{coin.upper()}USDT" if type_ == "spot" else f"https://www.bitget.com/en/futures/usdt/{coin.upper()}USDT"
        elif exchange == "Binance":
            return f"https://www.binance.com/en/trade/{coin.upper()}_USDT" if type_ == "spot" else f"https://www.binance.com/en/futures/{coin.upper()}USDT"
        elif exchange == "Hyperliquid":
            return f"https://www.hyperliquid.xyz/trade/{coin.upper()}-USDT" if type_ == "spot" else f"https://www.hyperliquid.xyz/futures/{coin.upper()}-USDT"
        elif exchange == "HTX":
            return f"https://www.htx.com/trade/{coin}-USDT" if type_ == "spot" else f"https://www.htx.com/futures/{coin}-USDT"
        elif exchange == "XT":
            return f"https://www.xt.com/trade/{coin.lower()}_usdt" if type_ == "spot" else f"https://www.xt.com/contract/{coin.lower()}_usdt"
        elif exchange == "OKX":
            return f"https://www.okx.com/trade-spot/{coin.lower()}_usdt" if type_ == "spot" else f"https://www.okx.com/trade-swap/{coin.lower()}_usdt"
        elif exchange == "Coinex":
            return f"https://www.coinex.com/exchange/{coin_dash}" if type_ == "spot" else f"https://www.coinex.com/futures/linear/{coin_dash}"

    def is_valid_diff(diff):
        return min_diff_percent <= diff <= max_diff_percent

    def is_reasonable_price(a, b):
        return 0.33 <= a / b <= 3

    # Предварительный проход без тяжелых запросов
    initial_candidates = []
    for symbol in all_symbols:
        for buy_exchange, buy_data in exchanges.items():
            for buy_type, buy_dict in buy_data.items():
                if symbol not in buy_dict:
                    continue
                buy_price = buy_dict[symbol]["price"] if isinstance(buy_dict[symbol], dict) else buy_dict[symbol]

                for sell_exchange, sell_data in exchanges.items():
                    for sell_type, sell_dict in sell_data.items():
                        if buy_exchange == sell_exchange and buy_type == sell_type:
                            continue
                        if buy_type == "spot" and sell_type == "spot":
                            continue
                        # if sell_type == "spot":
                        #     continue
                        if symbol not in sell_dict:
                            continue
                        # if buy_exchange == sell_exchange:
                        #     print(f"buy_exchange = {buy_exchange} sell_exchange = {sell_exchange}\n"
                        #           f"sell_dict[symbol][price] = {sell_dict[symbol]["price"]} buy_price = {buy_price}\n"
                        #           f"diff = (sell_price - buy_price) / buy_price * 100 = {(sell_dict[symbol]["price"] - buy_price) / buy_price * 100}")

                        sell_price = sell_dict[symbol]["price"] if isinstance(sell_dict[symbol], dict) else sell_dict[symbol]

                        if not is_reasonable_price(sell_price, buy_price):
                            continue

                        diff = (sell_price - buy_price) / buy_price * 100
                        if not is_valid_diff(diff):
                            continue

                        initial_candidates.append((symbol, buy_exchange, buy_type, sell_exchange, sell_type))


    # Параллельно собираем стаканы
    def fetch_orderbook(symbol, exchange, type_):
        if type_ == "spot":
            return getBayAndPriceSpot(symbol, exchange)
        else:
            return getBayAndPriceFutures(symbol, exchange)

    with ThreadPoolExecutor(max_workers=16) as executor:
        future_to_pair = {}
        for symbol, buy_exchange, buy_type, sell_exchange, sell_type in initial_candidates:
            future_to_pair[executor.submit(fetch_orderbook, symbol, buy_exchange, buy_type)] = ('buy', symbol, buy_exchange, buy_type)
            future_to_pair[executor.submit(fetch_orderbook, symbol, sell_exchange, sell_type)] = ('sell', symbol, sell_exchange, sell_type)

        orderbook_results = {}
        for future in as_completed(future_to_pair):
            side, symbol, exchange, type_ = future_to_pair[future]
            try:
                result = future.result()
                orderbook_results[(side, symbol, exchange, type_)] = result
            except Exception as e:
                orderbook_results[(side, symbol, exchange, type_)] = None

    # Второй проход — считаем actual_diff
    for symbol, buy_exchange, buy_type, sell_exchange, sell_type in initial_candidates:

        # изменения для нормальной работы одинаковых бирж
        buy_data = orderbook_results.get(('buy', symbol, buy_exchange, buy_type))
        sell_data = orderbook_results.get(('sell', symbol, sell_exchange, sell_type))

        if not buy_data or not sell_data:
            # if buy_exchange == sell_exchange:
            #     print(f"Отлет по причине того что одинаковые биржи (if not buy_data or not sell_data:)"
            #           f"buy_data = {buy_data} sell_data = {sell_data}")
            continue

        buy_bid, buy_ask, buy_vol_ask, buy_vol_bid = buy_data
        sell_bid, sell_ask, sell_vol_ask, sell_vol_bid = sell_data

        if None in (buy_bid, buy_ask, buy_vol_ask, buy_vol_bid, sell_bid, sell_ask, sell_vol_ask, sell_vol_bid):
            # if buy_exchange == sell_exchange:
            #     print(f"Отлет по причине того что одинаковые биржи ( if None in (buy_bid, buy_ask)"
            #           f"buy_data = {buy_data} sell_data = {sell_data}")
            continue
        if buy_ask == 0 or sell_bid == 0:
            # if buy_exchange == sell_exchange:
            #     print(f"Отлет по причине того что одинаковые биржи (if buy_ask == 0 or sell_bid == 0:)"
            #           f"buy_data = {buy_data} sell_data = {sell_data}")
            continue

        actual_diff = (sell_bid - buy_ask) / buy_ask * 100
        min_volume = min(buy_vol_ask, sell_vol_bid)

        if min_volume < min_usd_amount:
            continue
        if not is_valid_diff(actual_diff):
            continue

        clean_symbol = symbol.replace("_USDT", "")
        opportunities.append({
            "type": f"{buy_exchange} {buy_type.capitalize()} → {sell_exchange} {sell_type.capitalize()}",
            "symbol": symbol,
            "buy_exchange": buy_exchange,
            "sell_exchange": sell_exchange,
            "buy_type": buy_type,
            "sell_type": sell_type,
            "buy_price": buy_ask,
            "sell_price": sell_bid,
            "volume": min_volume,
            "profit_percent": actual_diff,
            "buy_link": link(clean_symbol, buy_type, buy_exchange),
            "sell_link": link(clean_symbol, sell_type, sell_exchange),
        })
        dataApp.opportunities.append({
            "type": f"{buy_exchange} {buy_type.capitalize()} → {sell_exchange} {sell_type.capitalize()}",
            "symbol": symbol,
            "buy_exchange": buy_exchange,
            "sell_exchange": sell_exchange,
            "buy_type": buy_type,
            "sell_type": sell_type,
            "buy_price": buy_ask,
            "sell_price": sell_bid,
            "volume": min_volume,
            "profit_percent": actual_diff,
            "buy_link": link(clean_symbol, buy_type, buy_exchange),
            "sell_link": link(clean_symbol, sell_type, sell_exchange),
        })

        # if telegram_sender: # Проверка, что функция была передана
        #     await telegram_sender({
        #     "type": f"{buy_exchange} {buy_type.capitalize()} → {sell_exchange} {sell_type.capitalize()}",
        #     "symbol": symbol,
        #     "buy_exchange": buy_exchange,
        #     "sell_exchange": sell_exchange,
        #     "buy_type": buy_type,
        #     "sell_type": sell_type,
        #     "buy_price": buy_ask,
        #     "sell_price": sell_bid,
        #     "volume": min_volume,
        #     "profit_percent": actual_diff,
        #     "buy_link": link(clean_symbol, buy_type, buy_exchange),
        #     "sell_link": link(clean_symbol, sell_type, sell_exchange),
        # })

    return opportunities


def check_close_opportunities(close_list):
    if len(close_list) == 0:
        return []

    closed_opps = []

    def link(coin, type_, exchange):
        coin = coin.replace("_", "").lower()
        coin_dash = f"{coin}-usdt"     

        if exchange == "MEXC":
            return f"https://www.mexc.com/exchange/{coin}" if type_ == "spot" else f"https://www.mexc.com/futures/contract/{coin}_USDT"
        elif exchange == "Gate":
            return f"https://www.gate.io/trade/{coin}_USDT" if type_ == "spot" else f"https://www.gate.io/futures_trade/USDT/{coin}_USDT"
        elif exchange == "Bingx":
            return f"https://bingx.com/en-us/spot/{coin}_USDT/" if type_ == "spot" else f"https://bingx.com/en-us/futures/{coin}_USDT/"
        elif exchange == "Bybit":
            return f"https://www.bybit.com/trade/spot/{coin.upper()}USDT" if type_ == "spot" else f"https://www.bybit.com/trade/usdt/{coin.upper()}USDT"
        elif exchange == "BitGet":
            return f"https://www.bitget.com/en/spot/{coin.upper()}USDT" if type_ == "spot" else f"https://www.bitget.com/en/futures/usdt/{coin.upper()}USDT"
        elif exchange == "Binance":
            return f"https://www.binance.com/en/trade/{coin.upper()}_USDT" if type_ == "spot" else f"https://www.binance.com/en/futures/{coin.upper()}USDT"
        elif exchange == "Hyperliquid":
            return f"https://www.hyperliquid.xyz/trade/{coin.upper()}-USDT" if type_ == "spot" else f"https://www.hyperliquid.xyz/futures/{coin.upper()}-USDT"
        elif exchange == "HTX":
            return f"https://www.htx.com/trade/{coin}-USDT" if type_ == "spot" else f"https://www.htx.com/futures/{coin}-USDT"
        elif exchange == "XT":
            return f"https://www.xt.com/trade/{coin.lower()}_usdt" if type_ == "spot" else f"https://www.xt.com/contract/{coin.lower()}_usdt"
        elif exchange == "OKX":
            return f"https://www.okx.com/trade-spot/{coin.lower()}_usdt" if type_ == "spot" else f"https://www.okx.com/trade-swap/{coin.lower()}_usdt"
        elif exchange == "Coinex":
            return f"https://www.coinex.com/exchange/{coin_dash}" if type_ == "spot" else f"https://www.coinex.com/futures/linear/{coin_dash}"

    async def process_opp(key, old_opp):
        symbol = old_opp['symbol']
        buy_exchange_name = old_opp['buy_exchange']
        sell_exchange_name = old_opp['sell_exchange']
        buy_type = old_opp['buy_type']
        sell_type = old_opp['sell_type']

        # Параллельный вызов тяжелых функций
        buy_future = asyncio.to_thread(getBayAndPriceSpot if buy_type == "spot" else getBayAndPriceFutures, symbol, buy_exchange_name)
        sell_future = asyncio.to_thread(getBayAndPriceSpot if sell_type == "spot" else getBayAndPriceFutures, symbol, sell_exchange_name)

        buy_bid, buy_ask, buy_volume_asks, buy_volume_bids = await buy_future
        sell_bid, sell_ask, sell_volume_asks, sell_volume_bids = await sell_future

        if None in [buy_bid, buy_ask, buy_volume_asks, buy_volume_bids, sell_bid, sell_ask, sell_volume_asks, sell_volume_bids]:
            return

        if buy_bid == 0 or sell_ask == 0:
            return

        #  минус странное явление
        actual_diff = (sell_ask - buy_bid) / buy_bid * 100
        min_volume = min(buy_volume_asks, sell_volume_bids)

        new_opp = {
            "type": f"{buy_exchange_name} {buy_type.capitalize()} → {sell_exchange_name} {sell_type.capitalize()}",
            "symbol": symbol,
            "buy_exchange": buy_exchange_name,
            "sell_exchange": sell_exchange_name,
            "buy_type": buy_type,
            "sell_type": sell_type,
            "buy_price": buy_bid,
            "sell_price": sell_ask,
            "volume": min_volume,
            "profit_percent": actual_diff,
            "buy_link": link(symbol.replace("_USDT", ""), buy_type, buy_exchange_name),
            "sell_link": link(symbol.replace("_USDT", ""), sell_type, sell_exchange_name),
        }

        old_profit = old_opp['profit_percent']
        new_profit = new_opp['profit_percent']

        # if new_profit <= 0:
        #     del close_list[key]
        #     return

        if new_profit < old_profit - dataApp.MIN_DIFFERENT_PROFIT_FOR_CLOSE:
            close_list[key] = new_opp

            msg = (
                f"🔁 <b>{new_opp['type']}</b>\n"
                f"Монета: <b>{new_opp['symbol']}</b>\n"
                f"🟢 Закрыть Покупку ({new_opp['buy_type'].upper()} на {new_opp['buy_exchange']}): "
                f"<a href='{new_opp['buy_link']}'>${new_opp['buy_price']}</a>\n"
                f"🔴 Закрыть Продажу ({new_opp['sell_type'].upper()} на {new_opp['sell_exchange']}): "
                f"<a href='{new_opp['sell_link']}'>${new_opp['sell_price']}</a>\n"
                f"💰 Объём: {new_opp['volume']}\n"
                f"📈 Прибыль: <b>{new_opp['profit_percent']:.2f}%</b>"
            )

            print("Сходимость сделки!!! ->\n + " + msg)
            closed_opps.append(new_opp)

    # Асинхронно запускаем все проверки
    async def run_all():
        tasks = [process_opp(key, old_opp) for key, old_opp in list(close_list.items())]
        await asyncio.gather(*tasks)

    asyncio.run(run_all())
    return closed_opps

def getBayAndPriceSpot(symbol, exchange_name):
    if exchange_name == "MEXC":
        return get_order_book_mexc_spot(symbol)
    elif exchange_name == "Gate":
        return get_order_book_gate_spot(symbol)
    elif exchange_name == "Bingx":
        return get_order_book_bingx_spot(symbol)
    elif exchange_name == "Bybit":
        return get_order_book_bybit_spot(symbol)
    elif exchange_name == "BitGet":
        return get_order_book_bitget_spot(symbol)
    elif exchange_name == "Binance":
        return get_order_book_binance_spot(symbol)
    elif exchange_name == "HTX":
        return get_order_book_htx(symbol)
    elif exchange_name == "XT":
        return get_xt_order_book_spot(symbol)
    elif exchange_name == "OKX":
        return get_okx_order_book_spot(symbol)
    elif exchange_name == "Coinex":
        return get_coinex_order_book_spot(symbol)


def getBayAndPriceFutures(symbol, exchange_name):
    if exchange_name == "MEXC":
        return get_order_book_mexc_futures(symbol)
    elif exchange_name == "Gate":
        return get_order_book_gate_futures(symbol)
    elif exchange_name == "Bingx":
        return get_order_book_bingx_futures(symbol)
    elif exchange_name == "Bybit":
        return get_order_book_bybit_futures(symbol)
    elif exchange_name == "BitGet":
        return get_order_book_bitget_futures(symbol)
    elif exchange_name == "Binance":
        return get_order_book_binance_futures(symbol)
    elif exchange_name == "Hyperliquid":
        return get_order_book_hyperliquid_futures(symbol)
    elif exchange_name == "HTX":
        return get_order_book_htx(symbol)
    # elif exchange_name == "XT":
    #     return get_xt_order_book_futures(symbol)
    elif exchange_name == "OKX":
        return get_okx_order_book_futures(symbol)
    elif exchange_name == "Coinex":
        return get_coinex_order_book_futures(symbol)