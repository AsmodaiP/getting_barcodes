import re
from reportlab.lib.utils import CIDict, prev_this_next
from requests.api import get
import telegram
import telebot
import os
import sys
import datetime
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
from telegram.ext import Updater, messagehandler
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler
import create_stickers_and_db
from create_stickers_and_db import create_path_if_not_exist, create_stickers, get_all_orders, set_status_collected_for_all_on_assembly, get_list_of_relative_path_to_all_today_results, get_list_of_relative_path_to_all_logs, NAME, set_status_to_orders
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Filters
from fbs import update_table
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(BASE_DIR, 'bot.log')

DEFAULT_CLIENT = 'БелотеловАГ'

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
    ID_FOR_NOTIFICATION = os.getenv('ID_FOR_NOTIFICATION', [295481377]).split(',')
except KeyError as e:
    logging.error(e, exc_info=True)
    sys.exit('Не удалось получить переменные окружения')

USERS = json.load(open('users_and_client.json', 'rb'))


bot = telegram.Bot(token=TELEGRAM_TOKEN)
bot_1= telegram.Bot(token=TELEGRAM_TOKEN)

TEXT_TO_PUT_ON_COLLECTED = '❌❌Перевести всё в собранное❌❌'
TEXT_TO_PUT_ON_ASSEMBLY_BY_ARTICLE = 'На сборку по артикулу'
TEXT_TO_PUT_ON_ASSEMBLY_BY_COUNT = 'На сборку по количеству'
TEXT_TO_CREATE_STICKERS = 'Создать стикеры'
TEXT_UPDATE_TABLE = 'Обновить таблицу'
TEXT_STATS = 'Статистика'
TEXT_TOP = 'Топ артикулов по количеству'
TEXT_SWAP_CLIENT = 'Сменить аккаунт'

whitelistid = (1617188356, 1126541068, 482957060, 172902983)

def send_notification(text):
    for id in ID_FOR_NOTIFICATION:
        bot.send_message(id, text, parse_mode = 'Markdown')

def send_message(message):
    bot.send_message(CHAT_ID, message)


def send_results(id):
    bot.send_document(id, document=open('results.pdf', 'rb'))


def start(update, _):
    # user = update.message.from_user
    main_menu_keyboard = (
        [KeyboardButton(TEXT_TO_CREATE_STICKERS), KeyboardButton(TEXT_TOP)],
        [KeyboardButton(TEXT_TO_PUT_ON_ASSEMBLY_BY_COUNT),KeyboardButton(TEXT_SWAP_CLIENT), KeyboardButton(TEXT_TO_PUT_ON_ASSEMBLY_BY_ARTICLE)],
        [KeyboardButton(TEXT_TO_PUT_ON_COLLECTED)],
        [KeyboardButton(TEXT_UPDATE_TABLE), KeyboardButton(TEXT_STATS)]
    )
    reply_kb_markup = ReplyKeyboardMarkup(main_menu_keyboard,
                                                   resize_keyboard=True,
                                                   one_time_keyboard=False)
    bot.send_message(chat_id=update.message.chat_id,
                     text='Выберите действие',
                     reply_markup=reply_kb_markup)

def test(message, update):
    id = message['message']['chat']['id']
    if update.args:
        orders = create_stickers_and_db.filter_orders_by_article(update.args)
        bot.send_message(id, orders)

def get_results(message, update):
    id = message['message']['chat']['id']
    if id in whitelistid:
        send_results(id)

def send_db(id):
    bot.send_document(id, document=open('db.xlsx', 'rb'))

def create_stickers_by_bot(message, update):
    # USERS = json.load(open('users_and_client.json', 'rb'))
    id = message['message']['chat']['id']
    if id in whitelistid:
        # try:
        #     client = USERS[str(id)]['client']
        # except:
        #     client= 'БелотеловАГ'
        # create_stickers_and_db.swap_token_by_name(client)
        bot.send_message(id, 'Начато создание стикеров')
        count_of_orders, barcodes = create_stickers()
        if count_of_orders == 0:
            bot.send_message(id, 'На сборке 0 заказов, создавать нечего')
            return 0
        bot.send_message(id, f'Стикеры созданы, количество {count_of_orders}')
        send_results(id)
        create_stickers_and_db.create_db_for_checking(barcodes)
        send_db(id)
        send_notification(f'Пользователь [{id}](tg://user?id={id}) получил стикеры, {count_of_orders}')
        for id_for_not in ID_FOR_NOTIFICATION:
            send_results(id_for_not)
            send_db(id_for_not)

def get_top_of_articles(message,update):
    id = message['message']['chat']['id']
    if id not in whitelistid:
        return 0
    msg=''
    bot.send_message(id, 'Идет формирование топа')
    try:
        barcodes = create_stickers_and_db.get_barcodes_with_full_info(get_all_orders(0))
        for barcode in barcodes.keys():
            msg += f'{barcodes[barcode]["info"]["article"]} {barcodes[barcode]["info"]["count"]} \n'
        bot.send_message(id,msg[:4096])
    except Exception as e:
        logging.error('Ошибка при получение топа', exc_info=e)
        bot.send_message(id,'Что-то пошло не так, попробуйте еще раз')

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
            return 0
        bot.send_message(id, f'{orders_count} заказов переведено в собранные')
        send_notification(f'Пользователь [{id}](tg://user?id={id}) перевел в собранные {orders_count} заказов')

def force_update_table(message, update):
    id = message['message']['chat']['id']
    if id in whitelistid:
        result_and_errors = update_table()
        result = result_and_errors['result']
        errors = result_and_errors['erors']
        str_errors = '\n'.join(errors)
        if result != '':
            send_notification(result)
            if len(errors)>0:
                send_notification(f'Что-то не так с артикулами \n{str_errors}')
            bot.send_message(id, result)



updater = Updater(token=TELEGRAM_TOKEN)

def set_on_assembly_by_article(bot, update):
    id = bot['message']['chat']['id']
    if not id in whitelistid:
        return 0
    update.user_data['count'] = bot.message.text.strip()
    try:
        count = int(update.user_data['count'])
    except:
        bot.message.reply_text('Неверный формат числа, начните всё с начала')
        return ConversationHandler.END
    articles = update.user_data['articles']
    orders  = create_stickers_and_db.filter_orders_by_article(articles,count)
    create_stickers_and_db.set_status_to_orders_by_ids(1,orders)
    orders_count = len(orders)

    if orders_count == 0:
        bot.message.reply_text('Таких артикулов нет в новых')
        return ConversationHandler.END
    bot.message.reply_text(f'{orders_count} переведено на сборку')
    send_notification(f'Пользователь [{id}](tg://user?id={id}) перевел  на сборку {orders_count} заказов')
    return ConversationHandler.END


def get_articles_from_user(bot, update):
    id = bot['message']['chat']['id']
    if not id  in whitelistid:
        return ConversationHandler.END
    bot.message.reply_text('Введите нужные артикулы через пробел, для отмены введите /cancel')
    return 'count'

def get_count_from_user(bot, update):
    id = bot['message']['chat']['id']
    if not id in whitelistid:
        return ConversationHandler.END
    update.user_data['articles'] = bot.message.text.upper().split()
    bot.message.reply_text('Введите масимальное число заказов для перевода, для отмены введите /cancel')
    return 'set_on_assembly'

def start_c(bot,update):
    return 'article'

def cancel(bot, update):
    bot.message.reply_text('Операция отменена')
    return ConversationHandler.END

def set_on_assembly_by_count(bot,update):
    id = bot['message']['chat']['id']
    if not id in whitelistid:
        return ConversationHandler.END
    update.user_data['count'] = bot.message.text.strip()
    
    try:
        count = int(update.user_data['count'])
    except:
        bot.message.reply_text('Неверный формат числа')
        return ConversationHandler.END
    orders = create_stickers_and_db.get_all_orders(status=0)[:count]
    # orders_ids = [order['orderId'] for order in orders ]
    create_stickers_and_db.set_status_to_orders(1,orders)
    bot.message.reply_text(f'{len(orders)} передано на сборку')
    return ConversationHandler.END

t= CommandHandler('test', test)
updater.dispatcher.add_handler(t)

set_on_assembly_by_article_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.text([TEXT_TO_PUT_ON_ASSEMBLY_BY_ARTICLE]), get_articles_from_user)],
    states ={
         'article' : [MessageHandler(Filters.text & ~Filters.command, get_articles_from_user)],
         'count': [MessageHandler(Filters.text & ~Filters.command, get_count_from_user)],
         'set_on_assembly':[MessageHandler(Filters.text, set_on_assembly_by_article)]
         },
    fallbacks=[CommandHandler('cancel', cancel)])

updater.dispatcher.add_handler(set_on_assembly_by_article_handler)

set_on_assembly_by_count_handler =ConversationHandler(
    entry_points= [MessageHandler(Filters.text(TEXT_TO_PUT_ON_ASSEMBLY_BY_COUNT), get_count_from_user )],
    states= {
        'set_on_assembly': [MessageHandler(Filters.text & ~Filters.command, set_on_assembly_by_count)]
    },
    fallbacks=[CommandHandler('cancel', cancel)])

def get_stats(bot, update):
    id = bot['message']['chat']['id']
    if not id in whitelistid:
        return ConversationHandler.END
    new_orders = get_all_orders(status=0)
    count_new = (len(new_orders))
    _ , count_order_without_address  = create_stickers_and_db.check_and_delete_orders_with_blank_officeAddress(new_orders)
    
    orders_on_assembly = len(get_all_orders(status=1))
    bot.message.reply_text(f'{count_new} — новых, из них без адреса — {count_order_without_address} \n{orders_on_assembly} — на сборке \n ')

def get_client_from_user(bot, update):
    cred = json.load(open('credentials.json', 'rb'))
    names = '\n'.join(cred)
    bot.message.reply_text(f'Текущий аккаунт {create_stickers_and_db.get_name()}\n\nВарианты выбора \nВыберете один и отправьте его в чат \n{names}')
    return 'get_client_from_user'

def swap_by_client_from_user(bot, update):
    try:
        client = bot.message.text.strip()
        if client in json.load(open('credentials.json', 'rb')):
            create_stickers_and_db.swap_token_by_name(client)
            bot.message.reply_text(f'Переключение на аккаунт «{client}» прошло успешно')
        else:
            bot.message.reply_text(f'Такого аккаунта не существует')
    except:
        bot.message.reply_text(f'Что-то пошло не так, попробуйте еще раз, проверив данные')
    return ConversationHandler.END

    
swap_client_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.text(TEXT_SWAP_CLIENT), get_client_from_user)],
    states={
        'get_client_from_user':  [MessageHandler(Filters.text & ~Filters.command, swap_by_client_from_user)]
    },
    fallbacks=[CommandHandler('cancel', cancel)])

def swap_client_in_json_by_bot(bot, update):
    id = bot['message']['chat']['id']
    client = bot.message.text.strip()
    swap_or_create_client_in_json(id, client)

def swap_or_create_client_in_json(id,  client):
    db = json.load(open('users_and_client.json', 'rb'))
    if client in json.load(open('credentials.json', 'rb')):
        db[id]=client
        with open('users_and_client.json','w', encoding='utf-8') as f:
            json.dump(db, f,ensure_ascii=False)

def get_client_info_by_telegram_id(id):
    db = json.load(open('users_and_client.json', 'rb'))
    if str(id) not in db:
        swap_or_create_client_in_json(id, DEFAULT_CLIENT)
    client = db[str(id)]['client']
    client_db = json.load(open('credentials.json', 'rb'))
    return client_db[client]

print(get_client_info_by_telegram_id(22))

updater.dispatcher.add_handler(swap_client_handler)


updater.dispatcher.add_handler(set_on_assembly_by_count_handler)
create_stickers_menu_handler = MessageHandler(Filters.text([TEXT_TO_CREATE_STICKERS]), create_stickers_by_bot)
updater.dispatcher.add_handler(create_stickers_menu_handler)

get_top_of_articles_handler = MessageHandler(Filters.text([TEXT_TOP]), get_top_of_articles)
updater.dispatcher.add_handler(get_top_of_articles_handler)

put_all_on_collected_menu_handler =MessageHandler(Filters.text([TEXT_TO_PUT_ON_COLLECTED]), put_all_on_collected)
updater.dispatcher.add_handler(put_all_on_collected_menu_handler)

update_table_menu_handler = MessageHandler(Filters.text([TEXT_UPDATE_TABLE]),force_update_table)
updater.dispatcher.add_handler(update_table_menu_handler)

get_stats_handler = MessageHandler(Filters.text(['Статистика']), get_stats)
updater.dispatcher.add_handler(get_stats_handler)

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
