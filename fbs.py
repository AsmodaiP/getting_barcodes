import json
from google.oauth2 import service_account
import os
from googleapiclient.discovery import build
import datetime as dt
from dotenv import load_dotenv
import marketplace
import logging
from get_orders_of_day import get_all_today_orders
import time
import telegram
from logging.handlers import RotatingFileHandler

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
ID_FOR_NOTIFICATION = 295481377
bot = telegram.Bot(token=TELEGRAM_TOKEN)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, '../SERVICE/credentials_service.json')
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
except:
    SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, 'credentials_service.json')
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
RANGE_NAME = '12.2021'
START_POSITION_FOR_PLACE = 14

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', None)
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
console_handler = logging.StreamHandler()
log_file = 'table.log'
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

def get_barcodes_with_orders_and_chartId(token, orders):
    barcodes_and_ids = {}
    logging.info('Сортировка информации по баркодам')
    for order in orders:
        barcode = order['barcodes'][0]
        id = int(order['orderId'])
        chrt_id = order['chrtId']
        if barcode not in barcodes_and_ids.keys():
            barcodes_and_ids[barcode] = {'orders': [id], 'chrtId': chrt_id}
        else:
            barcodes_and_ids[barcode]['orders'] += [id]

    logging.info(f'Получено {len(barcodes_and_ids)} баркодов')
    return barcodes_and_ids


def convert_to_column_letter(column_number):
    column_letter = ''
    while column_number != 0:
        c = ((column_number - 1) % 26)
        column_letter = chr(c + 65) + column_letter
        column_number = (column_number - c) // 26
    return column_letter


# def get_data_about_articles():
#     json_dir = create_all_today_path()['json_dir']
#     create_finall_table_of_day()
#     data = json.load(open(os.path.join(json_dir, 'result_fbs.json'), 'r'))
#     return data


def get_count_or_0(data, article):
    if article in data.keys():
        count = data[article]
        del data[article]
        return count
    else:
        return 0


def update_table(data):
    if SPREADSHEET_ID is None:
        return 'SPREADSHEET_ID не задано'
    position_for_place = START_POSITION_FOR_PLACE + \
        (dt.date.today().day - 1) * 6
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                range=RANGE_NAME, majorDimension='ROWS').execute()
    values = result.get('values', [])
    i = 3
    result = ''
    if not values:
        logging.info('No data found.')
    else:
        letter_for_range = convert_to_column_letter(position_for_place)
        body_data = [{'range': f'{RANGE_NAME}!{letter_for_range}{i-1}',
                      'values': [[str(dt.datetime.today().strftime('%d-%m-%Y %H:%M'))]]}]
        for row in values[2:]:
            article = row[7].strip().upper()
            price = row[8].strip().replace(' ', '')[:-1]
            count = get_count_or_0(data, article)
            count_from_table = row[position_for_place - 1]

            if count_from_table.isdigit():
                count = max(int(count), int(count_from_table))
            if count != 0:
                body_data += [{'range': f'{RANGE_NAME}!{letter_for_range}{i}',
                               'values': [[count]]}]
                result += f'{article} — {count}\n'

            else:
                try:
                    if row[position_for_place - 1].strip() == '':
                        body_data += [
                            {'range': f'{RANGE_NAME}!{letter_for_range}{i}', 'values': [[count]]}]
                except BaseException:
                    body_data += [{'range': f'{RANGE_NAME}!{letter_for_range}{i}',
                                   'values': [[count]]}]
            if price.isdigit():
                letter_for_range = convert_to_column_letter(
                    position_for_place + 2)
                body_data += [{'range': f'{RANGE_NAME}!{letter_for_range}{i}',
                               'values': [[int(price) * int(count)]]}]
            i += 1
        body = {
            'valueInputOption': 'USER_ENTERED',
            'data': body_data
        }
        sheet.values().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body).execute()
    return {'result': result, 'errors': data.keys()}


def get_data_about_today_nmid_and_count_of_orders(token):
    orders = get_all_today_orders(token)
    barcodes = marketplace.get_barcodes_with_full_info(
        token=token, orders=orders)
    order_and_nmid_dict = {}
    for barcode in barcodes.keys():
        orders = barcodes[barcode]['orders']
        for order in orders:
            order_and_nmid_dict[order] = barcodes[barcode]['info']['nmId']
    nmid_and_count = {}
    for order in order_and_nmid_dict.keys():
        article = str(order_and_nmid_dict[order])
        if not article in nmid_and_count:
            nmid_and_count[article] = 1
        else:
            nmid_and_count[article] += 1
    return nmid_and_count


if __name__ == '__main__':
    while True:
        try:
            cred = json.load(open('credentials.json', 'rb'))
            tokens = []
            tokens_and_name = {}
            for name in cred.keys():
                token = cred[name]['token']
                data = get_data_about_today_nmid_and_count_of_orders(token)
                result = update_table(data)
                errors = result['errors']

                if len(errors) > 0 and name == 'БелотеловАГ':
                    str_errors = '\n'.join(errors)
                    bot.send_message(
                        ID_FOR_NOTIFICATION, f'Что-то не так с артикулами  у {name} \n{str_errors}')
            time.sleep(120)

        except Exception as e:
            logging.error('Ошибка при обновлении таблицы фбс', exc_info=e)
            bot.send_message(ID_FOR_NOTIFICATION,
                             f'Ошибка {e} при обнолвении таблицы фбс')
