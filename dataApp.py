coins_string = "BTCUSDT,ETHUSDT,BNBUSDT,XRPUSDT,ADAUSDT,SOLUSDT,DOGEUSDT,TRXUSDT,DOTUSDT,MATICUSDT,LTCUSDT,AVAXUSDT,LINKUSDT,ATOMUSDT,UNIUSDT,XMRUSDT,ETCUSDT,ICPUSDT,FILUSDT,APTUSDT,NEARUSDT,AAVEUSDT,ALGOUSDT,GRTUSDT,STXUSDT,QNTUSDT,CHZUSDT,VETUSDT,MANAUSDT,SANDUSDT,EGLDUSDT,THETAUSDT,XLMUSDT,AXSUSDT,EOSUSDT,FLOWUSDT,IMXUSDT,XTZUSDT,RUNEUSDT,CRVUSDT,KAVAUSDT,NEOUSDT,PAXGUSDT,SNXUSDT,GMXUSDT,MKRUSDT,FTMUSDT,BSVUSDT,KLAYUSDT,MINAUSDT,ZECUSDT,1INCHUSDT,COMPUSDT,XECUSDT,DASHUSDT,ENSUSDT,HNTUSDT,APEUSDT,GALAUSDT,BTGUSDT,WAVESUSDT,LDOUSDT,DYDXUSDT,ARUSDT,CVXUSDT,YFIUSDT,ZILUSDT,IOTXUSDT,QTUMUSDT,BATUSDT,RSRUSDT,OPUSDT,ROSEUSDT,SCUSDT,API3USDT,OCEANUSDT,CELOUSDT,ANKRUSDT,JASMYUSDT,ONEUSDT,FLMUSDT,RENUSDT,HOTUSDT,GLMRUSDT,SKLUSDT,STORJUSDT,ANTUSDT,CFXUSDT,DENTUSDT,PHBUSDT,TRBUSDT,MTLUSDT,TOMOUSDT,REEFUSDT,COTIUSDT,CHRUSDT,KSMUSDT,NKNUSDT"
coins_string_name = "BTC,ETH,BNB,XRP,ADA,SOL,DOGE,TRX,DOT,MATIC,LTC,AVAX,LINK,ATOM,UNI,XMR,ETC,ICP,FIL,APT,NEAR,AAVE,ALGO,GRT,STX,QNT,CHZ,VET,MANA,SAND,EGLD,THETA,XLM,AXS,EOS,FLOW,IMX,XTZ,RUNE,CRV,KAVA,NEO,PAXG,SNX,GMX,MKR,FTM,BSV,KLAY,MINA,ZEC,1INCH,COMP,XEC,DASH,ENS,HNT,APE,GALA,BTG,WAVES,LDO,DYDX,AR,CVX,YFI,ZIL,IOTX,QTUM,BAT,RSR,OP,ROSE,SC,API3,OCEAN,CELO,ANKR,JASMY,ONE,FLM,REN,HOT,GLMR,SKL,STORJ,ANT,CFX,DENT,PHB,TRB,MTL,TOMO,REEF,COTI,CHR,KSM,NKN"
coin_list_usdt = coins_string.split(",")
coin_list = coins_string_name.split(",")

MIN_PROFIT = 1.0  # Минимальная разница в % для арбитража
MIN_PROFIT_MAX = 8.0  # Минимальная разница в % для арбитража для канала с большими сделками
MIN_VOLUME = 200.0  # Минимальный объем сделки

MIN_DIFFERENT_PROFIT_FOR_CLOSE = 0.5

LIMIT_ORDER_BOOK = 100

opportunities = []

# ================= ФАНДИНГ-БОТ «СНАЙПЕР» (Bybit LONG / MEXC SHORT) =================
# Все ставки и доход считаются в «% в день» (24 ч), чтобы сравнивать биржи
# с разными интервалами начисления (1/2/4/8 ч).
FUNDING_NORMALIZE_HOURS = 24
# Минимальный доход связки по фандингу, % в день
FUNDING_MIN_DELTA = 0.5
# Как считать доход связки:
#   "net" — фандинг MEXC − фандинг Bybit (реальный доход: лонг на Bybit получает при
#           отрицательном фандинге, шорт на MEXC — при положительном). Если фандинг
#           «перевернулся» (на MEXC стал больше, чем на Bybit), доход уходит в минус.
#   "abs" — буквально |фандинг Bybit| − |фандинг MEXC|
FUNDING_DELTA_MODE = "net"
# Насколько можно зайти в минус по цене при входе, %
# (разница цен = (ask Bybit − bid MEXC) / bid MEXC * 100 должна быть не больше этого)
FUNDING_MAX_ENTRY_LOSS = 1.0
# Горизонт прогноза: связка должна приносить >= FUNDING_MIN_DELTA в день дольше этого срока
FUNDING_FORECAST_HOURS = 72
# Сколько часов за этот срок фандинг может быть «перевёрнут» (MEXC больше Bybit, доход < 0)
FUNDING_MAX_FLIP_HOURS = 8
# Сколько часов подряд суточный доход уже должен держаться >= порога на момент сигнала
FUNDING_MIN_HISTORY_HOURS = 8
# Минимальная вероятность от нейросети, что продержится дольше горизонта
FUNDING_MIN_PROBA = 0.6
# Если нейросеть ещё не обучена — сигнал, только если по истории уже держится столько часов
FUNDING_FALLBACK_HOURS = 72
# Сколько дней истории фандинга загружать для анализа и обучения
FUNDING_HISTORY_DAYS = 30
# Минимальный суточный оборот (USDT) на каждой бирже, чтобы отсечь неликвид
FUNDING_MIN_TURNOVER = 100_000
# Пауза между проверками (сек) и переобучением нейросети (сек)
FUNDING_SCAN_INTERVAL = 60
FUNDING_RETRAIN_INTERVAL = 6 * 3600
# Повторно слать ту же монету, если доход изменился на столько п.п. в день или прошло столько секунд
FUNDING_RESEND_DELTA = 0.2
FUNDING_RESEND_SECONDS = 4 * 3600
