import datetime
import json
import pytz
import requests
import shutil
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
from requests.models import ReadTimeoutError
from dateutil import tz
from openpyxl.styles.borders import Border, Side


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(BASE_DIR, 'logs/')
log_file = os.path.join(BASE_DIR, 'logs/stickers.log')
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
    # return d.isoformat
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
today_prefix_path = os.path.join(
    pdf_path, datetime.datetime.today().strftime('%Y_%m_%d'))
create_path_if_not_exist(today_prefix_path)
today_path_with_name = os.path.join(today_prefix_path, NAME)
create_path_if_not_exist(today_path_with_name)
BACKUP_DIR = os.path.join(today_path_with_name, 'results/')
create_path_if_not_exist(BACKUP_DIR)


MEDIUM_BORDER = Border(left=Side(style='medium'),
                       right=Side(style='medium'),
                       top=Side(style='medium'),
                       bottom=Side(style='medium'))
THIN_BORDER = Border(left=Side(style='thin'),
                     right=Side(style='thin'),
                     top=Side(style='thin'),
                     bottom=Side(style='thin'))


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
        path = os.path.join(today_path_with_name, f'{id}.pdf')
        with open(path, 'wb') as f:
            f.write(codecs.decode(file_data, 'base64'))
        pdfs += [path]
    merger = PdfFileMerger()
    for pdf in pdfs:
        merger.append(pdf)
    merger.write("result2.pdf")
    merger.close()


def get_all_orders(status=0, date_end=get_now_time(), date_start='2021-11-06T00:47:17.528082+00:00'):
    logging.info(f'Получение всех заказов со статусом {status}')

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
        id = int(order['orderId'])
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
    for params in (count, name_of_host, name, size, color, extra_colors, article, chrtId):
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
            path = os.path.join(today_path_with_name, f'{id}.pdf')
            with open(path, 'wb') as f:
                f.write(codecs.decode(file_data, 'base64'))
            pdfs += [path]
        merger = PdfFileMerger()
        for pdf in pdfs:
            merger.append(pdf)
        path_for_result_of_barcode = os.path.join(
            today_path_with_name, f'result_{barcode}.pdf')
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
    add_results_file_to_today_backup('results.pdf')


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
    article_counts = {}
    for barcode in barcodes.keys():
        logging.info(f'Получение расшифрованных стикеров для {barcode}')
        barcodes_and_stickers[barcode] = {}
        arcticle = barcodes[barcode]['info']['article']
        name = barcodes[barcode]['info']['name']
        size = barcodes[barcode]['info']['size']
        color = barcodes[barcode]['info']['color']
        print(barcodes[barcode]['orders'])
        orders_and_sticker_encoded = get_orderId_and_sticker_encoded(
            barcodes[barcode]['orders'])
        print(orders_and_sticker_encoded)
        for order in barcodes[barcode]['orders']:
            sticker_encoded = orders_and_sticker_encoded[order]
            barcodes_and_stickers[barcode][order] = {
                'sticker_encoded': sticker_encoded,
                'article': arcticle,
                'name': name[:40],
                'size': size,
                'color': color
            }
            if not arcticle in article_counts:
                article_counts[arcticle] = 1
            else:
                article_counts[arcticle] += 1

    book = openpyxl.Workbook()
    sheet = book.active
    sheet['A1'] = 'Номер заказа'
    sheet['B1'] = 'Артикул'
    sheet['C1'] = 'Наименование'
    sheet['D1'] = 'Баркод'
    sheet['E1'] = 'Stick'

    sheet['H1'] = 'Артикул'
    sheet['I1'] = 'Количество'

    row = 2
    logging.info('Формирование xlsx файла')
    for barcode in barcodes_and_stickers.keys():
        barcode_info = barcodes_and_stickers[barcode]
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

    book.create_sheet("Sheet2")
    book.active = 1
    sheet = book.active
    # cell = sheet[2][8]
    # cell.value = f'=sfgsfdgsfdgsdfgSUM(I2:I{row-1})'
    sheet['A1'] = 'Артикул'
    sheet['A1'].border = THIN_BORDER
    sheet['B1'] = 'Количество'
    sheet['B1'].border = THIN_BORDER
    row = 2

    for article in article_counts.keys():
        cell = sheet.cell(row=row, column=1)
        cell.value = article
        cell.border = THIN_BORDER

        cell = sheet.cell(row=row, column=2)
        cell.value = article_counts[article]
        cell.border = THIN_BORDER
        row += 1
    cell = sheet.cell(row=row, column=1)
    cell.value = 'Сумма'
    cell.border = MEDIUM_BORDER

    cell = sheet.cell(row=row, column=2)
    cell.value = f'=SUM(B2:B{row-1})'
    cell.border = MEDIUM_BORDER
    book.save('db.xlsx')
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
    # # orders = check_and_delete_orders_with_blank_officeAddress(orders)
    if len(orders) == 0:
        return 0
    # orders = sorted(orders, key=lambda x: x['barcode'])
    # orders = [{'orderId': '122781838', 'dateCreated': '2021-11-15T15:17:59.781585Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 105208, 'officeAddress': 'г. Минск, Нёманская улица, д. 3', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 49128284, 'fio': 'Ерохова Софи ', 'phone': 375445626556}, 'chrtId': 47301927, 'barcode': '2000716391117', 'barcodes': ['2000716391117'], 'status': 1, 'userStatus': 4, 'rid': '300032806170', 'totalPrice': 119200, 'orderUID': '33564142053472337_6f35efb6172b4f31829736e919f810c0', 'deliveryType': 1}, {'orderId': '122628081', 'dateCreated': '2021-11-15T11:50:10.977447Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 103020, 'officeAddress': 'г. Ершов (Саратовская область), Калинина улица, д. 14', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 36211346, 'fio': 'Шохман Виктория Васильевна', 'phone': 79962668271}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429578873', 'totalPrice': 74000, 'orderUID': '27105673053466093_3760b85a04c841fba7095f46aee69498', 'deliveryType': 1}, {'orderId': '122629163', 'dateCreated': '2021-11-15T11:51:44.990127Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 101816, 'officeAddress': 'г. Светлоград (Ставропольский край), Выставочная площадь, д. 8А', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 21141322, 'fio': 'Надоленская Екатерина Анатольевна', 'phone': 79887373561}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429584281', 'totalPrice': 74000, 'orderUID': '19570661053466151_c7886ca43fd643e8a0637dcd0ae99e9b', 'deliveryType': 1}, {'orderId': '122632289', 'dateCreated': '2021-11-15T11:56:00.336669Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 17533, 'officeAddress': 'г. Минеральные Воды (Ставропольский край), улица 50 лет Октября, д. 51', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 23705659, 'fio': 'Сафронова Екатерина Владимировна', 'phone': 79289558635}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '51010909603', 'totalPrice': 74000, 'orderUID': '20852829553466279_947a5cfe80d64b09ad87c5d140ae9acb', 'deliveryType': 1}, {'orderId': '122636095', 'dateCreated': '2021-11-15T12:01:25.042171Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 13593, 'officeAddress': 'г. Благовещенск (Амурская область), Амурская улица, д. 230', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 5652279, 'fio': 'Шаруда Татьяна Николаевна', 'phone': 79140619074}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429611018', 'totalPrice': 85100, 'orderUID': '11826139553466430_0c70ee11e57f4bf1b8e97f4df05c6836', 'deliveryType': 1}, {'orderId': '122636702', 'dateCreated': '2021-11-15T12:02:15.182189Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 0, 'officeAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddressDetails': {'province': 'Республика Хакасия', 'area': 'Таштыпский район', 'city': 'село Таштып', 'street': 'улица Луначарского', 'home': '1', 'flat': '20', 'entrance': '2', 'longitude': 89.887835, 'latitude': 52.800433}, 'userInfo': {'userId': 44171800, 'fio': 'Султрекова Владлена Александровна', 'phone': 79833771263}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429613160', 'totalPrice': 74000, 'orderUID': '31085900053466455_d7530eb8638e4807b5e38b8c8cccee4f', 'deliveryType': 1}, {'orderId': '122636713', 'dateCreated': '2021-11-15T12:02:15.185581Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 0, 'officeAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddressDetails': {'province': 'Республика Хакасия', 'area': 'Таштыпский район', 'city': 'село Таштып', 'street': 'улица Луначарского', 'home': '1', 'flat': '20', 'entrance': '2', 'longitude': 89.887835, 'latitude': 52.800433}, 'userInfo': {'userId': 44171800, 'fio': 'Султрекова Владлена Александровна', 'phone': 79833771263}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429613162', 'totalPrice': 74000, 'orderUID': '31085900053466455_d7530eb8638e4807b5e38b8c8cccee4f', 'deliveryType': 1}, {'orderId': '122636712', 'dateCreated': '2021-11-15T12:02:15.225256Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 0, 'officeAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddressDetails': {'province': 'Республика Хакасия', 'area': 'Таштыпский район', 'city': 'село Таштып', 'street': 'улица Луначарского', 'home': '1', 'flat': '20', 'entrance': '2', 'longitude': 89.887835, 'latitude': 52.800433}, 'userInfo': {'userId': 44171800, 'fio': 'Султрекова Владлена Александровна', 'phone': 79833771263}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429613161', 'totalPrice': 74000, 'orderUID': '31085900053466455_d7530eb8638e4807b5e38b8c8cccee4f', 'deliveryType': 1}, {'orderId': '122636714', 'dateCreated': '2021-11-15T12:02:15.226511Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 0, 'officeAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddressDetails': {'province': 'Республика Хакасия', 'area': 'Таштыпский район', 'city': 'село Таштып', 'street': 'улица Луначарского', 'home': '1', 'flat': '20', 'entrance': '2', 'longitude': 89.887835, 'latitude': 52.800433}, 'userInfo': {'userId': 44171800, 'fio': 'Султрекова Владлена Александровна', 'phone': 79833771263}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429613159', 'totalPrice': 74000, 'orderUID': '31085900053466455_d7530eb8638e4807b5e38b8c8cccee4f', 'deliveryType': 1}, {'orderId': '122637253', 'dateCreated': '2021-11-15T12:03:09.553869Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 13593, 'officeAddress': 'г. Благовещенск (Амурская область), Амурская улица, д. 230', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 5652279, 'fio': 'Шаруда Татьяна Николаевна', 'phone': 79140619074}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429615599', 'totalPrice': 85100, 'orderUID': '11826139553466480_e62a90a5e8604316b5baf88998e25d6a', 'deliveryType': 1}, {'orderId': '122639643', 'dateCreated': '2021-11-15T12:06:25.053558Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 16642, 'officeAddress': 'г. Ульяновск (Ульяновская область), улица Шолмова, д. 37А', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 33549544, 'fio': 'Чижова Светлана Юрьевна', 'phone': 79278258162}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429621668', 'totalPrice': 74000, 'orderUID': '25774772053466543_111fcebda91d4446a32075d017d3615f', 'deliveryType': 1}, {'orderId': '122639642', 'dateCreated': '2021-11-15T12:06:25.053652Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 16642, 'officeAddress': 'г. Ульяновск (Ульяновская область), улица Шолмова, д. 37А', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 33549544, 'fio': 'Чижова Светлана Юрьевна', 'phone': 79278258162}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429621667', 'totalPrice': 74000, 'orderUID': '25774772053466543_111fcebda91d4446a32075d017d3615f', 'deliveryType': 1}]
    barcodes = get_barcodes_with_full_info(orders)
    # barcodes ={'2000790297008': {'orders': ['122628081', '122629163', '122632289', '122636095', '122636702', '122636713', '122636712', '122636714', '122637253', '122639643', '122639642', '122640444', '122640758', '122640759', '122641754', '122644303', '122644515', '122644956', '122645914', '122652587', '122656444', '122658597', '122661646', '122663132', '122663133', '122663335', '122664895', '122668224', '122668299', '122670492', '122675725', '122678619', '122681097', '122685607', '122689262', '122691238', '122693612', '122695099', '122698458', '122700706', '122701984', '122701992', '122701994', '122706147', '122708529', '122713702', '122716251', '122726002', '122731460', '122732755', '122733869', '122734078', '122734076', '122735939', '122736645', '122741109', '122741623', '122741636', '122743040', '122746899', '122750079', '122751643', '122752454', '122756573', '122760112', '122760175', '122767333', '122776811', '122777297', '122777366', '122779075', '122779613', '122781919', '122781920', '122781932', '122781962', '122782477', '122786703', '122788824', '122789846', '122790109', '122791052', '122791504', '122793887', '122795874', '122798102', '122798500', '122804948', '122804947', '122808350', '122808723', '122808814', '122808813', '122809629', '122810248', '122813658', '122818911', '122820995', '122823291', '122823292', '122823385', '122824137', '122827321', '122830683', '122831997', '122835274', '122836161', '122840467', '122845120', '122848995', '122850040', '122850172', '122853088', '122853211', '122856949', '122862452', '122862728', '122862917', '122866601', '122868515', '122868618', '122874027', '122876351', '122880308', '122880687', '122881159', '122881480', '122884131', '122885552', '122885914', '122885931', '122889470', '122889794', '122890369', '122892798', '122901848', '122904262', '122906384', '122908092', '122909595', '122910602', '122917075', '122926658', '122928104', '122928191', '122928488', '122928673', '122937170', '122939952', '122940670', '122942675', '122944367', '122944625', '122952119', '122953945', '122954945', '122957197', '122957417', '122962507', '122962511', '122962783', '122965300', '122973526', '122974106', '122976722', '122978395', '122980969', '122983750', '122988365', '122989374', '122989392', '122991264', '122995056', '123001596', '123001781', '123004435', '123010522', '123010535', '123010578', '123011199', '123014638', '123014640', '123014639', '123019170', '123019555', '123019596', '123020693', '123024637', '123025070', '123026063', '123028439', '123030495', '123030502', '123035260', '123035970', '123036061', '123037476'], 'chrtId': 48115318, 'info': {'name': 'Гирлянда дождик 3х2 метра / Новогодняя / Гирлянда 3 х 2 метра  на окно диодная / Гирлянда штора 3x2', 'article': 'WR00040', 'chrtId': 48115318, 'size': '', 'color': 'белый', 'extra_colors': '', 'count': 197}}, '2006812643006': {'orders': ['122626290', '122629894', '122631937', '122639710', '122653023', '122656256', '122658448', '122659711', '122672197', '122680872', '122691446', '122691561', '122691836', '122697516', '122703098', '122721360', '122724816', '122731194', '122741948', '122747343', '122758275', '122762843', '122778107', '122782594', '122784759', '122785613', '122798822', '122803065', '122803537', '122803539', '122805164', '122807733', '122807976', '122808312', '122808801', '122809554', '122809923', '122810190', '122810940', '122811450', '122813294', '122822196', '122822634', '122823739', '122829129', '122832099', '122839003', '122855857', '122857438', '122859251', '122861620', '122863370', '122864194', '122864601', '122867046', '122872491', '122873446', '122875582', '122877487', '122879674', '122880511', '122880512', '122883245', '122891498', '122894212', '122915887', '122922747', '122924816', '122933475', '122942237', '122945240', '122945333', '122948662', '122949322', '122952308', '122954675', '122965485', '122969882', '122970486', '122971813', '122977577', '122980449', '122981863', '122982467', '122983659', '122985531', '122988020', '122991595', '122992200', '122996609', '123000911', '123002720', '123008557', '123009199', '123012524', '123012525', '123028599', '123029503'], 'chrtId': 77673393, 'info': {'name': 'Гирлянда дождик 3х2 метра / Новогодняя / Гирлянда 3 х 2 метра  на окно диодная / Гирлянда штора 3x2', 'article': 'WR00040/01', 'chrtId': 77673393, 'size': '', 'color': 'желтый', 'extra_colors': '', 'count': 98}}, '2000790373009': {'orders': ['122670493', '122697524', '122703000', '122703003', '122702999', '122716076', '122716081', '122736195', '122741575', '122776570', '122792749', '122821155', '122837608', '122845116', '122862986', '122875636', '122875634', '122878580', '122883098', '122907122', '122910596', '122910604', '122912863', '122936634', '122953817', '122956434', '122956435', '122956443', '122963083', '122981406', '123001776', '123010519', '123012248'], 'chrtId': 48115295, 'info': {'name': 'Удлинитель для гирлянды 3м / 5 м прозрачный / гирлянда / новогодняя', 'article': 'WR00041', 'chrtId': 48115295, 'size': '', 'color': 'прозрачный', 'extra_colors': '', 'count': 33}}, '2008656836002': {'orders': ['122655104', '122690559', '122707886', '122737583', '122769939', '122777947', '122781942', '122784971', '122803500', '122822426', '122823646', '122825483', '122825480', '122825482', '122825487', '122825485', '122825484', '122844738', '122919861', '122942054', '123009250', '123012244', '123029154', '123032977', '123035033', '123038899'], 'chrtId': 83547212, 'info': {'name': 'Гирлянда дождик 3х2 метра / Новогодняя / Гирлянда 3 х 2 метра  на окно диодная / Гирлянда штора 3x2', 'article': 'WR00040/02', 'chrtId': 83547212, 'size': '', 'color': 'синий', 'extra_colors': '', 'count': 26}}, '2010832565002': {'orders': ['122635867', '122643983', '122684800', '122767327', '122780462', '122813132', '122818328', '122838779', '122909154', '122912694', '122954650', '123005047'], 'chrtId': 87613757, 'info': {'name': 'Гирлянда дождик 3х2 метра / Новогодняя / Гирлянда 3 х 2 метра  на окно диодная / Гирлянда штора 3x2', 'article': 'WR00040/03', 'chrtId': 87613757, 'size': '', 'color': 'зеленый', 'extra_colors': 'синий красный желтый ', 'count': 12}}, '2013112852007': {'orders': ['122667879', '122718905', '122794373', '122808927', '122912778', '122956437', '122956432', '122985530', '123006959', '123020937', '123020935', '123020936'], 'chrtId': 91293224, 'info': {'name': 'Удлинитель для гирлянды 3м / 5 м прозрачный / гирлянда / новогодняя', 'article': 'WR00041/02', 'chrtId': 91293224, 'size': '', 'color': 'прозрачный', 'extra_colors': '', 'count': 12}}, '2011585978002': {'orders': ['122645414', '122652462', '122705300', '122710797', '122711294', '122779144', '122788802', '122839869', '122862994', '122994694', '123038149'], 'chrtId': 89187842, 'info': {'name': 'Гирлянда дождик 3х2 метра / Новогодняя / Гирлянда 3 х 2 метра  на окно диодная / Гирлянда штора 3x2', 'article': 'WR00040/04', 'chrtId': 89187842, 'size': '', 'color': 'белый матовый', 'extra_colors': '', 'count': 11}}, '2007202830006': {'orders': ['122712610', '122877488', '122886877', '122959299', '123011198'], 'chrtId': 78897038, 'info': {'name': 'Удлинитель для гирлянды 3м / 5 м прозрачный / гирлянда / новогодняя', 'article': 'WR00041/01', 'chrtId': 78897038, 'size': '', 'color': 'белый', 'extra_colors': '', 'count': 5}}, '2008544074004': {'orders': ['122643495', '122643496', '122660763', '122837338', '122941927'], 'chrtId': 83129511, 'info': {'name': 'Крючки для штор', 'article': 'WR00090', 'chrtId': 83129511, 'size': '', 'color': 'прозрачный', 'extra_colors': '', 'count': 5}}, '2013113023000': {'orders': ['122750093', '122750201', '122954009'], 'chrtId': 91293868, 'info': {'name': 'Крючки для штор', 'article': 'WR00090/01', 'chrtId': 91293868, 'size': '', 'color': '', 'extra_colors': '', 'count': 3}}, '2008345110000': {'orders': ['122910284', '122910292'], 'chrtId': 82428947, 'info': {'name': 'Гирлянда новогодняя / занавес / на окно / светодиодная / 3 на 2 / штора', 'article': 'NY00088/01', 'chrtId': 82428947, 'size': '', 'color': 'белый', 'extra_colors': '', 'count': 2}}, '2013113218000': {'orders': ['122683980', '122966799'], 'chrtId': 91294010, 'info': {'name': 'Крючки для штор', 'article': 'NY00091/01', 'chrtId': 91294010, 'size': '', 'color': '', 'extra_colors': '', 'count': 2}}, '2000716391117': {'orders': ['122781838'], 'chrtId': 47301927, 'info': {'name': 'Сумка женская / шоппер / чёрная вместительная / для документов / городская / стильная', 'article': 'G00012', 'chrtId': 47301927, 'size': '', 'color': 'черный', 'extra_colors': '', 'count': 1}}, '2008345511005': {'orders': ['122911393'], 'chrtId': 82429973, 'info': {'name': 'Гирлянда новогодняя / занавес / на окно / светодиодная / 3 на 2 / штора', 'article': 'NY00088/03', 'chrtId': 82429973, 'size': '', 'color': 'желтый', 'extra_colors': '', 'count': 1}}, '2008346989001': {'orders': ['122870865'], 'chrtId': 82437687, 'info': {'name': 'Гирлянда новогодняя / занавес / на окно / светодиодная / 3 на 2 / штора', 'article': 'NY00088/02', 'chrtId': 82437687, 'size': '', 'color': 'зеленый', 'extra_colors': 'желтый ', 'count': 1}}, '2008545360007': {'orders': ['122822648'], 'chrtId': 83134431, 'info': {'name': 'Крючки для штор', 'article': 'NY00091', 'chrtId': 83134431, 'size': '', 'color': 'прозрачный', 'extra_colors': '', 'count': 1}}}
    create_pdf_stickers_by_barcodes(barcodes)
    create_db_for_checking(barcodes)
    return len(orders)


def filter_orders_by_barcode(orders, barcode):
    filtered_barcodes = []
    for order in orders:
        if order['barcode'] == barcode:
            filtered_barcodes += [order]
    logging.info(
        f'Получено {len(filtered_barcodes)} заказов с баркодом = {barcode}')
    return filtered_barcodes


def sorted_barcodes_by_count_of_orders(barcodes):
    sorted_tuples = sorted(barcodes.items(), key=lambda x: len(
        x[1]['orders']), reverse=True)
    sorted_dict = {k: v for k, v in sorted_tuples}
    return sorted_dict


def set_status_collected_for_all_on_assembly():
    orders = get_all_orders(status=1)
    set_status_to_orders(2, orders)
    logging.info(f'{len(orders)} заказов переведены в собранные')


def sorted_by_barcode_set_status_on_assembly(barcode, limit):
    orders_with_status_1 = get_all_orders(status=1)
    if get_all_orders(status=1) != []:
        logging.info(
            f'На сборке находится {len(orders_with_status_1)} товаров со статусом "На сборке"')
        print(
            f"Нажмите enter, чтобы продолжить и добавить{limit-len(orders_with_status_1)} товаров")
        approve = input()
        limit = limit-len(orders_with_status_1)
        return 0
    orders = get_all_orders(status=0)
    orders = filter_orders_by_barcode(orders, barcode)[:limit]
    set_status_to_orders(1, orders)


def create_stickers_by_id(ids):
    date_end = get_now_time()
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


def get_start_and_end_of_current_day():
    tz2 = pytz.timezone('Europe/Moscow')
    today = datetime.datetime.utcnow().date() - datetime.timedelta(1)
    start = datetime.datetime(today.year, today.month,
                              today.day, tzinfo=tz.tzutc()).astimezone(tz2)
    end = start + datetime.timedelta(1)
    return (start.replace(tzinfo=pytz.UTC).isoformat(), end.replace(tzinfo=pytz.UTC).isoformat())


def add_results_file_to_today_backup(path_to_results_file):
    filename = 'results_%s.pdf' % datetime.datetime.now().strftime('%H%M')
    path_to_backup_file = os.path.join(BACKUP_DIR, filename)
    shutil.copyfile(path_to_results_file, path_to_backup_file)


def get_list_of_relative_path_to_all_today_results():
    list_of_files = []
    for root, directories, file in os.walk(BACKUP_DIR):
        for file in file:
            list_of_files.append(os.path.relpath((os.path.join(root, file))))
    return list_of_files


def get_list_of_relative_path_to_all_logs():
    list_of_files = []
    for root, directories, file in os.walk(log_dir):
        for file in file:
            list_of_files.append(os.path.relpath((os.path.join(root, file))))
    return list_of_files


def get_orderId_and_sticker_encoded(ids):
    url = 'https://suppliers-api.wildberries.ru/api/v2/orders/stickers'
    json_order_id = {
        "orderIds": ids
    }
    response = requests.post(
        url,
        json=json_order_id,
        headers=headers)
    order_and_sticker_encoded = {}
    print(response.content.decode('utf-8'))
    for order in response.json()['data']:
        order_and_sticker_encoded[order['orderId']
                                  ] = order['sticker']['wbStickerEncoded']
    return order_and_sticker_encoded
    # return response.json()['data'][0]['sticker']['wbStickerEncoded']


if __name__ == '__main__':
    create_stickers()