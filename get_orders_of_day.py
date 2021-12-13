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


def get_all_orders(token, status=0, date_end=get_now_time(), date_start='2021-11-06T00:47:17.528082+00:00'):

    headers = {
    'Authorization': token,
    }

    # logging.info(f'Получение всех заказов со статусом {status}')
    date_end = get_now_time()
    orders = []
    params = {
        'date_end': date_end,
        'date_start': date_start,
        'status': status,
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

if __name__ == '__main__':
    pass
    #  print(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(1))
    end, beginning = get_beggining_and_end_of_today()
    print(end)
    print(beginning)
    orders = get_all_orders(token=TOKEN, status=0, date_end=end, date_start=beginning)
    print(len(orders))
    # for order in orders:
    #     print(order['orderId'])
# import time
# def get_next_utc_unix_00_00():
#     current_date = time.strftime("%d %b %Y", time.gmtime(time.time() + 86400))
#     current_date += ' 00:00:00'
#     next_utc = int(time.mktime(time.strptime(current_date, '%d %b %Y %H:%M:%S')))
#     return next_utc
# print(get_next_utc_unix_00_00())