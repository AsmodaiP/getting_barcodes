import datetime
import pytz
import requests
import codecs
import os
from dotenv import load_dotenv
from requests.api import get
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)


def get_now_time():
    d = datetime.datetime.utcnow()
    d_with_timezone = d.replace(tzinfo=pytz.UTC)
    return(d_with_timezone.isoformat())


TOKEN = os.environ.get('TOKEN')
base_url_for_getting_orders = 'https://suppliers-api.wildberries.ru/api/v2/orders'
url = 'https://suppliers-api.wildberries.ru/api/v2/orders?date_start=2021-11-06T08%3A47%3A17.528082%2B00%3A00&date_end=2021-11-06T11%3A19%3A03.297640%2B00%3A00&status=2&take=2&skip=0'
headers = {
    'Authorization': TOKEN,
}


def create_pdf_stickers_by_ids(ids):
    url_for_getting_stikers = 'https://suppliers-api.wildberries.ru/api/v2/orders/stickers/pdf'
    data_for_pdf = ''
    for id in ids:
        json_orders_id = {
            "orderIds": [id]
        }
        response = requests.post(
            url_for_getting_stikers,
            json=json_orders_id,
            headers=headers)
        data_for_pdf += response.json()['data']['file']
    file_data = bytes(data_for_pdf, 'utf-8')
    with open('test33.pdf', 'wb') as f:
        f.write(codecs.decode(file_data, 'base64'))
    with open('data.txt', 'w') as f:
        print(data_for_pdf, file=f)


def get_all_orders(status=0, date_end=get_now_time()):
    date_start = '2021-11-06T03:47:17.528082+00:00'
    orders = []
    params = {
        'date_end': date_end,
        'date_start': date_start,
        'status': status,
        'take': 100,
        'skip': 0
    }
    response = requests.get(
        base_url_for_getting_orders,
        headers=headers,
        params=params)
    orders_from_current_response = response.json()['orders']
    orders += orders_from_current_response
    while orders_from_current_response != []:
        params['skip'] += len(orders_from_current_response)
        response = requests.get(
            base_url_for_getting_orders,
            headers=headers,
            params=params)
        orders_from_current_response = response.json()['orders']
        orders += orders_from_current_response
    return orders




def barcode_key_for_sorting(order):
    return int(order['barcode'])




def get_orders_ids(orders):
    ids = []
    for order in orders:
        ids.append(int(order['orderId']))
    return ids



if __name__ == '__main__':
    orders = get_all_orders(status=2)
    orders.sort(key=barcode_key_for_sorting)
    with open('tmp.txt', 'w') as f:
        print(orders, file=f)
    orders_ids = get_orders_ids(orders)
    create_pdf_stickers_by_ids(orders_ids)
