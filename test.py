import ccxt

# Инициализируем биржу один раз
coinex_spot = ccxt.coinex()
coinex_futures = ccxt.coinex({'options': {'defaultType': 'swap'}})

def calculate_vwap_and_volume(orders):
    """Рассчитывает средневзвешенную цену (VWAP) и суммарный объем."""
    if not orders:
        return 0.0, 0.0
    
    total_volume = sum(order[1] for order in orders)
    if total_volume == 0:
        return 0.0, 0.0
        
    weighted_sum = sum(order[0] * order[1] for order in orders)
    average_price = weighted_sum / total_volume
    return average_price, total_volume

def get_coinex_order_book_spot(symbol="BTC_USDT", limit=50):
    """Получает стакан для спота CoinEx и рассчитывает VWAP."""
    ccxt_symbol = symbol.replace('_', '/')
    try:
        order_book = coinex_spot.fetch_order_book(ccxt_symbol, limit=limit)
        
        avg_bid, vol_bids = calculate_vwap_and_volume(order_book.get('bids', []))
        avg_ask, vol_asks = calculate_vwap_and_volume(order_book.get('asks', []))
        
        return avg_bid, avg_ask, vol_asks, vol_bids
    except Exception as e:
        print(f"❌ Ошибка Spot {symbol}: {e}")
        return 0.0, 0.0, 0.0, 0.0

def get_coinex_order_book_futures(symbol="BTC_USDT", limit=50):
    """Получает стакан для фьючерсов CoinEx и рассчитывает VWAP."""
    ccxt_symbol = symbol.replace('_', '/')
    try:
        order_book = coinex_futures.fetch_order_book(ccxt_symbol, limit=limit)
        
        avg_bid, vol_bids = calculate_vwap_and_volume(order_book.get('bids', []))
        avg_ask, vol_asks = calculate_vwap_and_volume(order_book.get('asks', []))
        
        return avg_bid, avg_ask, vol_asks, vol_bids
    except Exception as e:
        print(f"❌ Ошибка Futures {symbol}: {e}")
        return 0.0, 0.0, 0.0, 0.0
    
def run_test():
    test_symbol = "BTC_USDT"
    print(f"--- Тестирование CoinEx для {test_symbol} ---")
    
    # Тест Спота
    print("\n[SPOT]")
    s_bid, s_ask, s_vol_a, s_vol_b = get_coinex_order_book_spot(test_symbol)
    if s_bid > 0:
        print(f"✅ Успешно!")
        print(f"Средняя цена покупки (Bid): {s_bid:.2f} | Объем: {s_vol_b:.4f}")
        print(f"Средняя цена продажи (Ask): {s_ask:.2f} | Объем: {s_vol_a:.4f}")
    else:
        print("❌ Не удалось получить данные для спота.")

    # Тест Фьючерсов
    print("\n[FUTURES]")
    f_bid, f_ask, f_vol_a, f_vol_b = get_coinex_order_book_futures(test_symbol)
    if f_bid > 0:
        print(f"✅ Успешно!")
        print(f"Средняя цена покупки (Bid): {f_bid:.2f} | Объем: {f_vol_b:.4f}")
        print(f"Средняя цена продажи (Ask): {f_ask:.2f} | Объем: {f_vol_a:.4f}")
    else:
        print("❌ Не удалось получить данные для фьючерсов.")

if __name__ == "__main__":
    run_test()