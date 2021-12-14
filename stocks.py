from datetime import datetime
from os import name
import requests
import json
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import logging
from dotenv import load_dotenv
import telegram
import time

load_dotenv()
cred = json.load(open('credentials.json', 'rb'))
token = cred['БелотеловАГ']['token']
def get_stocks(token):
    headers = {
        'Authorization': token
    }
    URL_FOR_GETTING_STOCKS = 'https://suppliers-api.wildberries.ru/api/v2/stocks'
    params = {
        'skip':0,
        'take': 100000,
        'sort': 'article'
    }
    response = requests.get(URL_FOR_GETTING_STOCKS, params=params, headers=headers)
    data = response.json()
    return data

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
bot = telegram.Bot(token=TELEGRAM_TOKEN)
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

ID_FOR_NOTIFICATION = os.getenv('ID_FOR_NOTIFICATION', [295481377]).split(',')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, 'credentials_service.json')
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
RANGE_NAME = 'Остатки'
START_POSITION_FOR_PLACE = 14

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', None)

def convert_to_column_letter(column_number):
    column_letter = ''
    while column_number != 0:
        c = ((column_number-1) % 26)
        column_letter = chr(c+65)+column_letter
        column_number = (column_number-c)//26
    return column_letter

def update_stocks():
    stocks = get_stocks(token)['stocks']
    barcodes_info = {}

    for stock in stocks:

        barcode = stock['barcode']
        if barcode not in barcodes_info.keys():
            barcodes_info[barcode] = {
                'article': stock['article'],
                'stock': stock['stock'],
                'size': stock['size'],
                'name': stock['name']
            }
    
    
    i=2
    body_data = [{'range': f'{RANGE_NAME}!I1', 'values':[[datetime.now().strftime("%H:%M  %d.%m.%y")]]}]
    position_for_place = 1
    for barcode in barcodes_info.keys():
        article = barcodes_info[barcode]['article']
        name = barcodes_info[barcode]['name']
        size = barcodes_info[barcode]['size']
        stock = barcodes_info[barcode]['stock']
        body_data += [{'range': f'{RANGE_NAME}!{convert_to_column_letter(position_for_place)}{i}:{convert_to_column_letter(position_for_place+4)}{i}', 'values':[[barcode,article,name, size, stock]]}]
        i+=1
    body = {
        'valueInputOption': 'USER_ENTERED',
        'data':body_data
    }
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()
    sheet.values().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body).execute()

if __name__ == '__main__':
    while True:
        try:
            update_stocks()
        except Exception as e:
            bot.send_message(ID_FOR_NOTIFICATION[0], f'Ошибка {e} при обновлении остатков')
        time.sleep(300)
