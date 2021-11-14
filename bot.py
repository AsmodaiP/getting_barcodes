import telegram
import os
import sys
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
from telegram.ext import Updater 
from telegram.ext import CommandHandler
from create_stickers_and_db import create_stickers, set_status_collected_for_all_on_assembly


load_dotenv()

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
except KeyError as e:
    logging.error(e, exc_info=True)
    sys.exit('Не удалось получить переменные окружения')

bot = telegram.Bot(token=TELEGRAM_TOKEN)

whitelistid = (1617188356,1126541068, 482957060, 172902983)

def send_message(message):
    bot.send_message(CHAT_ID, message)

def send_results(id):
     bot.send_document(id,document=open('results.pdf', 'rb') )

def start(message, update):
    id = message['message']['chat']['id']
    if id in whitelistid:
        bot.send_message(id, 'Здравствуйте')

def get_results(message, update):
   id = message['message']['chat']['id']
   if id in whitelistid:
    send_results(id)

def create_stickers_by_bot(message, update):
    id = message['message']['chat']['id']
    if id in whitelistid:
        bot.send_message(id, 'Начато создание стикеров')
        create_stickers()
        bot.send_message(id, 'Стикеры созданы')
        send_results(id)

def set_status_collected_for_all_on_assembly_by_bot(message, update):
    id = message['message']['chat']['id']
    if id in whitelistid:
        set_status_collected_for_all_on_assembly()
        bot.send_message(id,'Все товары переведены в "Собрано"')


updater = Updater(token=TELEGRAM_TOKEN)

start_handler = CommandHandler('start', start)
updater.dispatcher.add_handler(start_handler)
get_results_handler = CommandHandler('get_results', get_results)
updater.dispatcher.add_handler(get_results_handler)
create_results_handler =  CommandHandler('create_stickers', create_stickers_by_bot)
updater.dispatcher.add_handler(create_results_handler)
updater.start_polling()