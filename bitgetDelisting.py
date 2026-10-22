# Мониторинг делистинга на BitGet.
#
# BitGet публикует объявления о снятии монет с торгов (annType=symbol_delisting).
# Модуль периодически тянет эти объявления, вытаскивает тикеры монет и держит их
# в кэше. Бот при формировании связки спрашивает is_bitget_delisting(symbol) —
# это чтение из памяти, без сети, поэтому не блокирует event loop.

import re
import time
import threading

import requests

ANNOUNCE_URL = "https://api.bitget.com/api/v2/public/annoucements"

# Как часто обновлять список делистингов (сек)
REFRESH_INTERVAL_SECONDS = 600

# Слова, которые НЕ являются тикерами монет (отсекаем мусор из заголовков)
_STOPWORDS = {
    "BITGET", "WILL", "DELIST", "DELISTING", "SPOT", "FUTURES", "PERPETUAL",
    "PERP", "USDT", "USDC", "USD", "TRADING", "PAIRS", "PAIR", "AND", "THE",
    "FOR", "OF", "ON", "TO", "A", "AN", "MARGIN", "BOT", "BOTS", "GRID",
    "NOTICE", "ABOUT", "CONTRACT", "CONTRACTS", "COIN", "COINS", "TOKEN",
    "TOKENS", "SWAP", "ANNOUNCEMENT", "REGARDING", "CEASE", "CESSATION",
    "LEVERAGED", "ETF", "ETFS", "NEW", "UTC", "AM", "PM",
}

# Тикер: 2-15 символов, латиница/цифры, не из стоп-листа
_TICKER_RE = re.compile(r"\b([A-Z0-9]{2,15})\b")

_lock = threading.Lock()
_delisting_bases: set = set()
_last_update: float = 0.0


def _extract_tickers(text: str) -> set:
    """Достаёт потенциальные тикеры монет из заголовка/описания объявления."""
    if not text:
        return set()
    found = set()
    for token in _TICKER_RE.findall(text.upper()):
        if token in _STOPWORDS:
            continue
        if token.isdigit():            # годы, числа
            continue
        found.add(token)
        # Если тикер склеен с квотой ("BETAUSDT") — добавляем и базу ("BETA")
        for quote in ("USDT", "USDC", "USD"):
            if token.endswith(quote) and len(token) > len(quote):
                base = token[:-len(quote)]
                if base and base not in _STOPWORDS and not base.isdigit():
                    found.add(base)
                break
    return found


def _fetch_delisting_bases() -> set:
    """Запрос к BitGet за объявлениями о делистинге. Возвращает set базовых монет."""
    bases = set()
    headers = {"User-Agent": "Mozilla/5.0", "locale": "en-US"}

    for ann_type in ("symbol_delisting",):
        try:
            resp = requests.get(
                ANNOUNCE_URL,
                params={"annType": ann_type, "language": "en_US"},
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"BitGet delisting: ошибка запроса ({ann_type}): {e}")
            continue

        if data.get("code") not in ("00000", 0, "0"):
            print(f"BitGet delisting: API вернул {data.get('code')} / {data.get('msg')}")
            continue

        for item in data.get("data", []) or []:
            title = item.get("annTitle", "") or ""
            desc = item.get("annDesc", "") or ""
            bases |= _extract_tickers(title)
            bases |= _extract_tickers(desc)

    return bases


def refresh_bitget_delisting(force: bool = False) -> set:
    """Обновляет кэш делистингов (сетевой вызов). Безопасно звать из потока."""
    global _delisting_bases, _last_update

    now = time.time()
    if not force and (now - _last_update) < REFRESH_INTERVAL_SECONDS and _delisting_bases:
        return _delisting_bases

    bases = _fetch_delisting_bases()

    # Если запрос не удался — не затираем предыдущий валидный список
    if bases:
        with _lock:
            _delisting_bases = bases
            _last_update = now
        print(f"BitGet delisting: обновлён список ({len(bases)} монет)")
    else:
        _last_update = now  # не долбим API, но старый список сохраняем

    with _lock:
        return set(_delisting_bases)


def _base_of(symbol: str) -> str:
    """'BTC_USDT' / 'BTCUSDT' / 'BTC/USDT' -> 'BTC'."""
    s = symbol.upper().replace("/", "_").replace("-", "_")
    if "_" in s:
        return s.split("_", 1)[0]
    if s.endswith("USDT"):
        return s[:-4]
    return s


def is_bitget_delisting(symbol: str) -> bool:
    """True, если монета в текущем списке делистингов BitGet. Чтение из кэша, без сети."""
    base = _base_of(symbol)
    with _lock:
        return base in _delisting_bases


if __name__ == "__main__":
    print("Запрос списка делистингов BitGet...")
    print(refresh_bitget_delisting(force=True))
