import re
import telegram
import os
import sys
import datetime
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
from telegram.ext import Updater
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
import create_stickers_and_db
from create_stickers_and_db import create_path_if_not_exist, create_stickers, set_status_collected_for_all_on_assembly, get_list_of_relative_path_to_all_today_results, get_list_of_relative_path_to_all_logs, NAME
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton
from fbs import update_table

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(BASE_DIR, 'bot.log')

console_handler = logging.StreamHandler()
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=100000,
    backupCount=3,
    encoding='utf-8'
)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(message)s',
    handlers=(
        file_handler,
        console_handler
    )
)
try:
    TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
    CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
    ID_FOR_NOTIFICATION = os.getenv('ID_FOR_NOTIFICATION', 295481377)
except KeyError as e:
    logging.error(e, exc_info=True)
    sys.exit('Не удалось получить переменные окружения')



bot = telegram.Bot(token=TELEGRAM_TOKEN)

whitelistid = (1617188356, 1126541068, 482957060, 172902983)



def send_message(message):
    bot.send_message(CHAT_ID, message)


def send_results(id):
    bot.send_document(id, document=open('results.pdf', 'rb'))


def start(message, update):
    id = message['message']['chat']['id']
    if id in whitelistid:
        bot.send_message(id, 'Здравствуйте', parse_mode="Markdown")


def get_results(message, update):
    id = message['message']['chat']['id']
    if id in whitelistid:
        send_results(id)

def send_db(id):
    bot.send_document(id, document=open('db.xlsx', 'rb'))

def create_stickers_by_bot(message, update):

    id = message['message']['chat']['id']
    if id in whitelistid:
        bot.send_message(id, 'Начато создание стикеров')
        count_of_orders, barcodes = create_stickers()
        if count_of_orders == 0:
            bot.send_message(id, 'На сборке 0 заказов, создавать нечего')
            return 0
        bot.send_message(id, f'Стикеры созданы, количество {count_of_orders}')
        send_results(id)
        create_stickers_and_db.create_db_for_checking(barcodes)
        send_db(id)
        bot.send_message(ID_FOR_NOTIFICATION, f'Пользователь [{id}](tg://user?id={id}) получил стикеры, {count_of_orders}', parse_mode = 'Markdown')
        send_results(ID_FOR_NOTIFICATION)
        send_db(ID_FOR_NOTIFICATION)



def set_status_collected_for_all_on_assembly_by_bot(message, update):
    id = message['message']['chat']['id']
    if id in whitelistid:
        set_status_collected_for_all_on_assembly()
        bot.send_message(id, 'Все товары переведены в "Собрано"')


def send_all_today_results(id):
    results = get_list_of_relative_path_to_all_today_results()
    if len(results) == 0:
        bot.send_message(id,'Сегодня стикеры еще не создавались')
        return 0
    for result in results:
        bot.send_document(id, document=open(result, 'rb'))


def get_all_today_results(message, update):
    id = message['message']['chat']['id']
    if id in whitelistid:
        send_all_today_results(id)

def send_all_logs(id):
    logs = get_list_of_relative_path_to_all_logs()
    for log in logs: 
        bot.send_document(id,document=open(log, 'rb'))

def get_logs(message, update):
    id = message['message']['chat']['id']
    if id in whitelistid:
        send_all_logs(id)

def send_finall_db(message, update):
    id = message['message']['chat']['id']
    if id in whitelistid:
        list_of_json = create_stickers_and_db.get_list_of_relative_path_to_all_today_json()
        if list_of_json == []:
            bot.send_message(id, 'Сегодня стикеры через бота не получались')
            return 0
        file = create_stickers_and_db.create_finall_table_of_day()
        bot.send_document(id, document=open(file, 'rb'))

def put_all_on_collected(message, update):
    id = message['message']['chat']['id']
    if id in whitelistid:
        orders_count = create_stickers_and_db.set_status_collected_for_all_on_assembly()
        if orders_count == 0:
            bot.send_message(id, 'На сборке ноль заказов, переводить в собранные нечего')
        bot.send_message(id, f'{orders_count} заказов переведено в собранные')
        bot.send_message(ID_FOR_NOTIFICATION, f'Пользователь [{id}](tg://user?id={id}) перевел в собранные {orders_count} заказов', parse_mode = 'Markdown')

def force_update_table(message, update):
    id = message['message']['chat']['id']
    if id in whitelistid:
        result = update_table()
        bot.send_message(ID_FOR_NOTIFICATION, result)
        bot.send_message(id, result)

updater = Updater(token=TELEGRAM_TOKEN)

start_handler = CommandHandler('start', start)
updater.dispatcher.add_handler(start_handler)

get_results_handler = CommandHandler('get_results', get_results)
updater.dispatcher.add_handler(get_results_handler)

put_all_on_collected_handler = CommandHandler('put_all_on_collected', put_all_on_collected)
updater.dispatcher.add_handler(put_all_on_collected_handler)

force_update_table_handler = CommandHandler('update_table', force_update_table)
updater.dispatcher.add_handler(force_update_table_handler)

get_all_today_results_handler = CommandHandler(
    'get_all_today_results', get_all_today_results)
updater.dispatcher.add_handler(get_all_today_results_handler)

get_logs_handler = CommandHandler('get_logs', get_logs)
updater.dispatcher.add_handler(get_logs_handler)

create_results_handler = CommandHandler(
    'create_stickers', create_stickers_by_bot)
updater.dispatcher.add_handler(create_results_handler)
get_finall_db_handler = CommandHandler(
    'get_finall_db', send_finall_db)
updater.dispatcher.add_handler(get_finall_db_handler)

updater.start_polling()
