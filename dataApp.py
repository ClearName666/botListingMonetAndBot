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

# ================= ФАНДИНГ-БОТ (Bybit LONG / MEXC SHORT) =================
# Минимальная дельта фандинга, % (0.2 = 0.2%)
FUNDING_MIN_DELTA = 0.2
# Как считать дельту:
#   "net" — реальный доход связки: фандинг MEXC − фандинг Bybit
#           (лонг на Bybit получает, когда фандинг там отрицательный; шорт на MEXC
#            получает, когда фандинг там положительный). При отрицательном фандинге
#            на обеих биржах это ровно |Bybit| − |MEXC|.
#   "abs" — буквально |фандинг Bybit| − |фандинг MEXC| (без учёта знака)
FUNDING_DELTA_MODE = "net"
# Приводить ставки к одному периоду (часов). У бирж разные интервалы начисления
# (1/2/4/8 ч), без приведения сравнивать ставки нельзя. None — сравнивать как есть.
FUNDING_NORMALIZE_HOURS = 8
# Сколько часов подряд по истории дельта должна была держаться выше порога
FUNDING_MIN_HISTORY_HOURS = 8
# Горизонт прогноза нейросети: "продержится ли дельта ещё N часов"
FUNDING_FORECAST_HOURS = 24
# Минимальная вероятность от нейросети, чтобы считать, что фандинг продержится долго
FUNDING_MIN_PROBA = 0.6
# Если нейросеть ещё не обучена — считаем «долго», если по истории держится столько часов
FUNDING_FALLBACK_HOURS = 24
# Минимальный суточный оборот (USDT) на каждой бирже, чтобы отсечь неликвид
FUNDING_MIN_TURNOVER = 100_000
# Пауза между проверками (сек) и переобучением нейросети (сек)
FUNDING_SCAN_INTERVAL = 60
FUNDING_RETRAIN_INTERVAL = 6 * 3600
# Повторно слать ту же монету, если дельта изменилась на столько п.п. или прошло столько секунд
FUNDING_RESEND_DELTA = 0.1
FUNDING_RESEND_SECONDS = 4 * 3600
