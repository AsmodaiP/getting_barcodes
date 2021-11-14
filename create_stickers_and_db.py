import datetime
import json
import pytz
import requests
import codecs
import os
from dotenv import load_dotenv
from PyPDF2 import PdfFileMerger
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch
import logging
from logging.handlers import RotatingFileHandler
import openpyxl


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(BASE_DIR, 'logs/bot.log')
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


pdfmetrics.registerFont(TTFont('FreeSans', 'fonts/FreeSans.ttf'))
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

def create_path_if_not_exist(path):
    if not os.path.exists(path):
        os.mkdir(path)


def get_now_time():
    d = datetime.datetime.utcnow()
    d_with_timezone = d.replace(tzinfo=pytz.UTC)
    return(d_with_timezone.isoformat())


TOKEN = os.environ.get('TOKEN')
base_url_for_getting_orders = 'https://suppliers-api.wildberries.ru/api/v2/orders'
headers = {
    'Authorization': TOKEN,
}


cred = json.load(open('credentials.json', 'rb'))
TOKEN = cred['БелотеловАГ']['token']
NAME = cred['БелотеловАГ']['name']

pdf_path = os.path.join(BASE_DIR, 'pdf/')
create_path_if_not_exist(pdf_path)
create_path_if_not_exist(os.path.join(pdf_path, str(datetime.date.today())))
today_path_wiht_name = os.path.join(pdf_path, str(datetime.date.today()), NAME)
create_path_if_not_exist(today_path_wiht_name)
# results_path = os.path.join()


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
        path = os.path.join(today_path_wiht_name, f'{id}.pdf')
        with open(path, 'wb') as f:
            f.write(codecs.decode(file_data, 'base64'))
        pdfs += [path]
    merger = PdfFileMerger()
    for pdf in pdfs:
        merger.append(pdf)
    merger.write("result2.pdf")
    merger.close()


def get_all_orders(status=0, date_end=get_now_time()):
    logging.info(f'Получение всех заказов со статусом {status}')
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
    try:
        orders_from_current_response = response.json()['orders']
    except KeyError as e:
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


def barcode_key_for_sorting(order):
    return int(order['barcode'])


def get_orders_ids(orders):
    ids = []
    for order in orders:
        ids.append(int(order['orderId']))
    return ids


def get_barcodes_with_orders_and_chartId(orders):
    barcodes_and_ids = {}
    logging.info('Сортировка информации по баркодам')
    for order in orders:
        barcode = order['barcode']
        id = order['orderId']
        chrt_id = order['chrtId']
        if barcode not in barcodes_and_ids.keys():
            barcodes_and_ids[barcode] = {'orders': [id], 'chrtId': chrt_id}
        else:
            barcodes_and_ids[barcode]['orders'] += [id]

    logging.info(f'Получено {len(barcodes_and_ids)} баркодов')
    return barcodes_and_ids


def edit_blank_pdf(barcode_info):

    canvas = Canvas('pdf/blank1.pdf', pagesize=(1.6 * inch, 1.2 * inch))
    font_size = 9
    canvas.setFont('FreeSans', font_size)
    n = 0
    blanks_number = 1
    slice = 23
    name_of_host = NAME
    name = barcode_info['name']
    size = barcode_info['size']
    article = f'article = {barcode_info["article"]}'
    color = barcode_info['color']
    extra_colors = barcode_info['extra_colors']
    count = 'Количество = ' + str(barcode_info['count'])
    chrtId = f'chrtId = {barcode_info["chrtId"]}'
    blanks = ['pdf/blank1.pdf']
    for params in (count,name_of_host, name, size, color, extra_colors, article, chrtId):
        a = str(params)
        while len(a) > 0:
            if n > 8:
                blanks_number += 1
                canvas.save()
                canvas = Canvas(
                    f'pdf/blank{blanks_number}.pdf', pagesize=(1.6 * inch, 1.2 * inch))
                canvas.setFont('FreeSans', font_size)
                blanks += [f'pdf/blank{blanks_number}.pdf']
                n = 0
            canvas.drawString(2, 75 - n * font_size,
                              a[:slice], charSpace=0)
            a = a[slice:]
            n += 1
    canvas.save()
    merg = PdfFileMerger()
    for blank in blanks:
        merg.append(blank)
    merg.write('pdf/blank.pdf')
    merg.close()
    logging.info(
        f'Получена информация: наименование "{barcode_info["name"]}" '
        f' {count}, '
        f'артикул = {article}, '
        f'chrtId = {chrtId} '
        f'{"Size "+size if size != "" else ""} '
        f'{"color "+ color if color != "" else ""} '
        f'{"Доп цвета: "+extra_colors if extra_colors != "" else ""} ')


def get_StickerEncoded_by_orderId(id):
    url = 'https://suppliers-api.wildberries.ru/api/v2/orders/stickers'
    json_order_id = {
        "orderIds": [int(id)]
    }
    response = requests.post(
        url,
        json=json_order_id,
        headers=headers)
    return response.json()['data'][0]['sticker']['wbStickerEncoded']


def create_and_merge_pdf_by_barcodes_and_ids(barcodes_and_ids):
    logging.info('Создание pdf для баркодов')
    results_files = []
    url_for_getting_stikers = 'https://suppliers-api.wildberries.ru/api/v2/orders/stickers/pdf'
    for barcode in barcodes_and_ids.keys():
        edit_blank_pdf(barcodes_and_ids[barcode]['info'])
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
            path = os.path.join(today_path_wiht_name, f'{id}.pdf')
            with open(path, 'wb') as f:
                f.write(codecs.decode(file_data, 'base64'))
            pdfs += [path]
        merger = PdfFileMerger()
        for pdf in pdfs:
            merger.append(pdf)
        path_for_result_of_barcode = os.path.join(
            today_path_wiht_name, f'result_{barcode}.pdf')
        merger.write(path_for_result_of_barcode)
        results_files.append(path_for_result_of_barcode)
        merger.close()
        logging.info(f'Создано pdf для баркода {barcode}')
    return results_files


def create_pdf_stickers_by_barcodes(barcodes_and_ids):
    results_files = []
    results_files = create_and_merge_pdf_by_barcodes_and_ids(barcodes_and_ids)
    merger = PdfFileMerger()
    logging.info('Объединение pdf файлов в results.pdf')
    for result in results_files:
        merger.append(result)
    merger.write('results.pdf')
    merger.close()


def get_data_nomenclature_from_card_by_chrtId(card, chrtId):
    all_nomenclatures = card['nomenclatures']
    for nomenclature in all_nomenclatures:
        for diffetent_types in nomenclature['variations']:
            vendorCode = nomenclature['vendorCode']
            data_about_nomenclature = diffetent_types
            for field in data_about_nomenclature:
                if data_about_nomenclature[field] == chrtId:
                    return(data_about_nomenclature, vendorCode, nomenclature)


def get_card_by_chrtId(chrtId):
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
    # print(response.content)
    card = response.json()['result']['cards'][0]
    return card


def get_card_by_nmid(nmid):
    url = 'https://suppliers-api.wildberries.ru/card/list'
    json_for_request = {
        "id": 1,
        "jsonrpc": "2.0",
        "params": {
            "filter": {
                "find": [
                    {
                        "column": "nomenclatures.nmId",
                        "search": nmid
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
    card = response.json()['result']['cards'][0]
    return card


def getting_information_about_barcode_by_chartId(chrtId):
    good = get_card_by_chrtId(chrtId)
    name = ''
    nomenclature_data, article, nomenclature = get_data_nomenclature_from_card_by_chrtId(
        good, int(chrtId))
    size = ''
    color = ''
    extra_colors = ''
    addin = nomenclature['addin']
    for type_and_params in addin:
        # print(type_and_params['params'])
        # print(type_and_params)
        if type_and_params['type'] in ('Цвет', 'Основной цвет'):
            color = type_and_params['params'][0]['value']
        if type_and_params['type'] == 'Доп. цвета':
            for extra_color in type_and_params['params']:
                extra_colors += extra_color['value']+' '
    if 'Доп. цвета' in nomenclature.keys():
        extra_colors = nomenclature['Доп. цвета']
    for type_and_params in good['addin']:
        if type_and_params['type'] == 'Наименование':
            name = type_and_params['params'][0]['value']
    for data in nomenclature_data['addin']:
        if data['type'] == 'Размер':
            size = data['params'][0]['value']
        if data['type'] == 'Доп. цвета':
            extra_colors = data['params'][0]['value']
    info = {
        'name': name,
        'article': article,
        'chrtId': chrtId,
        'size': size,
        'color': color,
        'extra_colors': extra_colors
    }
    return info


def add_information_about_barcodes_and_len(barcodes):
    for barcode in barcodes.keys():
        barcodes[barcode]['info'] = getting_information_about_barcode_by_chartId(
            barcodes[barcode]['chrtId'])
        barcodes[barcode]['info']['count'] = len(barcodes[barcode]['orders'])
    return barcodes


def create_db_for_checking(barcodes):
    barcodes_and_stickers = {}
    logging.info('Получение расшифрованных стикеров')
    for barcode in barcodes.keys():
        logging.info(f'Получение расшифрованных стикеров для {barcode}')
        barcodes_and_stickers[barcode] = {}
        arcticle = barcodes[barcode]['info']['article']
        name = barcodes[barcode]['info']['name']
        size = barcodes[barcode]['info']['size']
        color = barcodes[barcode]['info']['color']
        for order in barcodes[barcode]['orders']:
            sticker_encoded = get_StickerEncoded_by_orderId(order)
            barcodes_and_stickers[barcode][order] = {
                'sticker_encoded': sticker_encoded,
                'article': arcticle,
                'name': name[:40],
                'size': size,
                'color': color
            }

    book = openpyxl.Workbook()
    sheet = book.active
    sheet['A1'] = 'Номер заказа'
    sheet['B1'] = 'Артикул'
    sheet['C1'] = 'Наименование'
    sheet['D1'] = 'Баркод'
    sheet['E1'] = 'Stick'
    sheet['H1']= 'Баркод'
    sheet['I1']= 'Количество'

    row = 2
    row_for_counts = 2
    logging.info('Формирование xlsx файла')
    for barcode in barcodes_and_stickers.keys():
        barcode_info = barcodes_and_stickers[barcode]
        sheet[row_for_counts][7].value = str(barcode)
        sheet[row_for_counts][8].value = len(barcode_info.keys())
        row_for_counts += 1
        for order in barcode_info.keys():
            info = barcode_info[order]
            article = info['article']
            sticker_encoded = info['sticker_encoded']
            name = info['name']
            sheet[row][0].value = str(order)
            sheet[row][1].value = str(article)
            sheet[row][2].value = name
            sheet[row][3].value = str(barcode)
            sheet[row][4].value = sticker_encoded
            row += 1
        # article = barcodes_and_stickers[barcode]['article']
        # for order in barcodes_and_stickers[barcode]['orders']:
        #     sheet[row][0].value - str(order)
        #     sheet[row][1].value = str(article)
        #     sheet[row][2].value = str(barcode)
        #     sheet[row][3].value = order
        #     row += 1
    book.save('db_for_checking.xlsx')
    book.close()




def check_and_delete_orders_with_blank_officeAddress(orders):
    logging.info('Производится отчистка от заказов без адреса')
    for order in orders:
        if order['officeAddress'] == "":
            logging.info(f'Удален заказ {order["orderId"]}')
            orders.remove(order)
    logging.info(f'Осталось {len(orders)}')
    return orders

def set_status_to_orders(status, orders):
    url_for_set_status = 'https://suppliers-api.wildberries.ru/api/v2/orders'
    data_for_bulk_set_status = []
    for order in orders:
        data_for_bulk_set_status += [{
            "orderId": order["orderId"],
            "status": int(status)
        }]
    for order in orders:
        data_for_set_status = [{
            "orderId": order["orderId"],
            "status": int(status)
        }]
        js = json.dumps(data_for_set_status)
        response = requests.put(url_for_set_status, headers=headers, data=js)
        logging.info(response.content)

def get_barcodes_with_full_info(orders):
    barcodes = get_barcodes_with_orders_and_chartId(orders)
    barcodes = add_information_about_barcodes_and_len(barcodes)
    barcodes = sorted_barcodes_by_count_of_orders(barcodes)
    return barcodes


def create_stickers():
    orders = get_all_orders(status=1)
    # orders = check_and_delete_orders_with_blank_officeAddress(orders)
    orders = sorted(orders, key=lambda x: x['barcode'])
    barcodes = get_barcodes_with_full_info(orders)
    create_pdf_stickers_by_barcodes(barcodes)
    create_db_for_checking(barcodes)

def filter_orders_by_barcode(orders, barcode):
    filtered_barcodes = []
    for order in orders:
        if order['barcode'] == barcode:
            filtered_barcodes += [order]
    logging.info(f'Получено {len(filtered_barcodes)} заказов с баркодом = {barcode}')
    return filtered_barcodes


def sorted_barcodes_by_count_of_orders(barcodes):
    sorted_tuples = sorted(barcodes.items(), key=lambda x: len(x[1]['orders']), reverse=True)
    sorted_dict = {k: v for k, v in sorted_tuples}
    return sorted_dict

def set_status_collected_for_all_on_assembly():
    orders = get_all_orders(status=1)
    set_status_to_orders(2, orders)
    logging.info(f'{len(orders)} заказов переведены в собранные')

def sorted_by_barcode_set_status_on_assembly(barcode, limit):
    orders_with_status_1 = get_all_orders(status=1)
    if get_all_orders(status=1) != []:
        logging.info(f'На сборке находится {len(orders_with_status_1)} товаров со статусом "На сборке"')
        print(f"Нажмите enter, чтобы продолжить и добавить{limit-len(orders_with_status_1)} товаров")
        approve = input()
        limit = limit-len(orders_with_status_1)
        return 0
    orders = get_all_orders(status=0)
    orders = filter_orders_by_barcode(orders, barcode)[:limit]
    set_status_to_orders(1, orders)

def create_stickers_by_id(ids):
    date_end=get_now_time()
    orders = []
    for id in ids:
        date_start = '2021-11-06T00:47:17.528082+00:00'
        
        params = {
            'date_end': date_end,
            'date_start': date_start,
            'status': 2,
            'take': 100,
            'skip': 0,
            'id': id
        }
        response = requests.get(
            base_url_for_getting_orders,
            headers=headers,
            params=params)
        try:
            orders_from_current_response = response.json()['orders']
        except KeyError as e:
            logging.error(e, exc_info=True)
            print(id)
        orders += orders_from_current_response
        logging.info(f'Получено {len(orders)}')
    orders = sorted(orders, key=lambda x: x['barcode'])
    barcodes = get_barcodes_with_full_info(orders)
    create_pdf_stickers_by_barcodes(barcodes)
    create_db_for_checking(barcodes)

if __name__ == '__main__':
    # set_status_collected_for_all_on_assembly()
    # orders = get_all_orders(status=0)

    # orders = filter_orders_by_barcode(orders, '2000790297008')
    # print(len(orders))
    # barcodes = get_barcodes_with_full_info(orders)
    # print(barcodes)
    create_stickers()
