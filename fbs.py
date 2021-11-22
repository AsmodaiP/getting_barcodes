import json
from google.oauth2 import service_account
import os
from googleapiclient.discovery import build
import datetime as dt
from create_stickers_and_db import create_all_today_path, create_finall_table_of_day
from dotenv import load_dotenv
import logging

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, 'credentials_service.json')
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
RANGE_NAME = '04.2021'
START_POSITION_FOR_PLACE = 14

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', None)
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)


def convert_to_column_letter(column_number):
    column_letter = ''
    while column_number != 0:
        c = ((column_number-1) % 26)
        column_letter = chr(c+65)+column_letter
        column_number = (column_number-c)//26
    return column_letter


def get_data_about_articles():
    json_dir = create_all_today_path()['json_dir']
    create_finall_table_of_day()
    data = json.load(open(os.path.join(json_dir, 'result_fbs.json'), 'r'))
    return data

def get_count_or_0(data, article):
    if article in data.keys():
        return data[article]
    else:
        return 0

def update_table():
    if SPREADSHEET_ID is None:
        return 'SPREADSHEET_ID не задано'
    position_for_place = START_POSITION_FOR_PLACE + (dt.date.today().day-1)*6
    data = get_data_about_articles()
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                range=RANGE_NAME, majorDimension='ROWS').execute()
    values = result.get('values', [])
    i = 3
    result = ''
    if not values:
        print('No data found.')
    else:
        for row in values[2:]:
            article = row[6]

            count = get_count_or_0(data, article)
            logging.info(f'Для {article} получено количество продаж {count}')
            letter_for_range = convert_to_column_letter(position_for_place)
            body = {
                'valueInputOption': 'USER_ENTERED',
                'data': [{'range': f'{letter_for_range}{i}',
                         'values': [[count]]},
                ]
            }
            sheet.values().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body).execute()
            i += 1
            result += f'{article} — {count}\n'
    return result


if __name__ == '__main__':
    update_table()
