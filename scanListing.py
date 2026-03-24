import ccxt
import json
import time
import re
from datetime import datetime, timedelta

# --- НАСТРОЙКИ СКРИПТА ---

# Список внутренних имен бирж (для CCXT)
EXCHANGES = [
    'mexc', 
    'gate', 
    'bingx', 
    'bybit', 
    'bitget', 
    'binance', 
    'huobi',
    'xt',
    'hyperliquid',
    'okx',
    'coinex'
]

# Словарь для преобразования внутреннего имени в требуемое внешнее имя (для файла listings.txt)
EXCHANGE_MAPPING = {
    'mexc': 'MEXC', 
    'gate': 'Gate', 
    'bingx': 'Bingx', 
    'bybit': 'Bybit', 
    'bitget': 'BitGet', 
    'binance': 'Binance', 
    'huobi': 'HTX',
    'xt': 'XT',
    'hyperliquid': 'Hyperliquid',
    'okx': 'OKX',
    'coinex': 'Coinex'
}

# Имя файла для хранения известных символов (база данных)
KNOWN_SYMBOLS_FILE = "known_symbols.json"

# Имя файла для хранения листингов за текущие сутки (результат)
LISTINGS_FILE = "listings.txt"

# Интервал обновления данных (цикл опроса бирж), в секундах (10 минут = 600)
FETCH_INTERVAL_SECONDS = 300

# Интервал полного сброса данных (таймер сброса), в секундах (24 часа = 86400)
RESET_INTERVAL_SECONDS = 86400 

# --- ФУНКЦИИ УПРАВЛЕНИЯ ФАЙЛАМИ ---

def load_known_symbols():
    """Загружает известный список символов из JSON файла."""
    try:
        with open(KNOWN_SYMBOLS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_known_symbols(data):
    """Сохраняет текущий список символов в JSON файл."""
    with open(KNOWN_SYMBOLS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def append_to_listings(new_coins_map):
    """Добавляет новые монеты в файл listings.txt в требуемом формате: Биржа_МОНЕТА_USDT."""
    
    # 1. Загружаем текущее содержимое файла, чтобы избежать дублирования
    try:
        with open(LISTINGS_FILE, 'r') as f:
            existing_listings_set = set(f.read().split(', '))
            existing_listings_set.discard('')
    except FileNotFoundError:
        existing_listings_set = set()

    # 2. Форматируем и фильтруем новые монеты
    unique_new_coins = set()
    for symbol in new_coins_map:
        if symbol not in existing_listings_set:
            unique_new_coins.add(symbol)

    if unique_new_coins:
        # 3. Добавляем в конец файла через запятую
        formatted_string = ', '.join(sorted(list(unique_new_coins)))
        
        # Чтение файла для определения, нужно ли добавлять начальный разделитель
        try:
            with open(LISTINGS_FILE, 'r+') as f:
                f.seek(0, 2) # Переходим в конец файла
                is_empty = f.tell() == 0
                
                if not is_empty and existing_listings_set:
                    # Если файл не пустой (и не только что очищен), добавляем разделитель
                    f.write(f", {formatted_string}")
                else:
                    # Если файл пуст
                    f.write(formatted_string)
        except Exception as e:
            print(f"❌ Ошибка записи в {LISTINGS_FILE}: {e}")
            return 0
            
        print(f"📄 Добавлено {len(unique_new_coins)} новых уникальных листингов в {LISTINGS_FILE}")
        return len(unique_new_coins)
    return 0

def clear_listings_file():
    """Полностью очищает файл listings.txt."""
    with open(LISTINGS_FILE, 'w') as f:
        f.write("")
    print(f"\n--- ⏳ Файл {LISTINGS_FILE} очищен по таймеру! ---")

# --- ФУНКЦИИ ФИЛЬТРАЦИИ И МОНИТОРИНГА ---

def filter_market_symbols(markets):
    """
    НОВАЯ ФУНКЦИЯ: Фильтрует список рынков, включая СПОТ и БЕССРОЧНЫЕ ФЬЮЧЕРСЫ 
    (SWAP/PERPETUAL), исключая срочные фьючерсы, опционы и прочий мусор.
    """
    filtered_symbols = set()
    
    # Регулярное выражение для проверки: пары с USDT/BUSD/USDC/USD
    usdt_pair_regex = re.compile(r'^[A-Z0-9\-\/]+/(USDT|BUSD|USDC|USD|TRY)$')

    for market in markets:
        symbol = market.get('symbol')
        active = market.get('active', True)
        market_type = market.get('type') # 'spot', 'swap', 'future', 'option'
        
        if not symbol or not active:
            continue
            
        # 1. Базовое соответствие формата и активности
        if not usdt_pair_regex.match(symbol):
            continue
            
        # 2. Фильтрация по типу рынка: включаем SPOT и SWAP (бессрочные)
        if market_type in ['spot', 'swap']: 
            
            # Исключаем символы, которые содержат двоеточие (часто опционы или специфичные токены)
            # и токены с плечом (5L, 3S, и т.п., хотя это не идеально, но помогает)
            if ':' in symbol or '3S/' in symbol or '5L/' in symbol or '5S/' in symbol:
                continue

            # --- Форматирование ---
            # Приводим к формату MONETA_USDT (заменяем '/' на '_')
            formatted_symbol = symbol.replace('/', '_')
            
            filtered_symbols.add(formatted_symbol)
            
        # 3. Добавление ограниченной поддержки 'future' (для некоторых бирж, где PERP это 'future')
        elif market_type == 'future':
             # Исключаем срочные контракты (имеют даты или другие разделители)
            if market.get('expiry') or len(symbol.split('/')) > 2 or ':' in symbol:
                continue
                
            # Приводим к формату MONETA_USDT
            formatted_symbol = symbol.replace('/', '_')
            filtered_symbols.add(formatted_symbol)

    return filtered_symbols

def fetch_and_find_new_listings(known_symbols):
    """
    Выполняет запрос к биржам и ищет новые листинги.
    Возвращает set отформатированных строк для записи в listings.txt.
    """
    
    new_listings_for_file = set() 
    current_symbols_all = known_symbols.copy() 

    print(f"\n{'-'*50}\n🔎 Запрос данных. Время: {datetime.now().strftime('%H:%M:%S')}")

    for exchange_id in EXCHANGES:
        
        exchange_start_time = time.time()
        
        try:
            exchange_class = getattr(ccxt, exchange_id)
            exchange = exchange_class({'timeout': 30000})
            
            # Получаем все рынки (спот, фьючерсы, свопы и т.д.)
            markets = exchange.fetch_markets()
            
            # Фильтруем, включая чистые спотовые и бессрочные фьючерсы
            current_symbols_filtered = filter_market_symbols(markets)
            
            # --- Логика определения новых листингов ---
            
            known = set(known_symbols.get(exchange_id, []))
            new_coins_for_exchange = current_symbols_filtered - known
            
            if new_coins_for_exchange:
                
                # --- ФОРМАТИРОВАНИЕ ДЛЯ ФАЙЛА LISTINGS.TXT ---
                
                exchange_name_for_file = EXCHANGE_MAPPING.get(exchange_id, exchange_id.upper())
                
                for coin_symbol in new_coins_for_exchange:
                    # Создаем строку в требуемом формате: Биржа_МОНЕТА_USDT
                    formatted_line = f"{exchange_name_for_file}_{coin_symbol}"
                    new_listings_for_file.add(formatted_line)
                    
                print(f"✅ На {exchange_id.upper()}: {len(new_coins_for_exchange)} НОВЫХ листингов (Спот/Фьюч).")
            
            # --- Обновление базы данных ---
            
            current_symbols_all[exchange_id] = list(current_symbols_filtered)

        except Exception as e:
            print(f"❌ Ошибка при работе с {exchange_id.upper()}: {e}")
            
        print(f"   ({exchange_id.upper()} завершено за {time.time() - exchange_start_time:.2f} сек.)")

    # Сохраняем актуализированный список "известных" символов
    save_known_symbols(current_symbols_all)
    
    return new_listings_for_file

# --- ГЛАВНЫЙ ЦИКЛ ПРОГРАММЫ ---

def main_loop():
    
    print(f"*** 🚀 Запуск Монитора Листингов ***")
    print(f"Интервал запроса: {FETCH_INTERVAL_SECONDS} сек. | Интервал сброса: {timedelta(seconds=RESET_INTERVAL_SECONDS)}")
    
    next_reset_time = datetime.now() + timedelta(seconds=RESET_INTERVAL_SECONDS)
    print(f"Первый сброс данных запланирован на: {next_reset_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    while True:
        try:
            # Проверка таймера сброса
            if datetime.now() >= next_reset_time:
                print(f"\n{'='*50}\n⏰ НАЧИНАЕТСЯ ЕЖЕДНЕВНЫЙ СБРОС ДАННЫХ...")
                
                # 1. Очищаем файл результатов
                clear_listings_file()
                
                # 2. Очищаем базу данных известных символов
                # save_known_symbols({}) 
                
                # 3. Сбрасываем таймер
                next_reset_time = datetime.now() + timedelta(seconds=RESET_INTERVAL_SECONDS)
                print(f"Сброс завершен. Следующий сброс: {next_reset_time.strftime('%Y-%m-%d %H:%M:%S')}\n{'='*50}")

            # --- Основной цикл поиска ---
            
            known_symbols = load_known_symbols()
            new_listings_for_file = fetch_and_find_new_listings(known_symbols)
            
            # --- Обработка результата ---
            
            if new_listings_for_file:
                print(f"\n🎉 Обнаружено {len(new_listings_for_file)} уникальных новых листингов за цикл.")
                
                # Записываем в файл в требуемом формате: Gate_BOT_USDT, HTX_UXLINK_USDT...
                appended_count = append_to_listings(new_listings_for_file)
                
                if appended_count > 0:
                    print(f"⭐ Успешно добавлено {appended_count} новых листингов в {LISTINGS_FILE}")
            else:
                print("\n💤 Новых листингов не обнаружено. Ждем...")
                
            # Пауза до следующего цикла
            time.sleep(FETCH_INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            print("\n\n*** 🛑 Скрипт остановлен пользователем (Ctrl+C). ***")
            break
        except Exception as e:
            print(f"\n!!! КРИТИЧЕСКАЯ ОШИБКА В ОСНОВНОМ ЦИКЛЕ: {e}")
            print("Пауза 60 секунд перед перезапуском...")
            time.sleep(60)

if __name__ == "__main__":
    main_loop()