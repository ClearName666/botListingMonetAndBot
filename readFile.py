import os

file_path = 'symbols.txt'

def create_string_array_from_file():
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read().strip() # Читаем содержимое и удаляем пробелы по краям
            if not content:
                return [] # Возвращаем пустой список, если файл пуст

            # Разделяем строку по запятым и удаляем пробелы у каждой части
            string_array = [item.strip() for item in content.split(',') if item.strip()]
            return string_array
    except FileNotFoundError:
        print(f"Ошибка: Файл по пути '{file_path}' не найден.")
        return []
    except Exception as e:
        print(f"Произошла ошибка при чтении файла: {e}")
        return []
    
# Используем имя файла, которое мы настроили для листингов
file_path_listings = 'listings.txt' 

def parse_listings_file_to_array():
    """
    Читает файл листингов (например, Gate_BOT_USDT, HTX_UXLINK_USDT)
    и возвращает массив словарей, разделяя биржу и символ.
    """
    
    # Проверяем существование файла
    if not os.path.exists(file_path_listings):
        print(f"Ошибка: Файл по пути '{file_path_listings}' не найден. Убедитесь, что он создан и заполнен.")
        return []
        
    try:
        with open(file_path_listings, 'r', encoding='utf-8') as file:
            content = file.read().strip() # Читаем содержимое и удаляем пробелы по краям
            
            if not content:
                print(f"Внимание: Файл '{file_path_listings}' пуст.")
                return [] # Возвращаем пустой список, если файл пуст

            # 1. Разделяем строку по запятым и удаляем пробелы у каждой части
            string_array = [item.strip() for item in content.split(',') if item.strip()]
            
            result_array = []
            
            # 2. Итерируемся по каждому элементу и парсим его
            for full_symbol in string_array:
                
                # Ищем первый разделитель "_"
                if '_' in full_symbol:
                    # Разделяем строку только по первому вхождению '_'
                    # Пример: 'HTX_UXLINK_USDT' -> ['HTX', 'UXLINK_USDT']
                    try:
                        exchange, symbol = full_symbol.split('_', 1)
                        
                        # Добавляем в массив результат
                        result_array.append({
                            "exchange": exchange, 
                            "symbol": symbol
                        })
                    except ValueError:
                        print(f"Пропущена некорректная строка (неверный формат): {full_symbol}")
                else:
                    print(f"Пропущена строка без разделителя '_': {full_symbol}")

            return result_array
            
    except Exception as e:
        print(f"Произошла ошибка при чтении файла '{file_path_listings}': {e}")
        return []
    
# --- Функция проверки условия листинга ---
def is_listing_match(opp, parsed_listings):
    """
    Проверяет, соответствует ли арбитражная связка монете из файла листингов 
    и совершается ли покупка/продажа на соответствующей бирже.
    
    :param opp: Словарь с данными арбитражной связки.
    :param parsed_listings: Массив словарей из listings.txt (exchange, symbol).
    :return: True, если найдено совпадение.
    """
    
    # 1. Получаем список символов в требуемом формате: MONETA_USDT
    opp_symbol = opp['symbol'] 
    
    # 2. Проходим по всем листингам из файла
    for item in parsed_listings:
        
        # Проверка 1: Совпадение символа монеты (например, "BOT_USDT")
        # Сравнение должно быть точным, так как opp['symbol'] уже в формате МОНЕТА_USDT
        if opp_symbol == item['symbol']:
            
            # Проверка 2: Совпадение биржи покупки ИЛИ продажи с биржей листинга
            listing_exchange = item['exchange'].upper() # 'HTX'
            buy_exchange = opp['buy_exchange'].upper()  # 'HUOBI' или 'HTX'
            sell_exchange = opp['sell_exchange'].upper() # 'BINANCE'
            
            # Важно: Нам нужно учесть, что в opp['buy_exchange'] может быть 'HUOBI',
            # но в файле у нас 'HTX'. Поэтому нужно использовать маппинг.
            # Если у вас в opp['buy_exchange'] уже 'HTX', то это не проблема.
            # Если нет, требуется дополнительный словарь маппинга для buy/sell_exchange.
            
            # Для надежности используем маппинг, который соответствует EXCHANGE_MAPPING
            # из предыдущего ответа, чтобы преобразовать buy/sell_exchange в формат HTX/Gate/etc.
            # Поскольку у нас нет доступа к исходному коду, предположим, что
            # opp['buy_exchange'] и opp['sell_exchange'] уже содержат названия,
            # схожие с теми, что в listings.txt ('HTX', 'Gate', 'MEXC').
            
            if (buy_exchange == listing_exchange) or (sell_exchange == listing_exchange):
                # Найдено совпадение!
                return True
                
    return False

def get_all_listed_symbols() -> set:
    """
    Читает файл листингов (например, Gate_BOT_USDT, HTX_UXLINK_USDT)
    и возвращает набор (set) всех уникальных символов монет (например, {'BOT_USDT', 'UXLINK_USDT'}).
    """
    
    # Проверяем существование файла
    if not os.path.exists(file_path_listings):
        # print(f"Ошибка: Файл по пути '{file_path}' не найден.")
        return set()
        
    unique_symbols = set()
    try:
        with open(file_path_listings, 'r', encoding='utf-8') as file:
            content = file.read().strip()
            
            if not content:
                return set()

            # 1. Разделяем строку по запятым и удаляем пробелы у каждой части
            string_array = [item.strip() for item in content.split(',') if item.strip()]
            
            # 2. Парсим каждый элемент, чтобы извлечь только символ
            for full_symbol in string_array:
                if '_' in full_symbol:
                    try:
                        # Разделяем строку только по первому вхождению '_'
                        # Пример: 'HTX_UXLINK_USDT' -> ['HTX', 'UXLINK_USDT']
                        parts = full_symbol.split('_', 1)
                        if len(parts) == 2:
                             # UPLINK_USDT - это нужная нам часть
                            unique_symbols.add(parts[1]) 
                    except ValueError:
                        pass # Игнорируем некорректно отформатированные строки
                
        return unique_symbols
            
    except Exception as e:
        print(f"Произошла ошибка при чтении файла '{file_path_listings}': {e}")
        return set()

# ----------------------------------------------------------------------

def is_coin_in_listings_file(coin_symbol: str) -> bool:
    """
    Проверяет, есть ли данная монета (например, 'BTC_USDT') в листинге,
    игнорируя, на какой бирже она была обнаружена.

    :param coin_symbol: Символ монеты в формате 'MONETA_USDT'.
    :return: True, если монета найдена в listings.txt.
    """
    all_listed_symbols = get_all_listed_symbols()
    
    # Проверка на точное совпадение символа (MONETA_USDT)
    return coin_symbol in all_listed_symbols