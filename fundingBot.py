# Фандинг-бот «Снайпер»: связка Bybit LONG / MEXC SHORT.
#
# Доход связки по фандингу = фандинг MEXC − фандинг Bybit, приведённый к «% в день».
# (Лонг на Bybit получает, когда фандинг там отрицательный; шорт на MEXC — когда положительный.
#  Если фандинг «перевернулся» и на MEXC стал больше, чем на Bybit, доход уходит в минус.)
#
# Сигнал, если выполнены все условия:
#   1. Доход сейчас >= FUNDING_MIN_DELTA (0.5% в день).
#   2. Вход по цене не хуже −FUNDING_MAX_ENTRY_LOSS (1%):
#      (ask Bybit − bid MEXC) / bid MEXC * 100 <= 1.
#   3. Суточный доход уже держится >= порога не меньше FUNDING_MIN_HISTORY_HOURS.
#   4. Нейросеть прогнозирует, что доход >= 0.5% в день продержится дольше
#      FUNDING_FORECAST_HOURS (3 дня) без долгого переворота. Она учитывает, сколько
#      раньше длились такие периоды по этой монете.
#
# Запуск отдельно для проверки (без Телеграма):  python fundingBot.py

import math
import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import dataApp

BYBIT_API = "https://api.bybit.com"
MEXC_API = "https://contract.mexc.com"

MODEL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "funding_model.pkl")

_session = requests.Session()
_session.mount("https://", HTTPAdapter(max_retries=Retry(
    total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])))

HOUR_MS = 3_600_000


def _get(url, params=None, timeout=10):
    r = _session.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _f(x, default=None):
    try:
        if x is None or x == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


# ============================ ТЕКУЩИЕ ДАННЫЕ ============================

_BYBIT_MULT_RE = re.compile(r'^(1000000|100000|10000|1000)([A-Z0-9]+)USDT$')
_BYBIT_MULT_SUFFIX_RE = re.compile(r'^([A-Z]+)(1000|10000)USDT$')   # SHIB1000USDT


def _bybit_clean(raw):
    m = _BYBIT_MULT_RE.match(raw)
    if m:
        return m.group(2) + "_USDT", int(m.group(1))
    m = _BYBIT_MULT_SUFFIX_RE.match(raw)
    if m:
        return m.group(1) + "_USDT", int(m.group(2))
    if raw.endswith("USDT") and len(raw) > 4:
        return raw[:-4] + "_USDT", 1
    return None, None


def fetch_bybit_linear():
    """{BASE_USDT: {raw, mult, bid, ask, last, rate(%), next_ts, turnover}}"""
    data = _get(f"{BYBIT_API}/v5/market/tickers", {"category": "linear"})
    out = {}
    for t in (data.get("result") or {}).get("list", []) or []:
        raw = t.get("symbol", "")
        clean, mult = _bybit_clean(raw)
        if not clean:
            continue
        rate = _f(t.get("fundingRate"))
        last = _f(t.get("lastPrice"), 0)
        if rate is None or not last:
            continue
        bid = _f(t.get("bid1Price"), 0) or last
        ask = _f(t.get("ask1Price"), 0) or last
        out[clean] = {
            "raw": raw, "mult": mult,
            "bid": bid / mult, "ask": ask / mult, "last": last / mult,
            "rate": rate * 100,
            "next_ts": int(_f(t.get("nextFundingTime"), 0) or 0),
            "turnover": _f(t.get("turnover24h"), 0),
        }
    return out


_bybit_intervals = {}
_bybit_intervals_ts = 0.0


def fetch_bybit_intervals():
    """{RAWSYMBOL: интервал начисления в часах}. Кэш на час."""
    global _bybit_intervals, _bybit_intervals_ts
    if _bybit_intervals and time.time() - _bybit_intervals_ts < 3600:
        return _bybit_intervals
    out, cursor = {}, None
    for _ in range(20):
        params = {"category": "linear", "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        data = _get(f"{BYBIT_API}/v5/market/instruments-info", params)
        res = data.get("result") or {}
        for it in res.get("list", []) or []:
            minutes = _f(it.get("fundingInterval"))
            if minutes:
                out[it.get("symbol")] = max(1, round(minutes / 60))
        cursor = res.get("nextPageCursor")
        if not cursor:
            break
    if out:
        _bybit_intervals, _bybit_intervals_ts = out, time.time()
    return _bybit_intervals


def fetch_mexc_tickers():
    """{BASE_USDT: {bid, ask, last, rate(%), turnover}}"""
    data = _get(f"{MEXC_API}/api/v1/contract/ticker")
    out = {}
    for t in data.get("data", []) or []:
        sym = t.get("symbol", "")
        if not sym.endswith("_USDT"):
            continue
        rate = _f(t.get("fundingRate"))
        last = _f(t.get("lastPrice"), 0)
        if rate is None or not last:
            continue
        out[sym] = {
            "bid": _f(t.get("bid1"), 0) or last,
            "ask": _f(t.get("ask1"), 0) or last,
            "last": last,
            "rate": rate * 100,
            "turnover": _f(t.get("amount24"), 0),
        }
    return out


_mexc_info_cache = {}


def fetch_mexc_funding_info(symbol):
    """{rate(%), interval(ч), next_ts} для одной монеты MEXC. Кэш 5 минут."""
    cached = _mexc_info_cache.get(symbol)
    if cached and time.time() - cached[0] < 300:
        return cached[1]
    data = _get(f"{MEXC_API}/api/v1/contract/funding_rate/{symbol}")
    d = data.get("data") or {}
    info = {
        "rate": (_f(d.get("fundingRate"), 0) or 0) * 100,
        "interval": int(_f(d.get("collectCycle"), 8) or 8),
        "next_ts": int(_f(d.get("nextSettleTime"), 0) or 0),
    }
    _mexc_info_cache[symbol] = (time.time(), info)
    return info


# ============================ ИСТОРИЯ ФАНДИНГА ============================

_hist_cache = {}
HIST_TTL = 1800


def _cached_hist(key, loader):
    c = _hist_cache.get(key)
    if c and time.time() - c[0] < HIST_TTL:
        return c[1]
    val = loader()
    _hist_cache[key] = (time.time(), val)
    return val


def _enough_history(rows):
    if len(rows) < 2:
        return False
    span = max(r[0] for r in rows) - min(r[0] for r in rows)
    return span >= dataApp.FUNDING_HISTORY_DAYS * 24 * HOUR_MS


def fetch_bybit_history(raw_symbol):
    """[(ts_ms, rate%)] по возрастанию времени, примерно за FUNDING_HISTORY_DAYS дней."""
    def load():
        out, end = {}, None
        for _ in range(6):
            params = {"category": "linear", "symbol": raw_symbol, "limit": 200}
            if end:
                params["endTime"] = end
            data = _get(f"{BYBIT_API}/v5/market/funding/history", params)
            rows = (data.get("result") or {}).get("list", []) or []
            page = [(int(r["fundingRateTimestamp"]), float(r["fundingRate"]) * 100)
                    for r in rows if r.get("fundingRateTimestamp") and r.get("fundingRate") not in (None, "")]
            if not page:
                break
            out.update(page)
            if len(rows) < 200 or _enough_history(list(out.items())):
                break
            end = min(ts for ts, _ in page) - 1
        return sorted(out.items())
    return _cached_hist(("bybit", raw_symbol), load)


def fetch_mexc_history(symbol):
    """[(ts_ms, rate%)] по возрастанию времени, примерно за FUNDING_HISTORY_DAYS дней."""
    def load():
        out = {}
        for page_num in range(1, 9):
            data = _get(f"{MEXC_API}/api/v1/contract/funding_rate/history",
                        {"symbol": symbol, "page_num": page_num, "page_size": 100})
            rows = (data.get("data") or {}).get("resultList", []) or []
            page = [(int(r["settleTime"]), float(r["fundingRate"]) * 100)
                    for r in rows if r.get("settleTime") and r.get("fundingRate") is not None]
            if not page:
                break
            out.update(page)
            if len(rows) < 100 or _enough_history(list(out.items())):
                break
        return sorted(out.items())
    return _cached_hist(("mexc", symbol), load)


def hourly_rates(history):
    """
    Раскладывает начисления по часам: {номер_часа: ставка% в час}.
    Ставка начисления в момент T покрывает период (T − интервал, T].
    Интервал берём из разницы соседних начислений (1..8 ч).
    """
    out = {}
    if not history:
        return out
    for i, (ts, rate) in enumerate(history):
        if i > 0:
            gap = round((ts - history[i - 1][0]) / HOUR_MS)
        elif len(history) > 1:
            gap = round((history[1][0] - ts) / HOUR_MS)
        else:
            gap = 8
        interval = min(max(gap, 1), 8)
        end_h = int(round(ts / HOUR_MS))
        per_hour = rate / interval
        for h in range(end_h - interval + 1, end_h + 1):
            out[h] = per_hour
    return out


def calc_delta(bybit_pct, mexc_pct, mode=None):
    """Доход связки LONG Bybit / SHORT MEXC по фандингу (в %)."""
    mode = mode or dataApp.FUNDING_DELTA_MODE
    if mode == "abs":
        return abs(bybit_pct) - abs(mexc_pct)
    return mexc_pct - bybit_pct


def _norm_hours():
    return dataApp.FUNDING_NORMALIZE_HOURS or 24


def delta_series(bybit_hist, mexc_hist):
    """
    Почасовой ряд дохода связки (в % за FUNDING_NORMALIZE_HOURS, по умолчанию — в день).
    Возвращает список (час, доход%, bybit%, mexc%) по возрастанию; разрывы сохраняются.
    """
    hb, hm = hourly_rates(bybit_hist), hourly_rates(mexc_hist)
    n = _norm_hours()
    series = []
    for h in sorted(set(hb) & set(hm)):
        b, m = hb[h] * n, hm[h] * n
        series.append((h, calc_delta(b, m), b, m))
    return series


def _contiguous_runs(series):
    """Разбивает ряд на непрерывные по часам куски."""
    runs, cur = [], []
    for row in series:
        if cur and row[0] - cur[-1][0] != 1:
            runs.append(cur)
            cur = []
        cur.append(row)
    if cur:
        runs.append(cur)
    return runs


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs):
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


# ===================== ЭПИЗОДЫ: сколько раньше держался доход =====================
#
# «Эпизод» — период, когда связка приносила >= порога В ДЕНЬ. Смотрим на средний доход
# за последние 24 часа, а не на каждое начисление отдельно: так одно слабое начисление
# не рвёт период, а переворот фандинга (MEXC стал больше Bybit) — рвёт.

ROLL_HOURS = 24


class EpisodeTracker:
    """Идёт по почасовому ряду дохода и считает эпизоды и признаки для нейросети."""

    def __init__(self, threshold, horizon):
        self.thr = threshold
        self.horizon = horizon
        self.d = []            # доход по часам
        self.b = []
        self.m = []
        self.csum = [0.0]      # префиксные суммы для скользящего среднего
        self.streak = 0        # текущая серия часов с суточным доходом >= порога
        self.episodes = []     # длины завершённых эпизодов (ч)
        self.hours_above = 0

    def push(self, delta, b, m):
        self.d.append(delta)
        self.b.append(b)
        self.m.append(m)
        self.csum.append(self.csum[-1] + delta)
        if self.rolling() >= self.thr:
            self.streak += 1
            self.hours_above += 1
        else:
            if self.streak:
                self.episodes.append(self.streak)
            self.streak = 0

    def rolling(self, hours=ROLL_HOURS):
        n = min(hours, len(self.d))
        return (self.csum[-1] - self.csum[-1 - n]) / n if n else 0.0

    def summary(self):
        """Человекочитаемая сводка по прошлым эпизодам."""
        eps = self.episodes
        return {
            "count": len(eps),
            "avg": _mean(eps),
            "max": max(eps) if eps else 0,
            "long": sum(1 for e in eps if e >= self.horizon),
            "hours": len(self.d),
        }

    def features(self, interval):
        d = self.d
        cur = d[-1]
        eps = self.episodes
        last168 = d[-168:]
        return [
            cur,
            _mean(d[-8:]),
            self.rolling(24),
            self.rolling(72),
            _std(d[-24:]),
            cur - d[-25] if len(d) >= 25 else 0.0,
            math.log1p(self.streak),
            math.log1p(len(eps)),
            math.log1p(_mean(eps)),
            math.log1p(max(eps) if eps else 0),
            (sum(1 for e in eps if e >= self.horizon) / len(eps)) if eps else 0.0,
            sum(1 for x in last168 if x < 0) / len(last168),
            self.hours_above / len(d),
            math.log1p(len(d)),
            self.b[-1],
            self.m[-1],
            float(interval),
        ]


FEATURE_NAMES = [
    "income_now", "mean_8h", "income_24h", "income_72h", "std_24h", "change_24h",
    "log_streak", "log_n_episodes", "log_avg_episode", "log_max_episode",
    "share_long_episodes", "flip_share_7d", "share_hours_above", "log_history",
    "bybit_now", "mexc_now", "bybit_interval",
]


def track(deltas, b_vals, m_vals, threshold=None, horizon=None):
    tr = EpisodeTracker(threshold if threshold is not None else dataApp.FUNDING_MIN_DELTA,
                        horizon or dataApp.FUNDING_FORECAST_HOURS)
    for d, b, m in zip(deltas, b_vals, m_vals):
        tr.push(d, b, m)
    return tr


def future_label(future, threshold, max_flip_hours):
    """1 — следующие часы связка приносила в среднем >= порога и почти не переворачивалась."""
    if not future:
        return 0
    flips = sum(1 for x in future if x < 0)
    return 1 if _mean(future) >= threshold and flips <= max_flip_hours else 0


def build_samples(series, bybit_interval, threshold, horizon, step=4):
    """
    Обучающие примеры из одного ряда.
    Берём моменты, где доход уже заметный (>= половины порога), и смотрим,
    продержался ли он следующие `horizon` часов (в среднем >= порога, без долгого переворота).
    """
    X, y = [], []
    min_hist = 24
    max_flip = dataApp.FUNDING_MAX_FLIP_HOURS
    for run in _contiguous_runs(series):
        if len(run) < min_hist + horizon + 1:
            continue
        deltas = [r[1] for r in run]
        tr = EpisodeTracker(threshold, horizon)
        for t, row in enumerate(run):
            tr.push(row[1], row[2], row[3])
            if t < min_hist or t + horizon >= len(run) or t % step:
                continue
            if deltas[t] < threshold * 0.5:
                continue
            X.append(tr.features(bybit_interval))
            y.append(future_label(deltas[t + 1:t + 1 + horizon], threshold, max_flip))
    return X, y


def _model_config():
    """Настройки, от которых зависит смысл модели: при их изменении модель обучается заново."""
    return {"threshold": dataApp.FUNDING_MIN_DELTA, "horizon": dataApp.FUNDING_FORECAST_HOURS,
            "flip": dataApp.FUNDING_MAX_FLIP_HOURS, "norm": _norm_hours(),
            "mode": dataApp.FUNDING_DELTA_MODE}


class FundingForecaster:
    """Небольшая нейросеть (MLP), которая учится на истории фандинга Bybit/MEXC."""

    MIN_SAMPLES = 60
    MIN_PER_CLASS = 10

    def __init__(self):
        self.model = None
        self.trained_at = None
        self.info = "не обучена"
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        try:
            import joblib
            if os.path.exists(MODEL_FILE):
                bundle = joblib.load(MODEL_FILE)
                if bundle.get("features") == FEATURE_NAMES and bundle.get("config") == _model_config():
                    self.model = bundle["model"]
                    self.trained_at = bundle.get("trained_at")
                    self.info = bundle.get("info", "загружена с диска")
                    print(f"[funding] Нейросеть загружена: {self.info}")
        except Exception as e:
            print(f"[funding] Не удалось загрузить модель: {e}")

    def train(self, symbols_limit=None):
        """Собирает историю по общим монетам Bybit/MEXC и обучает MLP. Долгая операция."""
        try:
            from sklearn.neural_network import MLPClassifier
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
            from sklearn.model_selection import GroupShuffleSplit
            import joblib
        except ImportError:
            self.info = "scikit-learn не установлен (pip install scikit-learn) — работает эвристика"
            print(f"[funding] {self.info}")
            return False

        threshold = dataApp.FUNDING_MIN_DELTA
        horizon = dataApp.FUNDING_FORECAST_HOURS

        bybit = fetch_bybit_linear()
        mexc = fetch_mexc_tickers()
        intervals = fetch_bybit_intervals()
        common = [s for s in bybit if s in mexc
                  and bybit[s]["turnover"] >= dataApp.FUNDING_MIN_TURNOVER
                  and mexc[s]["turnover"] >= dataApp.FUNDING_MIN_TURNOVER]
        common.sort(key=lambda s: -abs(bybit[s]["rate"] - mexc[s]["rate"]))
        if symbols_limit:
            common = common[:symbols_limit]
        print(f"[funding] Обучение: собираю историю по {len(common)} монетам...")

        def collect(sym):
            try:
                raw = bybit[sym]["raw"]
                series = delta_series(fetch_bybit_history(raw), fetch_mexc_history(sym))
                time.sleep(0.15)  # бережём лимиты MEXC
                return sym, build_samples(series, intervals.get(raw, 8), threshold, horizon)
            except Exception as e:
                print(f"[funding] история {sym}: {e}")
                return sym, ([], [])

        X, y, groups = [], [], []
        with ThreadPoolExecutor(max_workers=4) as pool:
            for sym, (xs, ys) in pool.map(collect, common):
                X += xs
                y += ys
                groups += [sym] * len(xs)

        pos = sum(y)
        neg = len(y) - pos
        if len(y) < self.MIN_SAMPLES or pos < self.MIN_PER_CLASS or neg < self.MIN_PER_CLASS:
            self.info = (f"мало данных для обучения ({len(y)} примеров: {pos} держались / {neg} нет) "
                         f"— работает эвристика по истории")
            print(f"[funding] {self.info}")
            return False

        def new_model():
            return make_pipeline(
                StandardScaler(),
                MLPClassifier(hidden_layer_sizes=(32, 16), alpha=1e-3, max_iter=800,
                              random_state=42),
            )

        def balanced(xs, ys):
            """Случаев «держался» мало — дублируем их, чтобы классов было поровну.
            Иначе сеть учится всегда отвечать «не продержится»."""
            rnd = random.Random(42)
            pos_idx = [i for i, v in enumerate(ys) if v == 1]
            neg_idx = [i for i, v in enumerate(ys) if v == 0]
            small, big = (pos_idx, neg_idx) if len(pos_idx) < len(neg_idx) else (neg_idx, pos_idx)
            if not small:
                return xs, ys
            extra = [rnd.choice(small) for _ in range(len(big) - len(small))]
            idx = list(range(len(ys))) + extra
            rnd.shuffle(idx)
            return [xs[i] for i in idx], [ys[i] for i in idx]

        # Честная проверка: тестовые монеты не участвуют в обучении.
        # Считаем не общую «точность» (при перекосе классов она бессмысленна),
        # а сколько держащихся случаев сеть нашла и сколько из её сигналов верные.
        acc_text = ""
        try:
            if len(set(groups)) >= 5:
                for seed in range(20):
                    split = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed)
                    tr, te = next(split.split(X, y, groups))
                    if sum(y[i] for i in te) >= 3:
                        break
                y_te = [y[i] for i in te]
                if sum(y_te) > 0:
                    m = new_model().fit(*balanced([X[i] for i in tr], [y[i] for i in tr]))
                    pred = m.predict_proba([X[i] for i in te])[:, 1] >= dataApp.FUNDING_MIN_PROBA
                    hit = sum(1 for p, t in zip(pred, y_te) if p and t)
                    fired = int(sum(pred))
                    acc_text = (f"; проверка на других монетах: нашла {hit} из {sum(y_te)} долгих периодов, "
                                f"верных сигналов {hit} из {fired}")
        except Exception as e:
            print(f"[funding] проверка модели не удалась: {e}")

        model = new_model().fit(*balanced(X, y))
        info = (f"обучена {time.strftime('%Y-%m-%d %H:%M')} на {len(y)} примерах "
                f"({pos} держались > {horizon // 24} дн. / {neg} нет){acc_text}")
        with self._lock:
            self.model = model
            self.trained_at = time.time()
            self.info = info
        try:
            joblib.dump({"model": model, "features": FEATURE_NAMES, "config": _model_config(),
                         "trained_at": self.trained_at, "info": info}, MODEL_FILE)
        except Exception as e:
            print(f"[funding] не удалось сохранить модель: {e}")
        print(f"[funding] Нейросеть {info}")
        return True

    def predict(self, tracker, bybit_interval):
        """
        tracker — EpisodeTracker, прошедший всю историю + текущий момент.
        Возвращает (вероятность или None, продержится_долго: bool, метод: str).
        """
        with self._lock:
            model = self.model
        if model is not None and tracker.d:
            try:
                proba = float(model.predict_proba([tracker.features(bybit_interval)])[0][1])
                return proba, proba >= dataApp.FUNDING_MIN_PROBA, "нейросеть"
            except Exception as e:
                print(f"[funding] ошибка прогноза: {e}")
        ok = tracker.streak >= dataApp.FUNDING_FALLBACK_HOURS
        return None, ok, "эвристика (нейросеть ещё не обучена)"


# ============================ СКАНЕР ============================

def _links(symbol):
    base = symbol.replace("_USDT", "")
    return (f"https://www.bybit.com/trade/usdt/{base}USDT",
            f"https://www.mexc.com/futures/contract/{base}_USDT")


def scan_funding_opportunities(forecaster, verbose=False):
    threshold = dataApp.FUNDING_MIN_DELTA
    norm = dataApp.FUNDING_NORMALIZE_HOURS

    bybit = fetch_bybit_linear()
    mexc = fetch_mexc_tickers()
    intervals = fetch_bybit_intervals()

    # Быстрый отсев: на одной из бирж должен быть заметный фандинг
    candidates = []
    for sym, b in bybit.items():
        m = mexc.get(sym)
        if not m:
            continue
        if b["turnover"] < dataApp.FUNDING_MIN_TURNOVER or m["turnover"] < dataApp.FUNDING_MIN_TURNOVER:
            continue
        if not (0.5 <= b["last"] / m["last"] <= 2):   # разные контракты под одним тикером
            continue
        b_int = intervals.get(b["raw"], 8)
        b_norm = b["rate"] * (norm / b_int) if norm else b["rate"]
        # максимально возможная дельта при любом интервале MEXC (1..8ч)
        m_max = abs(m["rate"]) * (norm if norm else 1)
        if abs(b_norm) + m_max < threshold:
            continue
        candidates.append(sym)

    stats = {"candidates": len(candidates), "delta": 0, "price": 0, "history": 0, "forecast": 0}
    opps = []
    for sym in candidates:
        b, m = bybit[sym], mexc[sym]
        try:
            m_info = fetch_mexc_funding_info(sym)
        except Exception as e:
            print(f"[funding] MEXC funding_rate {sym}: {e}")
            continue
        b_int = intervals.get(b["raw"], 8)
        m_int = m_info["interval"] or 8
        m_rate = m_info["rate"] if m_info["rate"] else m["rate"]

        b_norm = b["rate"] * (norm / b_int) if norm else b["rate"]
        m_norm = m_rate * (norm / m_int) if norm else m_rate
        delta = calc_delta(b_norm, m_norm)

        # 1. доход по фандингу сейчас (% в день)
        if delta < threshold:
            continue
        stats["delta"] += 1

        # 2. разница цен: покупаем на Bybit по ask, продаём на MEXC по bid.
        #    Можно зайти в минус до FUNDING_MAX_ENTRY_LOSS — отобьётся фандингом за несколько дней.
        price_diff = (b["ask"] - m["bid"]) / m["bid"] * 100
        if price_diff > dataApp.FUNDING_MAX_ENTRY_LOSS:
            continue
        stats["price"] += 1

        # 3. история
        try:
            series = delta_series(fetch_bybit_history(b["raw"]), fetch_mexc_history(sym))
        except Exception as e:
            print(f"[funding] история {sym}: {e}")
            continue
        last_run = _contiguous_runs(series)[-1] if series else []
        tracker = track([r[1] for r in last_run], [r[2] for r in last_run], [r[3] for r in last_run])
        hist_streak = tracker.streak          # по завершённым начислениям
        past = tracker.summary()
        if hist_streak < dataApp.FUNDING_MIN_HISTORY_HOURS:
            if verbose:
                recent = ", ".join(f"{r[1]:+.2f}" for r in series[-24::4]) if series else "нет данных"
                print(f"[funding]   {sym}: доход сейчас {delta:.2f}%/день, вход {price_diff:+.2f}% — "
                      f"по истории держится {hist_streak} ч (нужно {dataApp.FUNDING_MIN_HISTORY_HOURS}); "
                      f"доход за сутки (каждые 4ч): {recent}")
            continue
        stats["history"] += 1

        # 4. прогноз нейросети: продержится ли доход >= порога дольше горизонта
        tracker.push(delta, b_norm, m_norm)   # текущий момент
        proba, long_enough, method = forecaster.predict(tracker, b_int)
        if not long_enough:
            if verbose:
                p_txt = f"{proba * 100:.0f}%" if proba is not None else method
                print(f"[funding]   {sym}: доход {delta:.2f}%/день, держится {hist_streak} ч, "
                      f"раньше периодов {past['count']} (ср. {past['avg']:.0f} ч, макс {past['max']} ч) — "
                      f"прогноз не прошёл ({p_txt})")
            continue
        stats["forecast"] += 1

        bybit_link, mexc_link = _links(sym)
        opps.append({
            "symbol": sym,
            "bybit_price": b["ask"], "mexc_price": m["bid"],
            "bybit_rate": b["rate"], "mexc_rate": m_rate,
            "bybit_interval": b_int, "mexc_interval": m_int,
            "bybit_norm": b_norm, "mexc_norm": m_norm,
            "bybit_next": b["next_ts"], "mexc_next": m_info["next_ts"],
            "delta": delta, "price_diff": price_diff,
            "history_hours": hist_streak, "past": past,
            "proba": proba, "method": method,
            "bybit_link": bybit_link, "mexc_link": mexc_link,
        })

    if verbose:
        print(f"[funding] кандидатов {stats['candidates']}, прошли доход {stats['delta']}, "
              f"цену {stats['price']}, историю {stats['history']}, прогноз {stats['forecast']}")
    # выше — те, что быстрее отбивают вход и больше приносят
    opps.sort(key=lambda o: -(o["delta"] * dataApp.FUNDING_FORECAST_HOURS / 24 - max(o["price_diff"], 0)))
    return opps


# ============================ СООБЩЕНИЯ ============================

_last_sent = {}


def should_send_funding(opp):
    key = opp["symbol"]
    prev = _last_sent.get(key)
    now = time.time()
    if prev is None or abs(opp["delta"] - prev[1]) >= dataApp.FUNDING_RESEND_DELTA \
            or now - prev[0] >= dataApp.FUNDING_RESEND_SECONDS:
        _last_sent[key] = (now, opp["delta"])
        return True
    return False


def _fmt_price(p):
    return f"{p:.8f}".rstrip("0").rstrip(".") if p < 1 else f"{p:.4f}".rstrip("0").rstrip(".")


def _until(ts_ms):
    if not ts_ms:
        return ""
    left = int(ts_ms / 1000 - time.time())
    if left <= 0:
        return ""
    return f", начисление через {left // 3600}ч {left % 3600 // 60}м"


def _per_label():
    n = _norm_hours()
    return "в день" if n == 24 else f"за {n}ч"


def _hours_text(h):
    h = int(round(h))
    if h >= 48:
        return f"{h / 24:.1f} дн."
    return f"{h} ч"


def format_funding_message(opp):
    per = _per_label()
    days = dataApp.FUNDING_FORECAST_HOURS / 24

    def rate_line(rate, interval, rate_norm):
        return f"{rate:+.4f}% / {interval}ч (≈ {rate_norm:+.3f}% {per})"

    if opp["proba"] is not None:
        forecast = (f"🤖 Прогноз нейросети: доход ≥{dataApp.FUNDING_MIN_DELTA}% {per} продержится "
                    f"> {days:.0f} дн. с вероятностью <b>{opp['proba'] * 100:.0f}%</b>")
    else:
        forecast = (f"🤖 Прогноз: {opp['method']} — уже держится "
                    f"≥ {_hours_text(dataApp.FUNDING_FALLBACK_HOURS)}")

    past = opp.get("past") or {}
    if past.get("count"):
        past_line = (f"📜 Раньше по монете: {past['count']} период(ов) с доходом ≥{dataApp.FUNDING_MIN_DELTA}% {per}, "
                     f"в среднем {_hours_text(past['avg'])}, максимум {_hours_text(past['max'])}, "
                     f"дольше {days:.0f} дн. — {past['long']}\n")
    else:
        past_line = (f"📜 Завершённых периодов с доходом ≥{dataApp.FUNDING_MIN_DELTA}% {per} "
                     f"за {_hours_text(past.get('hours', 0))} истории не было\n")

    loss = max(opp["price_diff"], 0)
    payback = f", отобьётся фандингом за ~{_hours_text(loss / opp['delta'] * 24)}" if loss > 0 else ""
    expected = opp["delta"] * days - loss

    return (
        f"💸 <b>Снайпер: Bybit LONG / MEXC SHORT</b>\n"
        f"Монета: <b>{opp['symbol']}</b>\n"
        f"🟢 Лонг Bybit: <a href='{opp['bybit_link']}'>${_fmt_price(opp['bybit_price'])}</a> — фандинг "
        f"{rate_line(opp['bybit_rate'], opp['bybit_interval'], opp['bybit_norm'])}{_until(opp['bybit_next'])}\n"
        f"🔴 Шорт MEXC: <a href='{opp['mexc_link']}'>${_fmt_price(opp['mexc_price'])}</a> — фандинг "
        f"{rate_line(opp['mexc_rate'], opp['mexc_interval'], opp['mexc_norm'])}{_until(opp['mexc_next'])}\n"
        f"📊 Доход по фандингу: <b>{opp['delta']:.3f}% {per}</b>\n"
        f"📉 Вход по цене: {-opp['price_diff']:+.3f}% (допустимо до -{dataApp.FUNDING_MAX_ENTRY_LOSS}%){payback}\n"
        f"💰 Если продержится {days:.0f} дн.: ≈ {expected:+.2f}% с учётом входа\n"
        f"⏳ Уже держится: {_hours_text(opp['history_hours'])}\n"
        f"{past_line}"
        f"{forecast}"
    )


if __name__ == "__main__":
    fc = FundingForecaster()
    if fc.model is None:
        fc.train()
    print(f"[funding] модель: {fc.info}")
    found = scan_funding_opportunities(fc, verbose=True)
    for o in found:
        print(format_funding_message(o))
        print()
    if not found:
        print("Сейчас подходящих связок нет.")
