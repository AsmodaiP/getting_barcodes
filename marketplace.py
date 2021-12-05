import datetime
import json
from sys import path
from typing import Dict, List
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
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import create_stickers_and_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3NJRCI6IjJmZDAzNjhkLTdmMDMtNGI3Yy1hMWIxLTY4ZjM5ODE5NDk1NiJ9.MMrdwCeAHU4Ly1BF5hfxhXljthEyAzbtV7DIwvR7lRc'

pdfmetrics.registerFont(TTFont('FreeSans', 'fonts/FreeSans.ttf'))

def get_supplies(token:str, status:str='ACTIVE') -> List:
    headers = {
        'Authorization': token,
    }
    URL_FOR_GETTING_SUPPLIES = 'https://suppliers-api.wildberries.ru/api/v2/supplies'
    params = {'status': status}
    response = requests.get(URL_FOR_GETTING_SUPPLIES, params=params, headers=headers)
    return response.json()['supplies']

def create_new_supplie(token:str) -> Dict:
    URL_FOR_CREATING_SUPPLIE = 'https://suppliers-api.wildberries.ru/api/v2/supplies'
    headers = {
        'Authorization': token,
    }
    response = requests.post(URL_FOR_CREATING_SUPPLIE,headers=headers)
    data = {
        'supplyId': '',
        'error':''
    }
    error_dict={
        409: 'У поставщика уже есть активная поставка',
        500: 'Ошибка WB'
    }
    if response.status_code == 201:
        data['supplyId']=response.json()['supplyId']
        return response.json()['supplyId']
    data['error'] = error_dict[response.status_code]
    return data

def add_orders_to_supplie(token: str, supplie_id: str, orders: List):
    order_ids = [order['orderId'] for order in orders]
    add_orders_to_supplie_by_id(token, supplie_id, order_ids)

def add_orders_to_supplie_by_id(token:str, supplie_id:str, orders_ids:List[str]) -> None | Dict:
    headers = {
        'Authorization': token,
    }
    data = {'orders':orders_ids}
    js = json.dumps(data)
    URL_FOR_ADD_ORDERS_TO_SUPPLIE = f'https://suppliers-api.wildberries.ru/api/v2/supplies/{supplie_id}'
    response = requests.put(URL_FOR_ADD_ORDERS_TO_SUPPLIE, headers=headers, data=js)

    if response.status_code != 200:
        return 200
    else:
        response.json()['errorText']


def close_supplie(token:str, supplie_id:str) -> None | str:
    headers = {
        'Authorization': token,
    }
    URL_FOR_CLOSING_SUPPLIE = f'https://suppliers-api.wildberries.ru/api/v2/supplies/{supplie_id}/close'
    response = requests.post(URL_FOR_CLOSING_SUPPLIE, headers=headers)
    if response.status_code == 200:
        return None
    return response.json()['errorText']

def get_data_svg_stick_of_supplie(token:str, supplie_id:str) -> Dict :
    headers = {
        'Authorization': token,
    }
    data = {'data_for_creating_pdf': '', 'error': ''}
    URL_FOR_GETTING_STICK_OF_SUPPLIE =  f'https://suppliers-api.wildberries.ru/api/v2/supplies/{supplie_id}/barcode'
    response = requests.get(URL_FOR_GETTING_STICK_OF_SUPPLIE, headers=headers, params={'type': 'svg'})
    if response.status_code == 200:
        data['data_for_creating_pdf'] = response.json()['file']
        return data
    data['error']=response.json()['errorText']
    return data


def create_file_by_data(data:str, path_for_save:str) -> None:
    file_data = bytes(data, 'utf-8')
    with open(path_for_save, 'wb') as f:
        f.write(codecs.decode(file_data, 'base64'))

def create_stick_of_supplie_by_svg_and_name(path_to_svg:str, name:str, path_for_save:str) -> None:
    drawing = svg2rlg(path_to_svg)
    canvas = Canvas(path_for_save, pagesize=A4)
    canvas.setFont('FreeSans', 20)
    renderPDF.draw(drawing, canvas,50*mm,190*mm)
    canvas.drawString(70*mm, 170*mm, name)
    canvas.save()


def get_suplies_orders(token:str, supplie_id:str) -> Dict:
    URL_FOR_ORDERS_OF_SUPPLIE =  f'https://suppliers-api.wildberries.ru/api/v2/supplies/{supplie_id}/orders'
    headers = {
        'Authorization': token,
    }
    response = requests.get(URL_FOR_ORDERS_OF_SUPPLIE, headers=headers)
    data = {'orders': '', 'error':  ''}
    if response.status_code == 200:
        data['orders'] = response.json()['orders']
        return data
    data['error']= response.json()['errorText']
    return data


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


def add_information_about_barcodes_and_len(barcodes):
    for barcode in barcodes.keys():
        barcodes[barcode]['info'] = getting_information_about_barcode_by_chartId(barcodes[barcode]['chrtId'])
        barcodes[barcode]['info']['count'] = len(barcodes[barcode]['orders'])
    return barcodes

def get_card_by_chrtId(token, chrtId):
    headers = {
        'Authorization': token,
    }
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

def get_data_nomenclature_from_card_by_chrtId(card, chrtId):
    all_nomenclatures = card['nomenclatures']
    for nomenclature in all_nomenclatures:
        for diffetent_types in nomenclature['variations']:
            vendorCode = nomenclature['vendorCode']
            data_about_nomenclature = diffetent_types
            for field in data_about_nomenclature:
                if data_about_nomenclature[field] == chrtId:
                    return(data_about_nomenclature, vendorCode, nomenclature)

def getting_information_about_barcode_by_chartId(chrtId):
    good = get_card_by_chrtId(token, chrtId)
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

def sorted_barcodes_by_count_of_orders(barcodes):
    sorted_tuples = sorted(barcodes.items(), key=lambda x: len(
        x[1]['orders']), reverse=True)
    sorted_dict = {k: v for k, v in sorted_tuples}
    return sorted_dict

def get_barcodes_with_full_info(token, orders):
    barcodes = get_barcodes_with_orders_and_chartId(token, orders)
    barcodes = add_information_about_barcodes_and_len(barcodes)
    barcodes = sorted_barcodes_by_count_of_orders(barcodes)
    return barcodes
orders = get_suplies_orders(token, 'WB-GI-4398749')['orders']
# print(orders[0].keys())
# for order in orders:
    # print(order['barcodes'], order['rid'])
# print(orders)
# print(orders[0].keys())

def add_json_file_to_today_json(name, path_to_json_file):
    json_dir = create_all_today_path(name)['json_dir']
    filename = 'barcodes_%s.json' % datetime.datetime.now().strftime('%H%M')
    path_to_backup_file = os.path.join(json_dir, filename)
    shutil.copyfile(path_to_json_file, path_to_backup_file)

def create_path_if_not_exist(path):
    if not os.path.exists(path):
        os.mkdir(path)

def create_all_today_path(name):
    pdf_path = os.path.join(BASE_DIR, 'pdf/')
    create_path_if_not_exist(pdf_path)
    today_prefix_path = os.path.join(
        pdf_path, datetime.datetime.today().strftime('%Y_%m_%d'))
    create_path_if_not_exist(today_prefix_path)
    today_path_with_name = os.path.join(today_prefix_path, name)
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

def create_and_merge_pdf_by_barcodes_and_ids(token, name, barcodes_and_ids):
    headers = {
        'Authorization': token,
    }
    logging.info('Создание pdf для баркодов')
    results_files = []
    url_for_getting_stikers = 'https://suppliers-api.wildberries.ru/api/v2/orders/stickers/pdf'
    for barcode in barcodes_and_ids.keys():
        create_stickers_and_db.edit_blank_pdf(barcodes_and_ids[barcode]['info'])
        pdfs = ['pdf/blank.pdf']
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
        today_path_with_name = create_all_today_path(name)['today_path_with_name']
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

def add_results_file_to_today_backup(name, path_to_results_file):
    backup_dir = create_all_today_path(name)['backup_dir']
    filename = 'results_%s.pdf' % datetime.datetime.now().strftime('%H%M')
    path_to_backup_file = os.path.join(backup_dir, filename)
    shutil.copyfile(path_to_results_file, path_to_backup_file)

def create_pdf_stickers_by_barcodes(token,name, barcodes_and_ids):
    results_files = []
    results_files = create_and_merge_pdf_by_barcodes_and_ids(token, name, barcodes_and_ids)
    merger = PdfFileMerger()
    logging.info('Объединение pdf файлов в results.pdf')
    for result in results_files:
        merger.append(result)
    merger.write('results.pdf')
    merger.close()
    add_results_file_to_today_backup(name,'results.pdf')

def create_stickers_by_supplie_id(token,name, supplie_id):
    orders = get_suplies_orders(token, supplie_id)['orders']
    if len(orders) == 0:
        return (0,0)
    barcodes = get_barcodes_with_full_info(token,orders)
    with open('barcodes.json','w', encoding='utf-8') as f:
        json.dump(barcodes, f,ensure_ascii=False)
    add_json_file_to_today_json(name,'barcodes.json')
    create_pdf_stickers_by_barcodes(token, name, barcodes)
    return (len(orders), barcodes)

def get_now_time():
    d = datetime.datetime.utcnow()
    d_with_timezone = d.replace(tzinfo=pytz.UTC)
    return(d_with_timezone.isoformat())

def get_all_orders(token, status=0, date_end=get_now_time(), date_start='2021-11-06T00:47:17.528082+00:00'):
    headers = {
        'Authorization': token,
    }
    URL_FOR_GETTING_ORDERS = 'https://suppliers-api.wildberries.ru/api/v2/orders'
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
        URL_FOR_GETTING_ORDERS,
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
            URL_FOR_GETTING_ORDERS,
            headers=headers,
            params=params)
        orders_from_current_response = response.json()['orders']
        orders += orders_from_current_response
        logging.info(f'{len(orders)}')
    logging.info(f'Получено {len(orders)}')
    return orders
# create_stickers_by_supplie_id(token,'БелотеловАГ','WB-GI-4397632')
# print(len(get_all_orders(token, status=1)))
# print(add_orders_to_supplie_by_id(token, 'WB-GI-4667695',['138455171']))

# щквук
# print(get_suplies_orders(token, 'WB-GI-4667695'))\
# add_orders_to_supplie(token,'WB-GI-4667695', get_all_orders(token) )
# orders = get_all_orders(token, status=1)
# for order in orders:
#     print(order['orderId'], end= ' ')
# print(get_all_orders(token, status=1))


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

# for orderid in blacklist:
#     print(orderid, end =' ')
# blacklist[0]
bl=[str(id) for id in blacklist]
# print(bl)
# add_orders_to_supplie_by_id(token, 'WB-GI-4667695',bl)
# print(len(blacklist))

create_stickers_and_db.set_status_to_orders_by_ids(2,bl)
print((get_suplies_orders(token, 'WB-GI-4667695')['orders']))
# print(get_supplies(token, status='ON_DELIVERY'))
# print(close_supplie(token,'WB-GI-4667695'))