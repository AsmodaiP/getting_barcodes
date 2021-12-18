from __future__ import print_function
from logging.handlers import RotatingFileHandler
import logging
import os.path
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google.oauth2 import service_account
from parsing import get_detail_info, get_html
import datetime as dt
import telebot
from dotenv import load_dotenv



load_dotenv()

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
ID_FOR_NOTIFICATION = os.environ['ID_FOR_NOTIFICATION'].split(',')

bot = telebot.TeleBot(TELEGRAM_TOKEN)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, 'credentials_service.json')
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

INDEX_OF_FIRST = 1
SAMPLE_SPREADSHEET_ID = '1m_IcullUpEP4yOOnOH7ojBzbPpn38tFtVNyS40yKJjQ'
SAMPLE_RANGE_NAME = '12.2021'
START_POSITION_FOR_PLACE = 17


log_dir = os.path.join(BASE_DIR, 'logs/')
log_file = os.path.join(BASE_DIR, 'logs/parsing.log')
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


def get_WB_articuls_and_query(colum_of_articul=7, colum_of_query=5):
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()
    query = '_'
    articuls_and_query_dict = {}
    result = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                                range=SAMPLE_RANGE_NAME, majorDimension='ROWS').execute()
    values = result.get('values', [])
    if not values:
        print('No data found.')
    else:
        for row in values:
            if row[colum_of_articul].isdigit():
                if row[colum_of_query] != '':
                    query = row[colum_of_query]
                articuls_and_query_dict[row[colum_of_articul]] = query
    return articuls_and_query_dict


blacklist = []


def update_sheet():
    position_for_place = START_POSITION_FOR_PLACE + (dt.date.today().day-1)*6
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                                range=SAMPLE_RANGE_NAME, majorDimension='ROWS').execute()
    values = result.get('values', [])
    if not values:
        print('No data found.')
    else:
        i = INDEX_OF_FIRST
        query = '_'
        body = {
                'valueInputOption': 'USER_ENTERED',
                'data': [{'range': 'E2', 'values': [[str(dt.datetime.today().strftime('%d-%m-%Y'))]]}],
        }
        sheet.values().batchUpdate(spreadsheetId=SAMPLE_SPREADSHEET_ID, body=body).execute()
        # i = len(values)
        for row in values:
            
            try:
                articulus = row[7]
                position_in_table = row[position_for_place-1]
                if articulus.isdigit():
                    if int(articulus) in blacklist:
                        i += 1
                        continue
                    new_query = row[5]
                    if len(new_query) > 0:
                        query = new_query
                    logging.info(
                        f'Получение детальной информации для {row[4]}, {articulus}')
                    info = get_detail_info(articulus)
                    if info['price'] != ' ':
                        position = get_position(articulus, query)
                        try:
                            if position_in_table != '' and position_in_table != ' ' and position==1000:
                                position = min(position, int(position_in_table))
                        except:
                            bot.send_message(ID_FOR_NOTIFICATION[0], f'{position_in_table}, {position}, {articulus}')
                    else:
                        position = 1000
                    if info['price'].strip()=='':
                        position='Нет в наличии'
                        info['raiting'] = 'Нет в наличии'
                    logging.info(f'Позиция в выдаче {position}')
                    letter_for_range = convert_to_column_letter(
                        position_for_place)
                    body = {
                        'valueInputOption': 'USER_ENTERED',
                        'data': [
                            {'range': f'{SAMPLE_RANGE_NAME}!I{i}', 'values': [[info['price']]]},
                            {'range': f'{SAMPLE_RANGE_NAME}!K{i}:L{i}', 'values': [
                                [info['raiting'], info['reviewCount']]]},
                            {'range': f'{SAMPLE_RANGE_NAME}!{letter_for_range}{i}',
                             'values': [[position]]},
                             {'range': f'{SAMPLE_RANGE_NAME}!B{i}', 'values': [[dt.datetime.now().strftime("%H:%M  %d.%m.%y")]]}
                        ]
                    }
                    sheet.values().batchUpdate(spreadsheetId=SAMPLE_SPREADSHEET_ID, body=body).execute()

                    for id in ID_FOR_NOTIFICATION:
                        try:
                            
                            if position_in_table != '\n':
                                if int(position_in_table) != position:
                                    delta = position - int(position_in_table)
                                    delta_str = f'+{delta}' if delta > 0 else f'{delta}'
                                    bot.send_message(
                                        id, f'Товар [«{row[4]}»](https://www.wildberries.ru/catalog/{articulus}/detail.aspx?targetUrl=SP) теперь на позиции {position}({delta_str}) \n По запросу «» {query},\n Цена -  {info["price"]} ', parse_mode='Markdown')
                        except IndexError:
                            bot.send_message(
                                id, f'Товар [«{row[4]}»](https://www.wildberries.ru/catalog/{articulus}/detail.aspx?targetUrl=SP) теперь на позиции {position}', parse_mode='Markdown')
                        except Exception as e:
                            logging.error(
                                f'Чат {id} не инициализирован или  другая ошибка', exc_info=e)
            except Exception as e:
                logging.info(f'С {articulus} что-то не так')
                logging.error('ошибка', exc_info=e)

            i += 1


def get_position_on_the_page(page, query, articulus):
    id = 'c' + str(articulus)
    search_url = f'https://www.wildberries.ru/catalog/0/search.aspx?page={page}&search={query}'
    html = get_html(search_url)
    soup = BeautifulSoup(html, 'lxml')
    card_product = soup.find('div', id=id)
    return int(card_product['data-card-index']) + 1


def get_position(articulus, query):
    id = 'c' + str(articulus)
    page = 1
    success = False
    count_of_advertisement = 0
    count = 0
    while not success:
        query=query.strip()
        search_url = f'https://www.wildberries.ru/catalog/0/search.aspx?page={page}&search={query}'
        EXCEPTIONS_FOR_URL = {
            'Платье женское ': f'https://www.wildberries.ru/catalog/zhenshchinam/odezhda/platya?sort=popular&page={page}',
            'Платье женское': f'https://www.wildberries.ru/catalog/zhenshchinam/odezhda/platya?sort=popular&page={page}',
            'Шорты женские': f'https://www.wildberries.ru/catalog/zhenshchinam/odezhda/bryuki-i-shorty/shorty?sort=popular&page={page}',
            'Костюм женский': f'https://www.wildberries.ru/catalog/zhenshchinam/odezhda/kostyumy?sort=popular&page={page}',
            'Шорты женские ': f'https://www.wildberries.ru/catalog/zhenshchinam/odezhda/bryuki-i-shorty/shorty?sort=popular&page={page}'
        }
        if query in EXCEPTIONS_FOR_URL:
            search_url = EXCEPTIONS_FOR_URL[query]
        html = get_html(search_url)
        soup = BeautifulSoup(html, 'lxml')
        card_product = soup.find('div', id=id)
        # На первой странице проверяем, сколько рекламных объявлений
        # И если наш товар на ней, то считаем, сколько нерекламных до него
        if page == 1:
            advertisements = soup.find_all('div', class_='advert-card-item')
            if not card_product is None:
                all_cards = soup.find_all('div', class_='product-card')
                for card in all_cards:
                    if not 'advert-card-item' in card['class']:
                        count += 1
                    if card['id'] == id:
                        return count
            count_of_advertisement += len(advertisements)
        if card_product is None:
            count += len(soup.find_all('div', class_='product-card'))
            page += 1
            if page > 10:
                return 1000
            if len(soup.find_all('div', class_='product-card', limit=1)) == 0:
                return 0
        else:
            success = True
            return(count+int(card_product['data-card-index']) + 1 - count_of_advertisement)


def convert_to_column_letter(column_number):
    column_letter = ''
    while column_number != 0:
        c = ((column_number-1) % 26)
        column_letter = chr(c+65)+column_letter
        column_number = (column_number-c)//26
    return column_letter


def main():
    while True:
        update_sheet()

def check_sheet_exitst_by_title(title):
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()
    sheet_metadata = service.spreadsheets().get(spreadsheetId=SAMPLE_SPREADSHEET_ID).execute()
    sheets = sheet_metadata.get('sheets', '')
    for item in sheets:
        if item.get("properties").get('title') == title:
            return True
        return False

if __name__ == '__main__':
    # cell_list = sheet.range('E2')
    # print(check_sheet_exitst_by_title('04.2021'))
    # titles = [sheet.get]
    # print(sheets)
    # sheet.get
    # print(cell_list)
    # sheet.update_cells(['E2']], value_input_option='USER_ENTERED')
    # print(str(dt.datetime.today().strftime('%d-%m-%Y')))
    main()
