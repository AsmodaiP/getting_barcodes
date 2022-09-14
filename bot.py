from datetime import datetime
import telegram
import os
import sys
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
from telegram.ext import Updater, CommandHandler, MessageHandler, ConversationHandler
import create_stickers_and_db
from create_stickers_and_db import create_stickers, get_all_orders, set_status_collected_for_all_on_assembly, get_list_of_relative_path_to_all_today_results, get_list_of_relative_path_to_all_logs, NAME, set_status_to_orders
from telegram import KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Filters
from fbs import update_table
import json
import marketplace
import codecs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(BASE_DIR, 'bot.log')

DEFAULT_CLIENT = 'Белотелов'

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
    ID_FOR_NOTIFICATION = os.getenv(
        'ID_FOR_NOTIFICATION', [295481377]).split(',')
except KeyError as e:
    logging.error(e, exc_info=True)
    sys.exit('Не удалось получить переменные окружения')

USERS = json.load(open('users_and_client.json', 'rb'))


bot = telegram.Bot(token=TELEGRAM_TOKEN)
bot_1 = telegram.Bot(token=TELEGRAM_TOKEN)

TEXT_TO_PUT_ON_COLLECTED = '❌❌Перевести всё в собранное❌❌'
TEXT_TO_PUT_ON_ASSEMBLY_BY_ARTICLE = 'На сборку по артикулу'
TEXT_TO_PUT_ON_ASSEMBLY_BY_COUNT = 'На сборку по количеству'
TEXT_TO_CREATE_STICKERS = 'Создать стикеры'
TEXT_UPDATE_TABLE = 'Обновить таблицу'
TEXT_STATS = 'Статистика'
TEXT_TOP = 'Топ артикулов по количеству'
TEXT_SWAP_CLIENT = 'Сменить аккаунт'
TEXT_CLOSE_SUPPLIE = 'Закрыть текущую поставку'
TEXT_GET_STICK_OF_SUPPLIE = 'Штрихкод поставки'
TEXT_GET_CURRENT_SUPPLIE = 'Текущая поставка/Создать новую'
TEXT_ADD_ORDERS_TO_SUPPLIE = 'Добавить заказы к текущей поставке'

ADD_CLIENT = 'Добавить клиента'

INSTRUCTION = 'Инструкция'

CATEGORY_SUPLLIES = 'Поставки'
CATEGORY_ON_ASSEMBLY = 'Перевести на сборку'
CATEGORY_MAIN_MENU = 'В главное меню'

ON_ASSEMBLY_KEYBOARD = (
    [KeyboardButton(TEXT_TO_PUT_ON_ASSEMBLY_BY_COUNT),
     KeyboardButton(TEXT_TO_PUT_ON_ASSEMBLY_BY_ARTICLE)],
    [KeyboardButton(TEXT_TOP)],
    [KeyboardButton(CATEGORY_MAIN_MENU)]
)

SUPPLIES_KEYBOARD = (
    [KeyboardButton(TEXT_GET_CURRENT_SUPPLIE),
     KeyboardButton(TEXT_GET_STICK_OF_SUPPLIE)],
    [KeyboardButton(TEXT_ADD_ORDERS_TO_SUPPLIE)],
    [KeyboardButton(TEXT_CLOSE_SUPPLIE)],
    [KeyboardButton(CATEGORY_MAIN_MENU)]
)
MAIN_MENU_CATEGORY = (
    [KeyboardButton(TEXT_TO_CREATE_STICKERS), KeyboardButton(TEXT_SWAP_CLIENT)],

    [KeyboardButton(CATEGORY_ON_ASSEMBLY),
     KeyboardButton(CATEGORY_SUPLLIES), ],
    [KeyboardButton(TEXT_STATS), KeyboardButton(INSTRUCTION)],
    [KeyboardButton(ADD_CLIENT)]
)

MAIN_MENU = (
    [KeyboardButton(TEXT_TO_CREATE_STICKERS), KeyboardButton(TEXT_TOP)],
    [KeyboardButton(TEXT_CLOSE_SUPPLIE), KeyboardButton(
        TEXT_ADD_ORDERS_TO_SUPPLIE)],
    [KeyboardButton(TEXT_TO_PUT_ON_ASSEMBLY_BY_COUNT), KeyboardButton(
        TEXT_SWAP_CLIENT), KeyboardButton(TEXT_TO_PUT_ON_ASSEMBLY_BY_ARTICLE)],
    [KeyboardButton(TEXT_GET_STICK_OF_SUPPLIE),
     KeyboardButton(TEXT_GET_CURRENT_SUPPLIE)],
    [KeyboardButton(TEXT_STATS)]
)
MAIN_MENU_MARKUP = ReplyKeyboardMarkup(
    MAIN_MENU,
    resize_keyboard=True,
    one_time_keyboard=False)

whitelistid = (1617188356, 1126541068, 482957060, 172902983)

def send_instruction(bot, update):
    bot.message.reply_text(codecs.open('instruction.md', 'r').read(), parse_mode='Markdown')

def send_notification(text):
    for id in ID_FOR_NOTIFICATION:
        bot.send_message(id, text, parse_mode='Markdown')


def send_notification_document(document):
    for id in ID_FOR_NOTIFICATION:
        bot.send_document(id, open(document))


def send_message(message):
    bot.send_message(CHAT_ID, message)


def send_results(id):
    bot.send_document(id, document=open('results.pdf', 'rb'))


def supplies_keyboard(bot, update):
    supplies_markup = ReplyKeyboardMarkup(
        SUPPLIES_KEYBOARD,
        resize_keyboard=True,
        one_time_keyboard=False)
    bot.message.reply_text(f'Выберете действие', reply_markup=supplies_markup)


def assembly_keyboard(bot, update):
    assembly_markup = ReplyKeyboardMarkup(
        ON_ASSEMBLY_KEYBOARD,
        resize_keyboard=True,
        one_time_keyboard=False)
    bot.message.reply_text(f'Выберете действие', reply_markup=assembly_markup)


def main_meny_category(bot, update):
    meny_markup = ReplyKeyboardMarkup(
        ON_ASSEMBLY_KEYBOARD,
        resize_keyboard=True,
        one_time_keyboard=False)
    bot.message.reply_text(f'Выберете действие', reply_markup=meny_markup)


def main_menu(bot, update):
    meny_markup = ReplyKeyboardMarkup(
        MAIN_MENU_CATEGORY,
        resize_keyboard=True,
        one_time_keyboard=False)
    bot.message.reply_text(f'Выберете действие', reply_markup=meny_markup)


def get_results(message, update):
    id = message['message']['chat']['id']
    if True:
        send_results(id)


def send_db(id):
    bot.send_document(id, document=open('db.xlsx', 'rb'))


def update_table_and_send_notification():
    result_and_errors = update_table()
    result = result_and_errors['result']
    errors = result_and_errors['erors']
    str_errors = '\n'.join(errors)
    if result != '':
        if len(errors) > 0:
            send_notification(f'Что-то не так с артикулами \n{str_errors}')


def create_stickers_by_bot(message, update):
    id = message['message']['chat']['id']
    if True:
        bot.send_message(id, 'Начато создание стикеров')
        count_of_orders, barcodes = create_stickers()
        if count_of_orders == 0:
            bot.send_message(id, 'На сборке 0 заказов, создавать нечего')
            main_menu(message, update)
            return 0
        bot.send_message(id, f'Стикеры созданы, количество {count_of_orders}')
        send_results(id)

        succsess = False
        while not succsess:
            count_of_try = 0
            try:
                create_stickers_and_db.create_db_for_checking(barcodes)
                send_db(id)
                succsess = True
            except Exception:
                count_of_try += 1
                if count_of_try > 4:
                    break
        send_notification(
            f'Пользователь [{id}](tg://user?id={id}) получил стикеры, {count_of_orders}')
        for id_for_not in ID_FOR_NOTIFICATION:
            send_results(id_for_not)
            send_db(id_for_not)
    main_menu(message, update)


def get_top_of_articles(message, update):
    id = message['message']['chat']['id']
    # if id not in whitelistid:
    #     return 0
    msg = ''
    bot.send_message(id, 'Идет формирование топа')
    try:
        barcodes = create_stickers_and_db.get_barcodes_with_full_info(
            get_all_orders(0))
        if barcodes == {}:
            return bot.send_message(id, 'Новых заказов нет')

        for barcode in barcodes.keys():
            msg += f'{barcodes[barcode]["info"]["article"]} {barcodes[barcode]["info"]["count"]} \n'
        bot.send_message(id, msg[:4096])
    except Exception as e:
        logging.error('Ошибка при получение топа', exc_info=e)
        bot.send_message(id, 'Что-то пошло не так, попробуйте еще раз')


def set_status_collected_for_all_on_assembly_by_bot(message, update):
    id = message['message']['chat']['id']
    if True:
        set_status_collected_for_all_on_assembly()
        bot.send_message(id, 'Все товары переведены в "Собрано"')


def send_all_today_results(id):
    results = get_list_of_relative_path_to_all_today_results()
    if len(results) == 0:
        bot.send_message(id, 'Сегодня стикеры еще не создавались')
        return 0
    for result in results:
        bot.send_document(id, document=open(result, 'rb'))


def get_all_today_results(message, update):
    id = message['message']['chat']['id']
    if True:
        send_all_today_results(id)


def send_all_logs(id):
    logs = get_list_of_relative_path_to_all_logs()
    for log in logs:
        bot.send_document(id, document=open(log, 'rb'))


def get_logs(message, update):
    id = message['message']['chat']['id']
    if True:
        send_all_logs(id)


def send_finall_db(message, update):
    id = message['message']['chat']['id']
    if True:
        list_of_json = create_stickers_and_db.get_list_of_relative_path_to_all_today_json()
        if list_of_json == []:
            bot.send_message(id, 'Сегодня стикеры через бота не получались')
            return 0
        file = create_stickers_and_db.create_finall_table_of_day()
        bot.send_document(id, document=open(file, 'rb'))


def put_all_on_collected(message, update):
    id = message['message']['chat']['id']
    if True:
        orders_count = create_stickers_and_db.set_status_collected_for_all_on_assembly()
        if orders_count == 0:
            bot.send_message(
                id, 'На сборке ноль заказов, переводить в собранные нечего')
            return 0
        bot.send_message(id, f'{orders_count} заказов переведено в собранные')
        send_notification(
            f'Пользователь [{id}](tg://user?id={id}) перевел в собранные {orders_count} заказов')


def force_update_table(message, update):
    id = message['message']['chat']['id']
   # if True:
    #    result_and_errors = update_table()
    #   result = result_and_errors['result']
    #  errors = result_and_errors['erors']
    # str_errors = '\n'.join(errors)
    # if result != '':
    #   send_notification(result)
    #  if len(errors) > 0:
    #     send_notification(f'Что-то не так с артикулами \n{str_errors}')
    #bot.send_message(id, result)

def create_stickers_by_json(message, update):
    id = message['message']['chat']['id']
    file_id = message.message.document['file_id']
    name = message.message.document['file_name']
    file = update.bot.get_file(file_id)
    file.download(name)
    with open(name, 'r') as f:
        orders = json.load(f)
    if True:
        bot.send_message(id, 'Начато создание стикеров')
        try:
            count_of_orders, barcodes = create_stickers_and_db.create_stickers_by_orders(orders)
            if count_of_orders == 0:
                bot.send_message(id, 'На сборке 0 заказов, создавать нечего')
                main_menu(message, update)
                return 0
            bot.send_message(id, f'Стикеры созданы, количество {count_of_orders}')
            send_results(id)
        except Exception as e:
            logging.info(e)
            bot.send_message(id, 'При создании стикеров что-то пошло не так, проверьте, соответствует ли файл заказов с текущем аккаунтом, в противном случае смените аккаунт и попробуйте еще раз')
            return 0

        succsess = False
        while not succsess:
            count_of_try = 0
            try:
                create_stickers_and_db.create_db_for_checking(barcodes)
                send_db(id)
                succsess = True
            except Exception:
                count_of_try += 1
                if count_of_try > 4:
                    succsess = True
                    break
        send_notification(
            f'Пользователь [{id}](tg://user?id={id}) получил стикеры, {count_of_orders}')
        for id_for_not in ID_FOR_NOTIFICATION:
            send_results(id_for_not)
            send_db(id_for_not)
    send_db(bot['message']['chat']['id'])

updater = Updater(token=TELEGRAM_TOKEN)


supplies_keyboard_menu_handler = MessageHandler(
    Filters.text([CATEGORY_SUPLLIES]), supplies_keyboard)
updater.dispatcher.add_handler(supplies_keyboard_menu_handler)

assembly_keyboard_menu_handler = MessageHandler(
    Filters.text([CATEGORY_ON_ASSEMBLY]), assembly_keyboard)
updater.dispatcher.add_handler(assembly_keyboard_menu_handler)

main_meny_category_menu_handler = MessageHandler(
    Filters.text([CATEGORY_MAIN_MENU]), main_menu)
updater.dispatcher.add_handler(main_meny_category_menu_handler)


def set_on_assembly_and_send_notification(bot, orders):
    create_stickers_and_db.set_status_to_orders_by_ids(1, orders)
    orders_count = len(orders)
    with open('orders.json', 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False)
    bot.message.reply_text(f'{orders_count} переведено на сборку')
    bot_1.send_document(id, open('orders.json', 'rb'))
    send_notification(
        f'Пользователь [{id}](tg://user?id={id}) перевел  на сборку {orders_count} заказов')
    send_notification_document('orders.json')


def set_on_assembly_by_article(bot, update):
    id = bot['message']['chat']['id']
    update.user_data['count'] = bot.message.text.strip()
    try:
        count = int(update.user_data['count'])
    except BaseException:
        bot.message.reply_text('Неверный формат числа, начните всё с начала')
        return ConversationHandler.END
    articles = update.user_data['articles']
    orders = create_stickers_and_db.filter_orders_by_article(articles, count)
    if len(orders) == 0:
        bot.message.reply_text('Таких артикулов нет в новых')
        return ConversationHandler.END
    create_stickers_and_db.set_status_to_orders_by_ids(1, orders)
    orders_count = len(orders)
    with open('orders.json', 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False)
    bot.message.reply_text(f'{orders_count} переведено на сборку')
    bot_1.send_document(id, open('orders.json', 'rb'))
    send_notification(
        f'Пользователь [{id}](tg://user?id={id}) перевел  на сборку {orders_count} заказов')
    send_notification_document('orders.json')
    return ConversationHandler.END


def get_articles_from_user(bot, update):
    id = bot['message']['chat']['id']
    bot.message.reply_text(
        'Введите нужные артикулы через пробел, для отмены введите /cancel')
    return 'count'


def get_count_from_user(bot, update):
    id = bot['message']['chat']['id']
   # if not id in whitelistid:
    #    return ConversationHandler.END
    update.user_data['articles'] = bot.message.text.upper().split()
    bot.message.reply_text(
        'Введите масимальное число заказов для перевода, для отмены введите /cancel')
    return 'set_on_assembly'


def start_c(bot, update):
    return 'article'


def cancel(bot, update):
    bot.message.reply_text('Операция отменена')
    return ConversationHandler.END


def set_on_assembly_by_count(bot, update):
    id = bot['message']['chat']['id']
    # if not id in whitelistid:
    #     return ConversationHandler.END
    update.user_data['count'] = bot.message.text.strip()

    try:
        count = int(update.user_data['count'])
    except BaseException:
        bot.message.reply_text('Неверный формат числа')
        return ConversationHandler.END
    orders = create_stickers_and_db.get_all_orders(status=0)[:count]
    create_stickers_and_db.set_status_to_orders(1, orders)
    orders_count = len(orders)
    with open('orders.json', 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False)
    bot.message.reply_text(f'{orders_count} переведено на сборку')
    bot_1.send_document(id, open('orders.json', 'rb'))
    send_notification(
        f'Пользователь [{id}](tg://user?id={id}) перевел  на сборку {orders_count} заказов')
    send_notification_document('orders.json')
    # set_on_assembly_and_send_notification(bot,orders)
    return ConversationHandler.END


set_on_assembly_by_article_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.text(
        [TEXT_TO_PUT_ON_ASSEMBLY_BY_ARTICLE]), get_articles_from_user)],
    states={
        'article': [MessageHandler(Filters.text & ~Filters.command, get_articles_from_user)],
        'count': [MessageHandler(Filters.text & ~Filters.command, get_count_from_user)],
        'set_on_assembly': [MessageHandler(Filters.text, set_on_assembly_by_article)]
    },
    fallbacks=[CommandHandler('cancel', cancel)])

updater.dispatcher.add_handler(set_on_assembly_by_article_handler)

set_on_assembly_by_count_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.text(
        TEXT_TO_PUT_ON_ASSEMBLY_BY_COUNT), get_count_from_user)],
    states={
        'set_on_assembly': [MessageHandler(Filters.text & ~Filters.command, set_on_assembly_by_count)]
    },
    fallbacks=[CommandHandler('cancel', cancel)])

def add_client_start(bot, update):
    bot.message.reply_text('Введите имя клиента (будет использоваться при смене аккаунтов), для отмены /cancel')
    return 'get_token'

def get_name_by_bot(bot, update):
    update.user_data['name'] = bot.message.text.strip()
    bot.message.reply_text('Введите токен клиента')
    return 'get_name_for_sticker'


def get_name_for_sticker(bot, update):
    update.user_data['token'] = bot.message.text.strip()
    if marketplace.check_token(update.user_data['token']) is False:
        bot.message.reply_text('Токен невалиден, операция отменена')
        return ConversationHandler.END
    bot.message.reply_text('Введите имя, которое будет печататься на стикерах, для отмены /cancel')
    return 'add_client_to_json'

def add_client_to_json(bot, update):
    cred = json.load(open('../SERVICE/credentials.json', 'rb'))
    name = update.user_data['name']
    token = update.user_data['token']
    name_for_sticker = bot.message.text.strip()
    if name not in cred.keys():
        cred[name] = {
            'token': token,
            'name': name_for_sticker,
            'telegram_chat_id': 1126541068
        }
        
        with open('credentials.json', 'w') as f:
            json.dump(cred, f, ensure_ascii=False, sort_keys=True, indent=2)
            
        bot.message.reply_text(f'Клиент {name} успешно добавлен')
        return ConversationHandler.END

    bot.message.reply_text(f'Запись с таким именем уже существует, операция отменена')
    return ConversationHandler.END

add_client_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.text([ADD_CLIENT]), add_client_start)],
    states={
        'get_token':[MessageHandler(Filters.text & ~Filters.command, get_name_by_bot)],
        'get_name_for_sticker': [MessageHandler(Filters.text & ~Filters.command, get_name_for_sticker)],
        'add_client_to_json':[MessageHandler(Filters.text & ~Filters.command, add_client_to_json)],
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)
updater.dispatcher.add_handler(add_client_handler)

def get_stats(bot, update):
    id = bot['message']['chat']['id']

    new_orders = get_all_orders(status=0)
    count_new = (len(new_orders))
    _, count_order_without_address = create_stickers_and_db.check_and_delete_orders_with_blank_officeAddress(
        new_orders)

    orders_on_assembly = len(get_all_orders(status=1))
    bot.message.reply_text(
        f'{count_new} — новых, из них без адреса — {count_order_without_address} \n{orders_on_assembly} — на сборке \n ')


def get_client_from_user(bot, update):
    cred = json.load(open('../SERVICE/credentials.json', 'rb'))
    print(cred)
    names = '\n'.join(cred)
    bot.message.reply_text(
        f'Текущий аккаунт {create_stickers_and_db.get_name()}\n\nВарианты выбора \nВыберете один и отправьте его в чат \n{names}')
    return 'get_client_from_user'


def swap_by_client_from_user(bot, update):
   # try:
    client = bot.message.text.strip()
    if client in json.load(open('../SERVICE/credentials.json', 'rb')):
        create_stickers_and_db.swap_token_by_name(client)
        bot.message.reply_text(
            f'Переключение на аккаунт «{client}» прошло успешно')
    else:
        bot.message.reply_text(f'Такого аккаунта не существует')
#    except BaseException:
 #       bot.message.reply_text(
  #          f'Что-то пошло не так, попробуйте еще раз, проверив данные')
    return ConversationHandler.END


swap_client_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.text(
        TEXT_SWAP_CLIENT), get_client_from_user)],
    states={
        'get_client_from_user': [MessageHandler(Filters.text & ~Filters.command, swap_by_client_from_user)]
    },
    fallbacks=[CommandHandler('cancel', cancel)])


def close_supplie_by_bot(bot, update):
    try:
        supplie = bot.message.text.strip()
        result = create_stickers_and_db.close_supplie(supplie)
        if result is None:
            bot.message.reply_text(f'Поставка {supplie} закрыта')
        else:
            bot.message.reply_text(
                f'Что-то пошло не так, вб написал, что {result}')
            return ConversationHandler.END
    except BaseException:
        bot.message.reply_text(
            f'Что-то пошло не так, попробуйте еще раз, проверив данные')
    return ConversationHandler.END


def get_supplie_from_user(bot, update):
    bot.message.reply_text('Введите ID поставки\n для отмены /cancel')
    return 'get_supplie_from_user'


def create_and_send_supplie_by_id(bot, update, supplie_id):
    id = bot['message']['chat']['id']
    try:
        path = create_stickers_and_db.create_stick_of_supplie(supplie_id)
        bot_1.send_document(id, open(path, 'rb'))
    except BaseException:
        bot.message.reply_text(
            'Что-то пошло не так при получении штрихкода поставки. /n Убедитесь в корректности номера поставки и попробуйте еще раз.')


def get_supplies_stick(bot, update):
    supplie = bot.message.text.strip()
    if not supplie[-1].isdigit():
        bot.message.reply_text('Операция получения штрихкода отменена')
        return ConversationHandler.END
    create_and_send_supplie_by_id(bot, update_table, supplie)
    return ConversationHandler.END


get_stick_of_supplie_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.text(
        [TEXT_GET_STICK_OF_SUPPLIE]), get_supplie_from_user)],
    states={
        'get_supplie_from_user': [MessageHandler(Filters.text & ~Filters.command, get_supplies_stick)]
    },
    fallbacks=[CommandHandler('cancel', cancel)])
updater.dispatcher.add_handler(get_stick_of_supplie_handler)

# close_supplie_handler = ConversationHandler(
#     entry_points=[MessageHandler(Filters.text(
#         ['Закрыть поставку']), get_supplie_from_user)],
#     states={
#         'get_supplie_from_user': [MessageHandler(Filters.text & ~Filters.command, close_supplie_by_bot)]
#     },
#     fallbacks=[CommandHandler('cancel', cancel)])\


def close_current_supplie(bot, update):
    try:
        supplies = create_stickers_and_db.get_supplies()
        if supplies == []:
            return bot.message.reply_text(
                f'Нет активной поставки, вначале создайте её, добавьте заказы и распечатайте стикеры')
        
        current_supplie = supplies[0]["supplyId"]
        create_stickers_by_bot(bot, update)
        result = create_stickers_and_db.close_supplie(current_supplie)
        if result is None:
            bot.message.reply_text(f'Поставка {current_supplie} закрыта')
        else:
            bot.message.reply_text(
                f'Что-то пошло не так, вб написал, что {result}')
    except Exception:
        bot.message.reply_text(
            f'Что-то пошло не так, попробуйте еще раз, проверив данные')


close_current_supplie_handler = MessageHandler(
    Filters.text([TEXT_CLOSE_SUPPLIE]), close_current_supplie)

updater.dispatcher.add_handler(close_current_supplie_handler)


def get_current_supplie(bot, update):
    supplies = create_stickers_and_db.get_supplies()
    if supplies == []:
        bot.message.reply_text('Активных поставок нет')
        reply_kb_markup = ReplyKeyboardMarkup(([KeyboardButton('Да')], [KeyboardButton('В главное меню')]),
                                              resize_keyboard=True,
                                              one_time_keyboard=True)
        bot.message.reply_text('Создать новую?', reply_markup=reply_kb_markup)
        return 'get_answer'
    current_supplie = supplies[0]["supplyId"]
    create_and_send_supplie_by_id(bot, update, current_supplie)
    bot.message.reply_text(f'{current_supplie}')


def get_answer_about_new_supplie(bot, update):
    answer = bot.message.text.strip()
    if answer != 'Да':
        main_menu(bot, update)
        return ConversationHandler.END
    create_new_supplie(bot, update)
    return ConversationHandler.END


def create_new_supplie(bot, update):
    data = create_stickers_and_db.create_new_supplie()
    supplie_id = data['supplyId']
    if supplie_id == '':
        bot.message.reply_text(f'Что-то пошло не так, ошибка {data["error"]}')
        main_menu(bot, update)
        return ConversationHandler.END
    bot.message.reply_text(f'Номер созданной поставки {supplie_id}')
    create_and_send_supplie_by_id(bot, update, supplie_id)
    main_menu(bot, update)
    id = bot['message']['chat']['id']
    send_notification(
        f'Пользователь [{id}](tg://user?id={id}) создал новую поставку {supplie_id}'
        f'для аккаунта {create_stickers_and_db.get_name()}')
    return ConversationHandler.END


get_current_supplie_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.text(
        [TEXT_GET_CURRENT_SUPPLIE]), get_current_supplie)],
    states={
        'get_answer': [MessageHandler(Filters.text & ~Filters.command, get_answer_about_new_supplie)],
        'create_new_supplie': [MessageHandler(Filters.text & ~Filters.command, create_new_supplie)],
    },
    fallbacks=[CommandHandler('cancel', cancel)])
updater.dispatcher.add_handler(get_current_supplie_handler)


def add_orders_to_supplie_by_bot(bot, update):
    try:
        supplie = bot.message.text.strip()
        orders = create_stickers_and_db.get_all_orders(status=1)
        if len(orders) == 0:
            bot.message.reply_text(f'На сборке ноль заказов, добавлять нечего')
            return ConversationHandler.END

        result = create_stickers_and_db.add_orders_to_supplie(supplie, orders)
        if result == 200:
            bot.message.reply_text(f'Okey')
        else:
            bot.message.reply_text(
                f'Что-то пошло не так, вб написал, что {result}')
        return ConversationHandler.END
    except BaseException:
        bot.message.reply_text(
            f'Что-то пошло не так, попробуйте еще раз, проверив данные')
    return ConversationHandler.END


# add_orders_to_supplie_handler = ConversationHandler(
#     entry_points=[MessageHandler(Filters.text(
#         [TEXT_ADD_ORDERS_TO_SUPPLIE]), get_supplie_from_user)],
#     states={
#         'get_supplie_from_user': [MessageHandler(Filters.text & ~Filters.command, add_orders_to_supplie_by_bot)]
#     },
#     fallbacks=[CommandHandler('cancel', cancel)])

def add_orders_to_current_supplie(bot, update):
    try:
        supplies = create_stickers_and_db.get_supplies()
        if supplies == []:
            return bot.message.reply_text(
                f'Нет активной поставки, вначале создайте её')
        current_supplie = supplies[0]["supplyId"]
        orders = create_stickers_and_db.get_all_orders(status=1)
        if len(orders) == 0:
            bot.message.reply_text('На сборке ноль заказов, добавлять нечего')
        result = create_stickers_and_db.add_orders_to_supplie(
            current_supplie, orders)
        if result == 200:
            bot.message.reply_text(f'Okey')
        else:
            bot.message.reply_text(
                f'Что-то пошло не так, вб написал, что {result}')
    except Exception:
        bot.message.reply_text(
            f'Что-то пошло не так, попробуйте еще раз, проверив данные')


add_orders_to_current_supplie_handler = MessageHandler(
    Filters.text([TEXT_ADD_ORDERS_TO_SUPPLIE]), add_orders_to_current_supplie)

updater.dispatcher.add_handler(add_orders_to_current_supplie_handler)


def swap_client_in_json_by_bot(bot, update):
    id = bot['message']['chat']['id']
    client = bot.message.text.strip()
    swap_or_create_client_in_json(id, client)


def swap_or_create_client_in_json(id, client):
    db = json.load(open('users_and_client.json', 'rb'))
    if client in json.load(open('../SERVICE/credentials.json', 'rb')):
        db[id] = client
        with open('users_and_client.json', 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False)


def get_client_info_by_telegram_id(id):
    db = json.load(open('users_and_client.json', 'rb'))
    if str(id) not in db:
        swap_or_create_client_in_json(id, DEFAULT_CLIENT)
    client = db[str(id)]['client']
    client_db = json.load(open('../SERVICE/credentials.json', 'rb'))
    return client_db[client]


updater.dispatcher.add_handler(swap_client_handler)


updater.dispatcher.add_handler(set_on_assembly_by_count_handler)
create_stickers_menu_handler = MessageHandler(
    Filters.text([TEXT_TO_CREATE_STICKERS]), create_stickers_by_bot)
updater.dispatcher.add_handler(create_stickers_menu_handler)

get_top_of_articles_handler = MessageHandler(
    Filters.text([TEXT_TOP]), get_top_of_articles)
updater.dispatcher.add_handler(get_top_of_articles_handler)

put_all_on_collected_menu_handler = MessageHandler(
    Filters.text([TEXT_TO_PUT_ON_COLLECTED]), put_all_on_collected)
updater.dispatcher.add_handler(put_all_on_collected_menu_handler)

update_table_menu_handler = MessageHandler(
    Filters.text([TEXT_UPDATE_TABLE]), force_update_table)
updater.dispatcher.add_handler(update_table_menu_handler)

get_stats_handler = MessageHandler(Filters.text(['Статистика']), get_stats)
updater.dispatcher.add_handler(get_stats_handler)

start_handler = CommandHandler('start', main_menu)
updater.dispatcher.add_handler(start_handler)

get_results_handler = CommandHandler('get_results', get_results)
updater.dispatcher.add_handler(get_results_handler)

put_all_on_collected_handler = CommandHandler(
    'put_all_on_collected', put_all_on_collected)
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

instruction_handler = MessageHandler(
    Filters.text([INSTRUCTION]), send_instruction)
updater.dispatcher.add_handler(instruction_handler)

document_handler = MessageHandler(
    Filters.document.file_extension("json"),
    create_stickers_by_json)
updater.dispatcher.add_handler(document_handler)

updater.start_polling()
