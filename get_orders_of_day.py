import logging
import requests
import datetime
import pytz
from dotenv import load_dotenv
import os
from dateutil import tz
from logging.handlers import RotatingFileHandler


load_dotenv()

base_url_for_getting_orders = 'https://suppliers-api.wildberries.ru/api/v2/orders'
TOKEN = os.environ.get('TOKEN')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(BASE_DIR, 'logs/')
log_file = os.path.join(BASE_DIR, 'logs/get_orders.log')
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

def get_beggining_and_end_of_today():
    d = datetime.datetime.utcnow()
    delta = datetime.timedelta(1)
    begin = d.replace(tzinfo=pytz.UTC).isoformat()
    
    # print(d_with_timezone)
    today= datetime.date.today()
    d = datetime.datetime(year=today.year, month=today.month, day=today.day-1, hour=21,microsecond=0, minute=0, tzinfo=pytz.UTC)
    end = d.replace(tzinfo=pytz.UTC).isoformat()
    # print(end)
    return( begin, end)


def get_now_time():
    d = datetime.datetime.utcnow()
    d_with_timezone = d.replace(tzinfo=pytz.UTC)
    return(d_with_timezone.isoformat())


def get_all_orders(token, date_end='', date_start='2021-11-06T00:47:17.528082+00:00'):

    headers = {
    'Authorization': token,
    }

    orders = []
    params = {
        'date_end': date_end,
        'date_start': date_start,
        'take': 1000,
        'skip': 0
    }

    response = requests.get(
        base_url_for_getting_orders,
        headers=headers,
        params=params)
    try:
        orders_from_current_response = response.json()['orders']
    except KeyError as e:
        orders_from_current_response = []
        logging.error(e, exc_info=True)
    orders += orders_from_current_response
    while orders_from_current_response != []:
        params['skip'] += len(orders_from_current_response)
        response = requests.get(
            base_url_for_getting_orders,
            headers=headers,
            params=params)
        orders_from_current_response = response.json()['orders']
        orders += orders_from_current_response
        logging.info(f'{len(orders)}')
    logging.info(f'Получено {len(orders)}')
    return orders

def get_all_today_orders(token):
    end, beginning = get_beggining_and_end_of_today()
    orders = get_all_orders(token=token, date_end=end, date_start=beginning)
    orders = clean_orders_from_user_status_1(orders)
    return orders

def clean_orders_from_user_status_1(orders):
    logging.info('Очистка заказов от заказов со статусом 1')
    filtered_orders = []
    for order in orders:
        if order['userStatus'] != 1:
            filtered_orders += [order]
    logging.info(f'Осталось  {len(filtered_orders)}')
    return filtered_orders

if __name__ == '__main__':
    print(len(get_all_today_orders(TOKEN)))
    # # get_all_today_orders()
    # headers = {
    # 'Authorization': TOKEN,
    # }
    # # logging.info(f'Получение всех заказов со статусом {status}')
    # orders = []
    # params = {
    #     'date_end': '2021-12-15T21:00:00+00:00',
    #     'date_start': '2021-12-14T21:00:00+00:00',
    #     'take': 1000,
    #     'skip': 0,
    # }

    # response = requests.get(
    #     base_url_for_getting_orders,
    #     headers=headers,
    #     params=params)
    # try:
    #     orders_from_current_response = response.json()['orders']
    # except KeyError as e:
    #     orders_from_current_response = []
    #     logging.error(e, exc_info=True)
    # orders += orders_from_current_response
    # while orders_from_current_response != []:
    #     params['skip'] += len(orders_from_current_response)
    #     response = requests.get(
    #         base_url_for_getting_orders,
    #         headers=headers,
    #         params=params)
    #     orders_from_current_response = response.json()['orders']
    #     orders += orders_from_current_response
    #     logging.info(f'{len(orders)}')
    # logging.info(f'Получено {len(orders)}')
    
    # filtered_orders = []
    # count=0
    # for order in orders:
    #     if order['barcode']=='2000790373009':
    #         count+=1

    #     if order['userStatus'] != 1:

    #         if order['userStatus'] != 4:
    #             print(order['userStatus']) 
    #         filtered_orders += [order]
    # logging.info(f'Осталось  {len(filtered_orders)}')
    # print(count)
    # headers = {
    # 'Authorization': TOKEN,
    # }
    # # logging.info(f'Получение всех заказов со статусом {status}')
    # orders = []
    # params = {
    #     'date_end': date_end,
    #     'date_start': date_start,
    #     'take': 1000,
    #     'skip': 0
    # }

    # response = requests.get(
    #     base_url_for_getting_orders,
    #     headers=headers,
    #     params=params)
    # try:
    #     orders_from_current_response = response.json()['orders']
    # except KeyError as e:
    #     orders_from_current_response = []
    #     logging.error(e, exc_info=True)
    # orders += orders_from_current_response
    # while orders_from_current_response != []:
    #     params['skip'] += len(orders_from_current_response)
    #     response = requests.get(
    #         base_url_for_getting_orders,
    #         headers=headers,
    #         params=params)
    #     orders_from_current_response = response.json()['orders']
    #     orders += orders_from_current_response
    #     logging.info(f'{len(orders)}')
    # logging.info(f'Получено {len(orders)}')
    # pass  

# import time
# def get_next_utc_unix_00_00():
#     current_date = time.strftime("%d %b %Y", time.gmtime(time.time() + 86400))
#     current_date += ' 00:00:00'
#     next_utc = int(time.mktime(time.strptime(current_date, '%d %b %Y %H:%M:%S')))
#     return next_utc
# print(get_next_utc_unix_00_00())