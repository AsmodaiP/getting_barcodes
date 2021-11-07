import datetime
import json
import pytz
import requests
import codecs
import os
from dotenv import load_dotenv
from PyPDF2 import PdfFileMerger
from requests.api import head
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm, inch

pdfmetrics.registerFont(TTFont('FreeSans', 'fonts/FreeSans.ttf'))
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
    pdfs = []
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


def get_barcodes_with_orders_and_chartId(orders):
    barcodes_and_ids = {}
    for order in orders:
        barcode = order['barcode']
        id = order['orderId']
        chrt_id = order['chrtId']
        if barcode not in barcodes_and_ids.keys():
            barcodes_and_ids[barcode] = {'orders': [id], 'chrtId': chrt_id}
        else:
            barcodes_and_ids[barcode]['orders'] += [id]
    return barcodes_and_ids


def edit_blank_pdf(barkode_info):
    canvas = Canvas('pdf/blank.pdf', pagesize=(1.6*inch,  1.2*inch))
    font_size = 8
    canvas.setFont('FreeSans', font_size)
    n = 0
    slice = 27
    while len(barkode_info['name']) > 0:
        canvas.drawString(2, 75-n*font_size,
                          barkode_info['name'][:slice], charSpace=0)
        barkode_info['name'] = barkode_info['name'][slice:]
        print(barkode_info['name'])
        n += 1
    canvas.drawString(2, 75-font_size*n, barkode_info['article'])
    n += 1
    canvas.drawString(2, 75-font_size*n, barkode_info['chrtId'])
    canvas.save()


def create_pdf_stickers_by_barcodes(barcodes_and_ids):
    url_for_getting_stikers = 'https://suppliers-api.wildberries.ru/api/v2/orders/stickers/pdf'
    data_for_pdf = ''
    results_file = []
    for barcode in barcodes_and_ids.keys():
        pdfs = ['pdf/blank.pdf']
        for id in barcodes_and_ids[barcode]['orders']:
            json_orders_id = {
                "orderIds": [int(id)]
            }
            response = requests.post(
                url_for_getting_stikers,
                json=json_orders_id,
                headers=headers)
            data_for_pdf = response.json()['data']['file']
            file_data = bytes(data_for_pdf, 'utf-8')
            with open(f'pdf/barcodes/{id}.pdf', 'wb') as f:
                f.write(codecs.decode(file_data, 'base64'))
            # with open(f'id_and_data.txt', 'a') as f:
            #     print(id, data_for_pdf, file=f)
            pdfs += [f'pdf/barcodes/{id}.pdf']
        merger = PdfFileMerger()
        for pdf in pdfs:
            merger.append(pdf)
        merger.write(f"pdf/barcodes/result_{barcode}.pdf")
        results_file.append(f"pdf/barcodes/result_{barcode}.pdf")
        merger.close()
    merger = PdfFileMerger()
    for result in results_file:
        merger.append(result)
    merger.write('results.pdf')
    merger.close()


def getting_information_about_barcode_by_chartId(chrtId):
    url = 'https://suppliers-api.wildberries.ru/card/list'
    json_for_request = {
        "id": 1,
        "jsonrpc": "2.0",
        "params": {
            "filter": {
                "find": [
                    {
                        "column": "nomenclatures.variations.chrtId",
                        "search": chrtId
                    }
                ],
                "order": {
                    "column": "string",
                    "order": "string"
                }
            }
        }
    }
    response = requests.post(url=url, headers=headers, json=json_for_request)
    good = response.json()['result']['cards'][0]
    name = ''
    article = good['nomenclatures'][0]['vendorCode']
    # print(good.keys())
    # print(good['nomenclatures'][0]['vendorCode'])
    for type_and_params in good['addin']:
        if type_and_params['type'] == 'Наименование':
            name = type_and_params['params'][0]['value']
    info = {
        'name': name,
        'article': article,
        'chrtId': chrtId
    }
    return info


def add_information_about_barcodes(barcodes):
    for barcode in barcodes.keys():
        barcodes[barcode]['info'] = getting_information_about_barcode_by_chartId(
            barcodes[barcode]['chrtId'])
    return barcodes


def create_stickers():
    orders = get_all_orders(status=1)
    orders = sorted(orders, key=lambda x: x['barcode'])
    barcodes = get_barcodes_with_orders_and_chartId(orders)
    barcodes = add_information_about_barcodes(barcodes)
    create_pdf_stickers_by_barcodes(barcodes)


if __name__ == '__main__':
    # canvas = Canvas('pdf/blank.pdf',pagesize=(113.4,  85.17))
    # canvas.setFont('FreeSans', 4)
    # canvas.drawString(2, 75, "Носки с принтом 'Новоssгодниеllll1adsfgsdgsgsdgsdgsdgds123", charSpace=0)
    info = {
        'name': "Носки с принтом 'Новоssssодние",
        'article': 'WR0055/WR0055/03/36-41',
        'chrtId': str(8156990)
    }
    edit_blank_pdf(info)
    # canvas.save()
