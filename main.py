# цены из стакана
# фандинг

import asyncio
import threading

# import requests
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, Message, BotCommand, InlineKeyboardMarkup
from aiogram import types

from cup import cache_clear
import dataApp
from getData import (
    get_coinex_futures_data, get_coinex_spot_data, get_gateio_spot_data, get_htx_futures_data, get_hyperliquid_data_futures, get_mexc_spot_data,
    get_gateio_futures_data, get_mexc_futures_data, get_okx_futures_data, get_okx_spot_data, get_spot_prices_bingx,
    get_futures_prices_with_real_price_bingx, get_spot_prices_bitget, get_futures_data_bitget, get_spot_prices_bybit,
    get_futures_data_bybit, get_binance_spot_data, get_binance_futures_data, get_htx_spot_data, get_xt_futures_data, get_xt_spot_data
)
from readFile import create_string_array_from_file, get_all_listed_symbols, is_listing_match, parse_listings_file_to_array
from scan import scan_arbitrage_opportunities_test, should_send, check_close_opportunities

TOKEN = "8023381531:AAGEyeO3xwoJHOSGbNsuTYrn72FUw94fwOE" # "7663512411:AAFOFh0uVn2_Kmmlr61i0gZuK0fJWHzxY80" # "7380819602:AAEdSde1Ub3uF-dxnKBfBWyOaJwBg-DCD3Y"
CHANNEL_ID = "-1003192536711" # "-1002467194406" # "-1002332428135"
CHANNEL_ID_MAX = "-1003205199934" #"-1003181826771"

CHANNEL_ID_CLOSE = "-1003299640737" # "-1002638487787"

LISTING_ID = "-1003224074615"
LISTING_MONET_ID = "-1003269912551"


CHANNEL_ID_FUTURES_STOT = "-1004415544476"


LISTING_ID_SENA = "-1003657279769"
CHANNEL_ID_MAX_SENA = "-1004437250336"
CHANNEL_ID_SENA = "-1003929442314"


bot = Bot(token=TOKEN)
dp = Dispatcher()

MIN_PROFIT = dataApp.MIN_PROFIT  # Минимальная разница в % для арбитража
MIN_VOLUME = dataApp.MIN_VOLUME  # Минимальный объем сделки

close_list = {}
pending_opp_list = {}
router = Router()
dp.include_router(router)

black_list_symbols = set()

# --- Начало вставки в main.py ---

# Объявление bot, channel_id и pending_opp_list должно быть ДО этой функции
# Но так как они уже объявлены в вашем файле, просто вставьте эту функцию
# где-нибудь вверху, например, сразу после импортов.

def format_opportunity_message(opp):
    """Форматирует сообщение об арбитражной возможности."""

    msg = (
        f"🔁 <b>{opp['type']}</b>\n"
        f"Монета: <b>{opp['symbol']}</b>\n"
        f"🟢 Купить ({opp['buy_type'].upper()} на {opp['buy_exchange']}): "
        f"<a href='{opp['buy_link']}'>${opp['buy_price']}</a>\n"
        f"🔴 Продать ({opp['sell_type'].upper()} на {opp['sell_exchange']}): "
        f"<a href='{opp['sell_link']}'>${opp['sell_price']}</a>\n"
        f"💰 Объём: {opp['volume']}\n"
        f"📈 Прибыль: <b>{opp['profit_percent']:.2f}%</b>"
    )
    if opp["buy_exchange"] == "Coinex" or opp["sell_exchange"] == "Coinex":
        print(msg)
    return msg

async def send_telegram_opportunity(opp):
    """
    Создает сообщение об арбитраже, добавляет его в pending_opp_list
    и отправляет в нужные Telegram-каналы.
    """
    # Импорты уже есть: from aiogram.utils.keyboard import InlineKeyboardBuilder
    # Глобальные переменные: bot, CHANNEL_ID, CHANNEL_ID_MAX, LISTING_ID, LISTING_MONET_ID, dataApp, pending_opp_list, black_list_symbols

    # Проверка черного списка
    my_drop_symbol = create_string_array_from_file()
    if opp["symbol"] in black_list_symbols or opp["symbol"] in my_drop_symbol:
        return

    # Проверка на повторную отправку
    if should_send(opp):
        msg = format_opportunity_message(opp)
        print(msg + "\n")

        # Добавление в список ожидающих закрытия
        symbol_data = f"{opp['symbol']} ({opp['buy_type'].upper()} на {opp['buy_exchange']}) ({opp['sell_type'].upper()} на {opp['sell_exchange']})"
        pending_opp_list[symbol_data] = opp

        # Проверяем длину callback_data
        # "details:" занимает 8 байт, остальное под данные
        callback_string = f"details:{symbol_data}"
        
        reply_markup = None
        # Проверяем длину в байтах (для UTF-8 символов это важно)
        if len(callback_string.encode('utf-8')) <= 64:
            builder = InlineKeyboardBuilder()
            builder.add(
                InlineKeyboardButton(
                    text="📊 Добавить в закрытие",
                    callback_data=callback_string
                )
            )
            reply_markup = builder.as_markup()
        else:
            print(f"⚠️ Кнопка не создана для {opp['symbol']}: слишком длинные данные ({len(callback_string.encode('utf-8'))} байт)")            


        

        if opp['buy_type'].lower() == "futures" and opp['sell_type'].lower() == "spot":
            await bot.send_message(CHANNEL_ID_FUTURES_STOT, msg, parse_mode="HTML")
            await asyncio.sleep(0.5) # Небольшая задержка перед следующими отправками
        else:
            # Отправка в основной канал
            await bot.send_message(CHANNEL_ID, msg, parse_mode="HTML", disable_web_page_preview=True,
                                reply_markup=reply_markup)
            await asyncio.sleep(0.5) # Небольшая задержка перед следующими отправками

            await bot.send_message(CHANNEL_ID_SENA, msg, parse_mode="HTML")
            await asyncio.sleep(0.5) # Небольшая задержка перед следующими отправками
            

            # Отправка в канал MAX
            if opp['profit_percent'] >= dataApp.MIN_PROFIT_MAX:
                await bot.send_message(CHANNEL_ID_MAX, msg, parse_mode="HTML", disable_web_page_preview=True,
                                    reply_markup=reply_markup)
                await asyncio.sleep(0.5)
                
                await bot.send_message(CHANNEL_ID_MAX_SENA, msg, parse_mode="HTML")
                await asyncio.sleep(0.5)

            # Отправка в канал ЛИСТИНГОВ (по файлу)
            parsed_listings = parse_listings_file_to_array()
            if is_listing_match(opp, parsed_listings):
                await bot.send_message(
                    LISTING_ID,
                    msg,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=reply_markup
                )
                await asyncio.sleep(0.5)
                
                await bot.send_message(
                    LISTING_ID_SENA,
                    msg,
                    parse_mode="HTML"
                )
                await asyncio.sleep(0.5)

            # Отправка в канал ЛИСТИНГОВ (по символу)
            all_listed_symbols = get_all_listed_symbols()
            if opp['symbol'] in all_listed_symbols:
                await bot.send_message(
                    LISTING_MONET_ID,
                    msg,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=reply_markup
                )
                await asyncio.sleep(0.5)

                await bot.send_message(
                    LISTING_ID_SENA,
                    msg,
                    parse_mode="HTML"
                )
                await asyncio.sleep(0.5)
            

        # Общая задержка после отправки всех сообщений.
        await asyncio.sleep(2) # Уменьшил с 3 до 2, так как уже были задержки 0.5

# --- Конец вставки в main.py ---

async def send_message(id_channel, msg):
    await bot.send_message(id_channel, msg, parse_mode="HTML", disable_web_page_preview=True)

async def safe_fetch(func, name):
    try:
        data = await asyncio.to_thread(func)
        if data is None:
            print(f"{name} вернул None")
            return {}
        return data
    except Exception as e:
        print(f"Ошибка получения {name}: {e}")
        return {}

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="add_black_list", description="Добавить монеты в черный список"),
        BotCommand(command="del_black_list", description="Удалить монеты из черного списка"),
        BotCommand(command="check_black_list", description="Показать список монет в черном сипске"),
    ]
    await bot.set_my_commands(commands)

async def send_arbitrage_opps():

    while True:

        try:

            print("Получение монет на рынке")

            tasks = {
                "mexc_spot": safe_fetch(get_mexc_spot_data, "mexc_spot"),
                "mexc_fut": safe_fetch(get_mexc_futures_data, "mexc_fut"),
                "gate_spot": safe_fetch(get_gateio_spot_data, "gate_spot"),
                "gate_fut": safe_fetch(get_gateio_futures_data, "gate_fut"),
                "bingx_spot": safe_fetch(get_spot_prices_bingx, "bingx_spot"),
                "bingx_fut": safe_fetch(get_futures_prices_with_real_price_bingx, "bingx_fut"),
                "bybit_spot": safe_fetch(get_spot_prices_bybit, "bybit_spot"),
                "bybit_fut": safe_fetch(get_futures_data_bybit, "bybit_fut"),
                "bitget_spot": safe_fetch(get_spot_prices_bitget, "bitget_spot"),
                "bitget_fut": safe_fetch(get_futures_data_bitget, "bitget_fut"),
                "binance_spot": safe_fetch(get_binance_spot_data, "binance_spot"),
                "binance_fut": safe_fetch(get_binance_futures_data, "binance_fut"),
                "hyperliquid_fut": safe_fetch(get_hyperliquid_data_futures, "hyperliquid_fut"),
                "xt_spot": safe_fetch(get_xt_spot_data, "xt_spot"),
                # "okx_spot": safe_fetch(get_okx_spot_data, "okx_spot"),
                # "okx_fut": safe_fetch(get_okx_futures_data, "okx_fut"),
                "htx_spot": safe_fetch(get_htx_spot_data, "htx_spot"),
                "htx_fut": safe_fetch(get_htx_futures_data, "htx_fut"),
                "coinex_spot": safe_fetch(get_coinex_spot_data, "coinex_spot"),
                "coinex_fut": safe_fetch(get_coinex_futures_data, "coinex_fut"),
            }

            results = await asyncio.gather(*tasks.values())

            data = dict(zip(tasks.keys(), results))

            print("Начало обработки партии данных")

            opportunities = await asyncio.to_thread(
                scan_arbitrage_opportunities_test,
                data["mexc_spot"], data["mexc_fut"],
                data["gate_spot"], data["gate_fut"],
                data["bingx_spot"], data["bingx_fut"],
                data["bybit_spot"], data["bybit_fut"],
                data["bitget_spot"], data["bitget_fut"],
                data["binance_spot"], data["binance_fut"],
                data["hyperliquid_fut"],
                data["htx_spot"], data["htx_fut"],
                data["xt_spot"],
                # data["okx_spot"], data["okx_fut"],
                data["coinex_spot"], data["coinex_fut"],
                min_diff_percent=MIN_PROFIT,
                min_usd_amount=MIN_VOLUME
            )

            print("Обработка окончена, данные отправляются!")

            if opportunities:
                for opp in opportunities:
                    await send_telegram_opportunity(opp)

        except Exception as e:
            print(f"Ошибка в send_arbitrage_opps: {e}")

        cache_clear()

        await asyncio.sleep(2)


# новый код
@router.callback_query(F.data.startswith("unclose:"))
async def process_callback_unclose(callback_query: types.CallbackQuery):
    await callback_query.answer()  # ✅ Обязательный отклик на нажатие кнопки

    symbol = callback_query.data.split(":")[1]
    print(symbol, f"-------------------{close_list.keys()}")
    if symbol in close_list:
        opp = close_list.pop(symbol)
        pending_opp_list[symbol] = opp
        await bot.send_message(
            CHANNEL_ID_CLOSE,
            "Удалён из закрытия.",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    elif symbol in pending_opp_list:
        await bot.send_message(
            CHANNEL_ID_CLOSE,
            f"{symbol} уже не находится в закрытии.",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    else:
        await bot.send_message(
            CHANNEL_ID_CLOSE,
            "Информация устарела или недоступна.",
            parse_mode="HTML",
            disable_web_page_preview=True
        )


@router.callback_query(F.data.startswith("details:"))
async def process_callback_details(callback_query: types.CallbackQuery):
    await callback_query.answer()  # ✅ Обязательный отклик на нажатие кнопки

    symbol = callback_query.data.split(":")[1]


    if symbol in pending_opp_list:
        opp = pending_opp_list.pop(symbol)
        close_list[symbol] = opp
        await bot.send_message(
            CHANNEL_ID,
            "Добавлен в закрытие.",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    elif symbol in close_list:
        await bot.send_message(
            CHANNEL_ID,
            f"{symbol} уже добавлен.",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    else:
        await bot.send_message(
            CHANNEL_ID,
            "Информация устарела или недоступна.",
            parse_mode="HTML",
            disable_web_page_preview=True
        )


# Отправка закрытых сделок — БЕСКОНЕЧНЫЙ ФОН
async def send_closed_opps():
    while True:
        try:


            if close_list:
                closed_opps = await asyncio.to_thread(check_close_opportunities, close_list)
                for opp in closed_opps:
                    msg = (
                        f"🔁 <b>{opp['type']}</b>\n"
                        f"Монета: <b>{opp['symbol']}</b>\n"
                        f"🟢 Купить -> теперь продать ({opp['buy_type'].upper()} на {opp['buy_exchange']}): "
                        f"<a href='{opp['buy_link']}'>${opp['buy_price']}</a>\n"
                        f"🔴 Продать -> теперь купить ({opp['sell_type'].upper()} на {opp['sell_exchange']}): "
                        f"<a href='{opp['sell_link']}'>${opp['sell_price']}</a>\n"
                        f"💰 Объём: {opp['volume']}\n"
                        f"📈 Прибыль: <b>{opp['profit_percent']:.2f}%</b>"
                    )
                    # await bot.send_message(CHANNEL_ID_CLOSE, msg, parse_mode="HTML", disable_web_page_preview=True)
                    # новый код
                    # Создание клавиатуры с кнопкой "Удалить из закрытия"
                    symbol_data = f"{opp['symbol']} ({opp['buy_type'].upper()} на {opp['buy_exchange']}) ({opp['sell_type'].upper()} на {opp['sell_exchange']})"
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="❌ Удалить из закрытия",
                                    callback_data=f"unclose:{symbol_data}"
                                )
                            ]
                        ]
                    )

                    await bot.send_message(
                        CHANNEL_ID_CLOSE,
                        msg,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )

            await asyncio.sleep(5)  # немного отдыха между итерациями
        except Exception as e:
            print(f"Ошибка в send_closed_opps: {e}")
            await asyncio.sleep(5)


# async def periodic_check_close_opportunities():
#     while True:
#         closed_opps = check_close_opportunities(close_list)
#         for opp in closed_opps:
#             msg = (
#                 f"🔁 <b>{opp['type']}</b>\n"
#                 f"Монета: <b>{opp['symbol']}</b>\n"
#                 f"🟢 Купить ({opp['buy_type'].upper()} на {opp['buy_exchange']}): "
#                 f"<a href='{opp['buy_link']}'>${opp['buy_price']}</a>\n"
#                 f"🔴 Продать ({opp['sell_type'].upper()} на {opp['sell_exchange']}): "
#                 f"<a href='{opp['sell_link']}'>${opp['sell_price']}</a>\n"
#                 f"💰 Объём: {opp['volume']}\n"
#                 f"📈 Прибыль: <b>{opp['profit_percent']:.2f}%</b>"
#             )
#             await bot.send_message(CHANNEL_ID_CLOSE, msg, parse_mode="HTML",
#                                    disable_web_page_preview=True)
#         await asyncio.sleep(1)  # Проверять каждые 1 секунду


# # команды для обработки
# @router.message(Command("add_black_list"))
# async def black_list_add(message: Message):
#     text = message.text or ""
#     coins = [c.strip().upper() for c in text.replace("/add_black_list", "").split(",") if c.strip()]
#
#     if not coins:
#         await message.answer("❗ Укажи хотя бы одну монету для добавления.\nПример: /add_black_list BNB, TRAMP")
#         return
#
#     added = []
#     for coin in coins:
#         if coin not in black_list_symbols:
#             black_list_symbols.add(coin)
#             added.append(coin)
#
#     if added:
#         await message.answer(f"✅ Добавлены в черный список: {', '.join(added)}")
#     else:
#         await message.answer("⚠️ Все указанные монеты уже были в черном списке.")
#
#     await message.answer('Текущий черный список: ' + ', '.join(sorted(black_list_symbols)))
#
#
# @router.message(Command("del_black_list"))
# async def black_list_del(message: Message):
#     text = message.text or ""
#     coins = [c.strip().upper() for c in text.replace("/del_black_list", "").split(",") if c.strip()]
#
#     if not coins:
#         await message.answer("❗ Укажи хотя бы одну монету для удаления.\nПример: /del_black_list BNB, TRAMP")
#         return
#
#     removed = []
#     for coin in coins:
#         if coin in black_list_symbols:
#             black_list_symbols.remove(coin)
#             removed.append(coin)
#
#     if removed:
#         await message.answer(f"🗑 Удалены из черного списка: {', '.join(removed)}")
#     else:
#         await message.answer("⚠️ Ни одна из указанных монет не найдена в черном списке.")
#
#     await message.answer('Текущий черный список: ' + ', '.join(sorted(black_list_symbols)))
#
#
# @router.message(Command("check_black_list"))
# async def black_list_check(message: Message):
#     if black_list_symbols:
#         await message.answer('Черный список: ' + ', '.join(sorted(black_list_symbols)))
#     else:
#         await message.answer('Черный список пуст.')

async def main():
    await set_commands(bot)
    await bot.delete_webhook(drop_pending_updates=True)

    loop = asyncio.get_event_loop()

    # Запускаем фоновые задачи
    loop.create_task(send_arbitrage_opps())
    loop.create_task(send_closed_opps())

    # Запускаем основной polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())




