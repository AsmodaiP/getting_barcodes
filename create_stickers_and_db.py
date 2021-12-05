import datetime
import json
from sys import path
from openpyxl.styles.fills import PatternFill
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
from openpyxl.formula.translate import Translator
from requests.models import ReadTimeoutError
from dateutil import tz
from openpyxl.styles.borders import Border, Side
import sys
from openpyxl.styles import Protection, Font, Fill
from openpyxl.formatting import Rule
from openpyxl.styles.differential import DifferentialStyle
from openpyxl.formatting.rule import CellIsRule
from openpyxl.formatting.rule import ColorScaleRule, CellIsRule, FormulaRule
pdfmetrics.registerFont(TTFont('FreeSans', 'fonts/FreeSans.ttf'))
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

def create_all_today_path():
    pdf_path = os.path.join(BASE_DIR, 'pdf/')
    create_path_if_not_exist(pdf_path)
    today_prefix_path = os.path.join(
        pdf_path, datetime.datetime.today().strftime('%Y_%m_%d'))
    create_path_if_not_exist(today_prefix_path)
    today_path_with_name = os.path.join(today_prefix_path, NAME)
    create_path_if_not_exist(today_path_with_name)
    backup_dir = os.path.join(today_path_with_name, 'results/')
    json_dir = os.path.join(today_path_with_name, 'json/')
    create_path_if_not_exist(backup_dir)
    create_path_if_not_exist(json_dir)
    return {
        'backup_dir': backup_dir,
        'json_dir': json_dir,
        'today_prefix_path': today_prefix_path,
        'today_path_with_name':today_path_with_name
    }




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
        today_path_with_name = create_all_today_path()['today_path_with_name']
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
    date_end=get_now_time()
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
        # for id in barcodes_and_ids[barcode]['orders']:
        #     json_orders_id = {
        #         "orderIds": [int(id)]
        #     }
        #     response = requests.post(
        #         url_for_getting_stikers,
        #         json=json_orders_id,
        #         headers=headers)
        #     data_for_pdf = response.json()['data']['file']
        #     file_data = bytes(data_for_pdf, 'utf-8')
        #     today_path_with_name = create_all_today_path()['today_path_with_name']
        #     path = os.path.join(today_path_with_name, f'{id}.pdf')
        #     with open(path, 'wb') as f:
        #         f.write(codecs.decode(file_data, 'base64'))
        #     pdfs += [path]
        merger = PdfFileMerger()
        orders = barcodes_and_ids[barcode]['orders']
        json_orders_id = {
            "orderIds": orders
        }
        response = requests.post(
                url_for_getting_stikers,
                json=json_orders_id,
                headers=headers)
        data_for_pdf = response.json()['data']['file']
        file_data = bytes(data_for_pdf, 'utf-8')
        today_path_with_name = create_all_today_path()['today_path_with_name']
        path = os.path.join(today_path_with_name, f'{barcode}.pdf')
        with open(path, 'wb') as f:
            f.write(codecs.decode(file_data, 'base64'))
        pdfs += [path]
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
        orders_and_sticker_encoded = get_orderId_and_sticker_encoded(
            barcodes[barcode]['orders'])
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
    book.create_sheet("Итог")
    book.create_sheet('Проверка')
    sheet['A1'] = 'Номер заказа'
    sheet['B1'] = 'Артикул'
    sheet['C1'] = 'Наименование'
    sheet['D1'] = 'Баркод'
    sheet['E1'] = 'Stick'
    sheet.protection.sheet=True
    sheet.protection.set_password('osdfjl2')
    sheet.protection.enable()

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
            sheet[f'K{row}'] = f'=IF(ISERROR(MATCH(J{row+1},L{row},0)),"",TRUE)'
            sheet[f'L{row}'] = f'=IF(ISERROR(INDEX(D:D,MATCH(J{row},E:E,0),1)),"",INDEX(D:D,MATCH(J{row},E:E,0),1))'
            row += 1

    # book.create_sheet("Итог")
    book.active = 1                                                     
    sheet = book.active
    sheet['A1'] = 'Артикул'
    sheet['A1'].border = THIN_BORDER
    sheet['B1'] = 'Количество'
    sheet['B1'].border = THIN_BORDER
    sheet['C1'] = 'Собрано'
    sheet['B1'].border = THIN_BORDER
    row = 2
    sheet.protection.sheet=True
    sheet.protection.set_password('osdfjl2')
    sheet.protection.enable()
    for article in article_counts.keys():
        cell = sheet.cell(row=row, column=1)
        cell.value = article
        cell.border = THIN_BORDER

        cell = sheet.cell(row=row, column=2)
        cell.value = article_counts[article]
        cell.border = THIN_BORDER

        cell = sheet.cell(row=row, column=3)
        cell.value = f'=COUNTIF(Проверка!D:D,A{row})'
        cell.border = THIN_BORDER
        row += 1
    cell = sheet.cell(row=row, column=1)
    cell.value = 'Сумма'
    cell.border = MEDIUM_BORDER

    cell = sheet.cell(row=row, column=2)
    cell.value = f'=SUM(B2:B{row-1})'
    cell.border = MEDIUM_BORDER
    cell = sheet.cell(row=row, column=3)
    cell.value = f'=SUM(C2:C{row-1})'
    cell.border = THIN_BORDER
    
    green_fill=PatternFill(bgColor="a0db8e")
    sheet.conditional_formatting.add('C1:C3000',FormulaRule(formula=['IF(AND(C1=B1, C1<>""),True,False)'], stopIfTrue=True, fill=green_fill))
 
    book.active = 2
    sheet = book.active
    red_fill = PatternFill(bgColor="FFC7CE")

    sheet.conditional_formatting.add('B1:B3000',FormulaRule(formula=['IF(B1="Ошибка",True,False)'], stopIfTrue=True, fill=red_fill))

    row = 2
    sheet['A1'] = 'Данные'
    sheet['B1'] = 'Результат'
    sheet['D1'] = 'Артикул'
    sheet.protection.sheet=True
    sheet.protection.enable()
    for barcode in barcodes_and_stickers.keys():
        barcode_info = barcodes_and_stickers[barcode]
        for order in barcode_info.keys():
            for i in range(2):
                if row % 2 == 0: 
                    # =IF(AND(ISERROR(MATCH(A3,C2,0)),A2<>"",A3<>""),"Ошибка","")
                    sheet[f'B{row}'] = f'=IF(AND(ISERROR(MATCH(A{row+1},C{row},0)),A{row}<>"",A{row+1}<>""),"Ошибка","")'
                    sheet[f'C{row}'] = f'=IF(ISERROR(INDEX(Sheet!D:D,MATCH(A{row},Sheet!E:E,0),1)),"",INDEX(Sheet!D:D,MATCH(A{row},Sheet!E:E,0),1))'
                else:
                    sheet[f'D{row}'] = f'=IF(AND(B{row-1}<>"Ошибка", A{row-1}<>""),INDEX(Sheet!B:B, MATCH(A{row},Sheet!D:D,0),1), "")'
                sheet[f'A{row}'].number_format = '@'
                sheet[f'A{row}'].protection = Protection(locked=False)
                row += 1
    for column in ['C', 'D']:
        for cell in sheet[column]:
            cell.font= Font(color='Ffffffff')
    book.save('db.xlsx')
    book.close()


def check_and_delete_orders_with_blank_officeAddress(orders):
    logging.info('Производится отчистка от заказов без адреса')
    count = 0 
    for order in orders:
        if order['officeAddress'] == "":
            count += 1
            # logging.info(f'Удален заказ {order["orderId"]}')
            orders.remove(order)
    # logging.info(f'Осталось {len(orders)}')

    return (orders, count)


def set_status_to_orders_by_ids(status, ids):
    url_for_set_status = 'https://suppliers-api.wildberries.ru/api/v2/orders'
    data_for_bulk_set_status = []
    
    for id in ids:
        data_for_bulk_set_status += [{
            "orderId": str(id),
            "status": int(status)
        }]
        
        # response = requests.put(url_for_set_status, headers=headers, data=js)
        # print(response.content)
    js = json.dumps(data_for_bulk_set_status)
    response = requests.put(url_for_set_status, headers=headers, data=js)
    # for ord

def set_status_to_orders(status, orders):
    url_for_set_status = 'https://suppliers-api.wildberries.ru/api/v2/orders'
    data_for_bulk_set_status = []
    for order in orders:
        data_for_bulk_set_status += [{
            "orderId": order["orderId"],
            "status": int(status)
        }]
    # for order in orders:
    #     data_for_set_status = [{
    #         "orderId": order["orderId"],
    #         "status": int(status)
    #     }]
    js = json.dumps(data_for_bulk_set_status)
    response = requests.put(url_for_set_status, headers=headers, data=js)


def get_barcodes_with_full_info(orders):
    barcodes = get_barcodes_with_orders_and_chartId(orders)
    barcodes = add_information_about_barcodes_and_len(barcodes)
    barcodes = sorted_barcodes_by_count_of_orders(barcodes)
    return barcodes


def create_stickers():
    orders = get_all_orders(status=1)
    if len(orders) == 0:
        return (0,0)
    barcodes = get_barcodes_with_full_info(orders)
    with open('barcodes.json','w', encoding='utf-8') as f:
        json.dump(barcodes, f,ensure_ascii=False)
    add_json_file_to_today_json('barcodes.json')
    create_pdf_stickers_by_barcodes(barcodes)
    return (len(orders), barcodes)


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
    return len(orders)


def sorted_by_barcode_set_status_on_assembly(barcode, limit):
    # orders_with_status_1 = get_all_orders(status=1)
    # if get_all_orders(status=1) != []:
    #     limit = limit-len(orders_with_status_1)
    #     return 0
    orders = get_all_orders(status=0)
    orders = filter_orders_by_barcode(orders, barcode)[:limit]
    print(orders)
    print(len(orders))
    set_status_to_orders(1, orders)

def set_status_on_assmebly_by_limit_and_date(limit=350):
    orders = get_all_orders(status=0)
    orders = orders[-limit:]
    set_status_to_orders(1, orders)

def set_status_on_assmebly_by_limit(limit=350):
    orders = get_all_orders(status=0)
    orders = orders[:limit]
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

def add_json_file_to_today_json(path_to_json_file):
    json_dir = create_all_today_path()['json_dir']
    filename = 'barcodes_%s.json' % datetime.datetime.now().strftime('%H%M')
    path_to_backup_file = os.path.join(json_dir, filename)
    shutil.copyfile(path_to_json_file, path_to_backup_file)

def add_results_file_to_today_backup(path_to_results_file):
    backup_dir = create_all_today_path()['backup_dir']
    filename = 'results_%s.pdf' % datetime.datetime.now().strftime('%H%M')
    path_to_backup_file = os.path.join(backup_dir, filename)
    shutil.copyfile(path_to_results_file, path_to_backup_file)


def get_list_of_relative_path_to_all_today_results():
    list_of_files = []
    backup_dir = create_all_today_path()['backup_dir']
    for root, directories, file in os.walk(backup_dir):
        for file in file:
            list_of_files.append(os.path.relpath((os.path.join(root, file))))
    return list_of_files

def get_list_of_relative_path_to_all_today_json():
    list_of_files = []
    json_dir = create_all_today_path()['json_dir']
    for root, directories, files in os.walk(json_dir):
        for file in files:
            if file != 'result_fbs.json':
                list_of_files.append(os.path.relpath((os.path.join(root, file))))
    return list_of_files

def get_list_of_relative_path_to_all_logs():
    list_of_files = []
    for root, directories, file in os.walk(log_dir):
        for file in file:
            list_of_files.append(os.path.relpath((os.path.join(root, file))))
    return list_of_files


def get_dict_of_unique_orders_and_article():
    list_of_json = get_list_of_relative_path_to_all_today_json()
    order_and_article_dict = {}
    for json_path in list_of_json:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for barcode in data.keys():
                orders = data[barcode]['orders']
                # print(orders)
                for order in orders:
                    order_and_article_dict[order] = data[barcode]['info']['article']
    return order_and_article_dict

def get_today_article_and_count():
    orders_and_article = get_dict_of_unique_orders_and_article()
    article_and_count = {}
    for order in orders_and_article.keys():
        article = orders_and_article[order]
        if not article in article_and_count:
            article_and_count[article] = 1
        else:
            article_and_count[article] += 1
    return article_and_count


def create_finall_table_of_day():
    logging.info('Получение артикулов и количества заказов для них')
    article_and_count = get_today_article_and_count()
    json_dir = create_all_today_path()['json_dir']
    path_for_saving_aricle_and_count_dict = os.path.join(json_dir,'result_fbs.json')
    with open(path_for_saving_aricle_and_count_dict, 'w') as f:
        json.dump(article_and_count, f)
    book = openpyxl.Workbook()
    sheet = book.active
    sheet['A1'] = 'Артикул'
    sheet['A1'].border = THIN_BORDER
    sheet['B1'] = 'Количество'
    sheet['B1'].border = THIN_BORDER
    row = 2
    for article in article_and_count.keys():
        cell = sheet.cell(row=row, column=1)
        cell.value = article
        cell.border = THIN_BORDER

        cell = sheet.cell(row=row, column=2)
        cell.value = article_and_count[article]
        cell.border = THIN_BORDER
        row += 1
    cell = sheet.cell(row=row, column=1)
    cell.value = 'Сумма'
    cell.border = MEDIUM_BORDER

    cell = sheet.cell(row=row, column=2)
    cell.value = f'=SUM(B2:B{row-1})'
    cell.border = MEDIUM_BORDER
    today_path_with_name = create_all_today_path()['today_path_with_name']
    file_path = os.path.join(today_path_with_name, 'final_bd.xlsx')
    book.save(file_path)
    book.close()
    return file_path

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
    for order in response.json()['data']:
        order_and_sticker_encoded[order['orderId']
                                  ] = order['sticker']['wbStickerEncoded']
    return order_and_sticker_encoded

def filter_orders_by_article(articles, count):
    orders = get_all_orders(status=0)
    barcodes = get_barcodes_with_full_info(orders)
    filtered_orders = []
    for barcode in barcodes: 
        if (barcodes[barcode]['info']['article'] in articles) and (len(filtered_orders) <= count):
            filtered_orders += barcodes[barcode]['orders']
    return filtered_orders[:count]

# def set_status_on_assembly_by_article_and_limit(article, limit):
#     orders = filter_orders_by_article(article)
#     set_status_to_orders(1, orders)

def swap_token_by_name(name):
    global TOKEN
    cred = json.load(open('credentials.json', 'rb'))
    global NAME
    TOKEN = cred[name]['token']
    NAME = cred[name]['name']
    global headers
    headers = {
        'Authorization': TOKEN,
    }
    create_all_today_path()

def get_name():
    return NAME

if __name__ == '__main__':
    swap_token_by_name('БелотеловАГ')
    blacklist=[
        138455171,
138457541,
138460357,
138473645,
138500139,
138500134,
138500716,
138501542,
138507376,
138520222,
138522217,
138527329,
138531535,
138536231,
138549122,
138575639,
138586056,
138594351,
138596418,
138609844,
138612350,
138637307,
138639836,
138644986,
138665385,
138672205,
138673940,
138677130,
138677345,
138677654,
138678296,
138685019,
138706938,
138713466,
138729496,
138730355,
138750405,
138762234,
138775117,
138799167,
138799158,
138817930,
138818371,
138820035,
138833465,
138853066,
138862400,
138865136,
138866761,
138867971,
138878020,
138888949,
138893684,
138900118,
138901336,
138916746,
138919278,
138921736,
138941898,
138946042,
138946035,
138971785,
138971788,
138980787,
139003645,
139026849,
139031458,
139042500,
139042664,
139047569,
139051473,
139066012,
139066428,
139070351,
139088058,
139097675,
139098407,
139099178,
139102086,
139110869,
139131801,
139136970,
139136986,
139136990,
139140877,
139142542,
139151927,
139158363,
139162008,
139181208,
139185728,
139216245,
139232480,
139243786,
139266514,
139270680,
138462887,
138465989,
138478181,
138514210,
138521023,
138534332,
138539281,
138555282,
138564928,
138572104,
138578125,
138579354,
138599040,
138612774,
138621543,
138622088,
138631010,
138643441,
138649247,
138661800,
138666099,
138667813,
138692210,
138698690,
138706246,
138724447,
138745162,
138758861,
138758873,
138759932,
138759931,
138764782,
138774985,
138776961,
138776951,
138783963,
138785280,
138826202,
138842157,
138869466,
138871745,
138876455,
138877370,
138883825,
138896126,
138903365,
138919873,
138937871,
138938250,
138939266,
138982541,
139051678,
139055343,
139055805,
139062049,
139063903,
139073710,
139104764,
139139598,
139141082,
139142308,
139230445,
139245332,
139253781,
139257333,
139269907,
138461699,
138466757,
138478082,
138549377,
138555533,
138580784,
138606885,
138617343,
138631632,
138632027,
138680801,
138681489,
138709499,
138711442,
138719467,
138723564,
138819400,
138850209,
138856528,
138878166,
138885438,
138989758,
139025425,
139090688,
139106808,
139137847,
139161129,
139161172,
139161926,
139235244,
139235241,
139252768,
139256617,
139258434,
139262769,
138489121,
138524082,
138524083,
138524084,
138524087,
138567801,
138571098,
138607718,
138607731,
138638998,
138643553,
138643717,
138687816,
138694997,
138701773,
138702754,
138808239,
138816420,
138867591,
138871702,
138937345,
138937356,
138958957,
139023738,
139055647,
139055643,
139056082,
139059388,
139124855,
139124850,
139237420,
139257881,
139261303,
138564696,
138565970,
138595610,
138595615,
138607734,
138607738,
138751565,
138783042,
138783053,
138793538,
138798384,
138841037,
138861037,
138877885,
138889794,
138978690,
138978695,
138986760,
139039322,
139039327,
139041694,
139067253,
139067259,
139132644,
139138698,
139154533,
139254775,
139256720,
139256852,
139257126,
139257795,
139262757,
139263104,
139263968,
139263983,
139264261,
139265145,
139266839,
139267700,
139270937,
139271324,
139273317,
139274924,
139275445,
139252162,
139253657,
139256435,
139256531,
139257125,
139257127,
139258132,
139263089,
139266195,
139266196,
139266235,
139266651,
139271714,
139275102,
138459978,
138599490,
138599499,
138605802,
138615890,
138635914,
138782930,
138790936,
138794426,
138794429,
138815721,
138999391,
138593688,
138624366,
138651396,
138756273,
138819439,
138831499,
138917398,
138979792,
139107392,
139108663,
139114142,
139234004,
138484273,
138548989,
138549452,
138608439,
138664179,
138677628,
138694721,
139044798,
139063911,
139084663,
139240575,
138520917,
138594348,
138595616,
138722539,
138733604,
138818343,
138868179,
138967581,
139088057,
139153755,
138520495,
138520497,
138653368,
138657087,
138676848,
138747854,
138753305,
138820869,
138953059,
138610926,
138746636,
138883190,
139108661,
139141384,
139203345,
139234006,
139234008,
139249958,
138767137,
138770934,
138819440,
138819955,
138892453,
138924416,
139088059,
139236720,
139258194,
138488876,
138800494,
138830795,
138854348,
138962919,
138962923,
139024060,
139275010,
138531432,
138622218,
138670719,
138705808,
138819956,
138945680,
138973668,
139241462,
138553494,
138666933,
138755955,
138815073,
138833200,
138930001,
138971574,
139046381,
138692797,
138793539,
138841442,
139049266,
139059479,
139062107,
139130762,
139264964,
139264966,
139266352,
139267419,
139269692,
139269694,
139275103,
138578200,
138751746,
138756553,
138777807,
139180678,
139187525,
138641664,
138699396,
138929985,
138977104,
139000481,
139205093,
138676512,
138761861,
138794427,
138815722,
138815726,
138835626,
138481492,
138588983,
138665803,
138683767,
138776255,
138981854,
139014937,
139187338,
139258731,
138525839,
138634261,
138862332,
138638156,
138705490,
139261388,
138817672,
139021383,
139023070,
138847541,
139009129,
139258725,
138919955,
139139009,
139163024,
138985932,
139055642,
139055644,
139264475,
139269906,
139274313,
138469170,
138503368,
138470456,
138868425,
138476417,
138896526,
138518691,
138835784,
138527381,
138663726,
138562750,
138573920,
138641453,
139108364,
138677346,
138977675,
138686587,
138971854,
138723974,
138964576,
138926629,
138968754,
139000737,
139063205,
139028939,
139111656,
139117915,
139177023,
139131016,
139203999,
138580670,
138632758,
138754721,
138787059,
138825643,
138875000,
138876315,
138876905,
138882209,
138897485,
138921271,
138934699,
138955959,
138982035,
139028171,
139080469,
139082427,
139263174,
    ]
    # create_stickers()
    # orders =get_all_orders(status=1)
    
    # print(len(orders))
    # orders_id = []
    # # for order in orders:
    # #     orders_id.append(orderp['orderId']])
    # orders_id = [x['orderId'] for x in orders if int(x['orderId']) not in blacklist]
    # print(len(orders_id))
    # create_stickers_by_id()

    orders = get_all_orders(status=1)
    print(len(orders))
    orders = [order for order in orders if int(order['orderId']) not in blacklist]
    print(len(orders))
    barcodes = get_barcodes_with_full_info(orders)
    with open('barcodes.json','w', encoding='utf-8') as f:
        json.dump(barcodes, f,ensure_ascii=False)
    add_json_file_to_today_json('barcodes.json')
    create_pdf_stickers_by_barcodes(barcodes)
    # return (len(orders), barcodes)


    # with open('fsdf.txt', 'w') as f:
    #     print(orders_id, file=f)
    # for order in orders:
    #     if int(order['orderId']) in blacklist:
    #         print(f'найдет {order["orderId"]}')
    #         orders.remove(order)
    # print(len(orders))
    # baroces = get_barcodes_with_full_info(orders)
    # print(baroces.items())
    # а
    # barcodes = sorted_barcodes_by_count_of_orders(barcodes)
    # pass
    # set_status_to_orders_by_ids(1,orders)

    # sorted_by_barcode_set_status_on_assembly('2000790297008', 350)
    # set_status_to_orders_by_ids(1,[str(132959439)])



    # orders = get_all_orders(status=0)
    # barcodes = get_barcodes_with_full_info(orders)
    # for barcode in barcodes:
    #     print(len(barcodes[barcode]['orders']), barcodes[barcode]['info']['article'])



        # print()
    # print(sys.path)
    # orders = [{'orderId': '122781838', 'dateCreated': '2021-11-15T15:17:59.781585Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 105208, 'officeAddress': 'г. Минск, Нёманская улица, д. 3', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 49128284, 'fio': 'Ерохова Софи ', 'phone': 375445626556}, 'chrtId': 47301927, 'barcode': '2000716391117', 'barcodes': ['2000716391117'], 'status': 1, 'userStatus': 4, 'rid': '300032806170', 'totalPrice': 119200, 'orderUID': '33564142053472337_6f35efb6172b4f31829736e919f810c0', 'deliveryType': 1}, {'orderId': '122628081', 'dateCreated': '2021-11-15T11:50:10.977447Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 103020, 'officeAddress': 'г. Ершов (Саратовская область), Калинина улица, д. 14', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 36211346, 'fio': 'Шохман Виктория Васильевна', 'phone': 79962668271}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429578873', 'totalPrice': 74000, 'orderUID': '27105673053466093_3760b85a04c841fba7095f46aee69498', 'deliveryType': 1}, {'orderId': '122629163', 'dateCreated': '2021-11-15T11:51:44.990127Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 101816, 'officeAddress': 'г. Светлоград (Ставропольский край), Выставочная площадь, д. 8А', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 21141322, 'fio': 'Надоленская Екатерина Анатольевна', 'phone': 79887373561}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429584281', 'totalPrice': 74000, 'orderUID': '19570661053466151_c7886ca43fd643e8a0637dcd0ae99e9b', 'deliveryType': 1}, {'orderId': '122632289', 'dateCreated': '2021-11-15T11:56:00.336669Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 17533, 'officeAddress': 'г. Минеральные Воды (Ставропольский край), улица 50 лет Октября, д. 51', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 23705659, 'fio': 'Сафронова Екатерина Владимировна', 'phone': 79289558635}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '51010909603', 'totalPrice': 74000, 'orderUID': '20852829553466279_947a5cfe80d64b09ad87c5d140ae9acb', 'deliveryType': 1}, {'orderId': '122636095', 'dateCreated': '2021-11-15T12:01:25.042171Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 13593, 'officeAddress': 'г. Благовещенск (Амурская область), Амурская улица, д. 230', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 5652279, 'fio': 'Шаруда Татьяна Николаевна', 'phone': 79140619074}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429611018', 'totalPrice': 85100, 'orderUID': '11826139553466430_0c70ee11e57f4bf1b8e97f4df05c6836', 'deliveryType': 1}, {'orderId': '122636702', 'dateCreated': '2021-11-15T12:02:15.182189Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 0, 'officeAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddressDetails': {'province': 'Республика Хакасия', 'area': 'Таштыпский район', 'city': 'село Таштып', 'street': 'улица Луначарского', 'home': '1', 'flat': '20', 'entrance': '2', 'longitude': 89.887835, 'latitude': 52.800433}, 'userInfo': {'userId': 44171800, 'fio': 'Султрекова Владлена Александровна', 'phone': 79833771263}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429613160', 'totalPrice': 74000, 'orderUID': '31085900053466455_d7530eb8638e4807b5e38b8c8cccee4f', 'deliveryType': 1}, {'orderId': '122636713', 'dateCreated': '2021-11-15T12:02:15.185581Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 0, 'officeAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddressDetails': {'province': 'Республика Хакасия', 'area': 'Таштыпский район', 'city': 'село Таштып', 'street': 'улица Луначарского', 'home': '1', 'flat': '20', 'entrance': '2', 'longitude': 89.887835, 'latitude': 52.800433}, 'userInfo': {'userId': 44171800, 'fio': 'Султрекова Владлена Александровна', 'phone': 79833771263}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429613162', 'totalPrice': 74000, 'orderUID': '31085900053466455_d7530eb8638e4807b5e38b8c8cccee4f', 'deliveryType': 1}, {'orderId': '122636712', 'dateCreated': '2021-11-15T12:02:15.225256Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 0, 'officeAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddressDetails': {'province': 'Республика Хакасия', 'area': 'Таштыпский район', 'city': 'село Таштып', 'street': 'улица Луначарского', 'home': '1', 'flat': '20', 'entrance': '2', 'longitude': 89.887835, 'latitude': 52.800433}, 'userInfo': {'userId': 44171800, 'fio': 'Султрекова Владлена Александровна', 'phone': 79833771263}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429613161', 'totalPrice': 74000, 'orderUID': '31085900053466455_d7530eb8638e4807b5e38b8c8cccee4f', 'deliveryType': 1}, {'orderId': '122636714', 'dateCreated': '2021-11-15T12:02:15.226511Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 0, 'officeAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddress': 'село Таштып, улица Луначарского, д. 1, кв. 20, под. 2, дмф. B1234, этаж 2, индекс 655740', 'deliveryAddressDetails': {'province': 'Республика Хакасия', 'area': 'Таштыпский район', 'city': 'село Таштып', 'street': 'улица Луначарского', 'home': '1', 'flat': '20', 'entrance': '2', 'longitude': 89.887835, 'latitude': 52.800433}, 'userInfo': {'userId': 44171800, 'fio': 'Султрекова Владлена Александровна', 'phone': 79833771263}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429613159', 'totalPrice': 74000, 'orderUID': '31085900053466455_d7530eb8638e4807b5e38b8c8cccee4f', 'deliveryType': 1}, {'orderId': '122637253', 'dateCreated': '2021-11-15T12:03:09.553869Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 13593, 'officeAddress': 'г. Благовещенск (Амурская область), Амурская улица, д. 230', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 5652279, 'fio': 'Шаруда Татьяна Николаевна', 'phone': 79140619074}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429615599', 'totalPrice': 85100, 'orderUID': '11826139553466480_e62a90a5e8604316b5baf88998e25d6a', 'deliveryType': 1}, {'orderId': '122639643', 'dateCreated': '2021-11-15T12:06:25.053558Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 16642, 'officeAddress': 'г. Ульяновск (Ульяновская область), улица Шолмова, д. 37А', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 33549544, 'fio': 'Чижова Светлана Юрьевна', 'phone': 79278258162}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429621668', 'totalPrice': 74000, 'orderUID': '25774772053466543_111fcebda91d4446a32075d017d3615f', 'deliveryType': 1}, {'orderId': '122639642', 'dateCreated': '2021-11-15T12:06:25.053652Z', 'wbWhId': 119408, 'storeId': 11087, 'pid': 16642, 'officeAddress': 'г. Ульяновск (Ульяновская область), улица Шолмова, д. 37А', 'deliveryAddress': '', 'deliveryAddressDetails': {'province': '', 'area': '', 'city': '', 'street': '', 'home': '', 'flat': '', 'entrance': '', 'longitude': 0, 'latitude': 0}, 'userInfo': {'userId': 33549544, 'fio': 'Чижова Светлана Юрьевна', 'phone': 79278258162}, 'chrtId': 48115318, 'barcode': '2000790297008', 'barcodes': ['2000790297008'], 'status': 1, 'userStatus': 4, 'rid': '101429621667', 'totalPrice': 74000, 'orderUID': '25774772053466543_111fcebda91d4446a32075d017d3615f', 'deliveryType': 1}]
    # if len(orders) == 0:
    #     return (0,0)

    # data = b'JVBERi0xLjMKMyAwIG9iago8PC9UeXBlIC9QYWdlCi9QYXJlbnQgMSAwIFIKL01lZGlhQm94IFswIDAgMTEzLjQwIDg1LjE3XQovUmVzb3VyY2VzIDIgMCBSCi9Db250ZW50cyA0IDAgUj4+CmVuZG9iago0IDAgb2JqCjw8L0ZpbHRlciAvRmxhdGVEZWNvZGUgL0xlbmd0aCAzNjY+PgpzdHJlYW0KeAGUUztuwzAM3XUKjs1QlRL18xogLdAtgC5Qx3aAbO3S6xei45g20QKdIvjlffhEIbwbhJtBGzN8G7SICG/336tx3qYMxdkSwLXjc0zt52uEybhoER8g4hbMlugOYqNIpncryMcNGFZQM/+U7ZrRkpZoI0ucfwF3aUmM4hVY2peFuZMNrbIHuJMN1P4+M5VsSCuo5gzdCqqGohhFMWNYS9BgahHnQK4dZfGxrJ60BxN/WZi7EpKQVZ5JXJnyzDzcLKuYWWwf28u0WchqptgEBRZOMXtyk1K2iE3QTLEJGtxcWcob2U6Mopid2ATuQwZyKDbM75t3yMUsw+z2z6FYBqXMun5+2444sfdNgl/3scLL64CFcpxSGPuuJHdJ48cYhukyDf1AEXHqh34kGsFxbXWCUzWffM0IVzhWSJY8FJsD1AGeAiVP5QD1BqcKZ/M/E/+rCdqS2wvr2AVL5w5Qb3CqcDY/AQAA//98pAYSCmVuZHN0cmVhbQplbmRvYmoKMSAwIG9iago8PC9UeXBlIC9QYWdlcwovS2lkcyBbMyAwIFIgXQovQ291bnQgMQovTWVkaWFCb3ggWzAgMCA1OTUuMjggODQxLjg5XQo+PgplbmRvYmoKNSAwIG9iago8PC9UeXBlIC9Gb250Ci9CYXNlRm9udCAvVGltZXMtUm9tYW4KL1N1YnR5cGUgL1R5cGUxCi9FbmNvZGluZyAvV2luQW5zaUVuY29kaW5nCj4+CmVuZG9iagoyIDAgb2JqCjw8Ci9Qcm9jU2V0IFsvUERGIC9UZXh0IC9JbWFnZUIgL0ltYWdlQyAvSW1hZ2VJXQovRm9udCA8PAovRmQwODM3NWY2NGViOTg2MWM2ZWFlNGRmY2ZkYmQzNTAwZmJkYmUzM2UgNSAwIFIKPj4KL1hPYmplY3QgPDwKPj4KL0NvbG9yU3BhY2UgPDwKPj4KPj4KZW5kb2JqCjYgMCBvYmoKPDwKL1Byb2R1Y2VyICj+/wBGAFAARABGACAAMQAuADcpCi9DcmVhdGlvbkRhdGUgKEQ6MjAyMTExMjYwOTIyNTMpCi9Nb2REYXRlIChEOjIwMjExMTI2MDkyMjUzKQo+PgplbmRvYmoKNyAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwovUGFnZXMgMSAwIFIKL05hbWVzIDw8Ci9FbWJlZGRlZEZpbGVzIDw8IC9OYW1lcyBbCiAgCl0gPj4KPj4KPj4KZW5kb2JqCnhyZWYKMCA4CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDU1MiAwMDAwMCBuIAowMDAwMDAwNzM3IDAwMDAwIG4gCjAwMDAwMDAwMDkgMDAwMDAgbiAKMDAwMDAwMDExNiAwMDAwMCBuIAowMDAwMDAwNjM5IDAwMDAwIG4gCjAwMDAwMDA4OTggMDAwMDAgbiAKMDAwMDAwMTAxMSAwMDAwMCBuIAp0cmFpbGVyCjw8Ci9TaXplIDgKL1Jvb3QgNyAwIFIKL0luZm8gNiAwIFIKPj4Kc3RhcnR4cmVmCjExMDgKJSVFT0YK'
    # # print(filter_orders_by_article(['WR00041', 'WR00040/01']))

    # with open('test.pdf', 'wb') as f:
    #     f.write(codecs.decode(data, 'base64'))
    # orders = get_all_orders(status=1)
    # if len(orders) == 0:
    #     return (0,0)
    # barcodes = get_barcodes_with_full_info(orders)
    # with open('barcodes.json','w', encoding='utf-8') as f:
    #     json.dump(barcodes, f,ensure_ascii=False)
    # add_json_file_to_today_json('barcodes.json')
    # create_db_for_checking(barcodes)
    # create_pdf_stickers_by_barcodes(barcodes)
    # create_pdf_stickers_by_barcodes(barcodes)
    # date_start='2021-11-06T00:47:17.528082+00:00'
    # logging.info(f'Получение всех заказов со статусом {2}')
    # date_end=get_now_time()
    # orders = []
    # params = {
    #     'date_end': date_end,
    #     'date_start': date_start,
    #     'status': 2,
    #     'take': 200,
    #     'skip': 0
    # }
    # response = requests.get(
    #     base_url_for_getting_orders,
    #     headers=headers,
    #     params=params)
    # orders = response.json()['orders']
    # barcodes = get_barcodes_with_full_info(orders)
    # with open('barcodes.json','w', encoding='utf-8') as f:
    #     json.dump(barcodes, f,ensure_ascii=False)
    # add_json_file_to_today_json('barcodes.json')
    # create_db_for_checking(barcodes)