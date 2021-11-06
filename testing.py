import datetime
import pytz
import requests
import codecs
import os
from dotenv import load_dotenv
from PyPDF2 import PdfFileMerger


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
    pdfs=[]
    for id in ids:
        json_orders_id = {
            "orderIds": [int(id)]
        }
        response = requests.post(
            url_for_getting_stikers,
            json=json_orders_id,
            headers=headers)
        data_for_pdf = response.json()['data']['file']
        file_data = bytes(data_for_pdf, 'utf-8')
        with open(f'pdf/{id}.pdf', 'wb') as f:
            f.write(codecs.decode(file_data, 'base64'))
        with open(f'id_and_data.txt', 'a') as f:
            print(id, data_for_pdf, file=f)
        pdfs += [f'pdf/{id}.pdf']
    merger = PdfFileMerger()
    for pdf in pdfs:
        merger.append(pdf)
    merger.write("result2.pdf")
    merger.close()


    # file_data = bytes(data_for_pdf, 'utf-8')

    # with open('data.txt', 'w') as f:
    #     print(data_for_pdf, file=f)


def get_all_orders(status=0, date_end=get_now_time()):
    date_start = '2021-11-06T00:47:17.528082+00:00'
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

def get_barcodes_and_ids(orders):
    barcodes_and_ids = {}
    for order in orders:
        barcode = order['barcode']
        id = order['orderId']
        if barcode not in  barcodes_and_ids.keys(): 
            barcodes_and_ids[barcode] = [id]
        else:
            barcodes_and_ids[barcode] += [id]
    return barcodes_and_ids
if __name__ == '__main__':
    orders = get_all_orders(status=2)
    # orders.sort(key=barcode_key_for_sorting)
    orders = sorted(orders, key=lambda x: x['barcode'])
    # print(orders[:10])
    # for i in range(51):
    #     print(orders[i]['barcode'])
    orders_ids = get_orders_ids(orders)
    print(len(orders))
    barcodes_and_ids = get_barcodes_and_ids(orders)
    print(barcodes_and_ids.keys())
    with open('tmp.txt', 'w') as f:
        print(orders_ids, file=f)
    with open('ids_and_barcode.txt', 'w') as f:
        for order in orders:
            print(order['orderId'], order['barcode'], file=f)
        
    # # create_pdf_stickers_by_ids(ids[:10])
    create_pdf_stickers_by_ids(orders_ids)
