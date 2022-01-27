import logging
import os
import time
from json.decoder import JSONDecodeError
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv
from requests.exceptions import RequestException

load_dotenv()

PRACTICUM_TOKEN = os.getenv('practicum')
TELEGRAM_TOKEN = os.getenv('telegram_token')
TELEGRAM_CHAT_ID = os.getenv('telegram_chat_id')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('my_logger.log', maxBytes=5000000, backupCount=5)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s'
)
handler.setFormatter(formatter)


def send_message(bot, message):
    """Отправка сообщения в телеграм."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info('Удачная отправка сообщения в Телеграм')
    except Exception:
        logger.error('Ошибка в отправке сообщения')


def get_api_answer(current_timestamp):
    """Отправка запроса к API сервиса Домашка."""
    payload = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except RequestException:
        message = f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен.'
        logger.error(message)
        raise Exception(message)
    if response.status_code != 200:
        message = (f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен. '
                   f'Код ответа API: {response.status_code}')
        logger.error(message)
        raise Exception(message)
    try:
        return response.json()
    except JSONDecodeError:
        message = f'В ответе файл не JSON-формата: {response.status_code}'
        logger.error(message)
        raise TypeError(message)


def check_response(response):
    """Проверка на наличие и статуса домашки."""
    if not isinstance(response, dict):
        message = 'Ответ API - не словарь'
        logger.error(message)
        raise TypeError(message)
    try:
        homework = response['homeworks']
        if len(homework) == 0:
            message = 'В ответе API нет домашней работы'
            logger.error(message)
            raise IndexError(message)
    except KeyError:
        message = 'Некорректный файл-ответа'
        logger.error(message)
        raise Exception(message)
    try:
        homework_dict = response.get('homeworks')[0]
        keys = ['status', 'homework_name']
        for key in keys:
            if key not in homework_dict:
                message = 'Некорректный файл-ответа'
                logger.error(message)
                raise Exception(message)
        return homework_dict
    except Exception:
        message = 'Некорректный файл-ответа'
        logger.error(message)
        raise Exception(message)


def parse_status(homework):
    """Проверка на изменение статуса."""
    try:
        homework_status = homework['status']
    except Exception:
        message = 'Ключа status нет в ответе API'
        logger.error(message)
        raise KeyError(message)
    if homework_status not in HOMEWORK_STATUSES:
        message = 'Неизвестный статус домашней работы в ответе API'
        logger.error(message)
        raise KeyError(message)
    homework_name = homework['homework_name']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}" - {verdict}'


def check_tokens():
    """Проверка на доступность переменных окружения."""
    statuses = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if None in statuses:
        for status in statuses:
            if status is None:
                logger.critical(
                    f'Отсутствует обязательная переменная окружения: {status}'
                )
        return False
    return True


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    bot.send_message(TELEGRAM_CHAT_ID, 'Бот запущен')
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            try:
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            except Exception:
                message = 'Ошибка во взаимодействии с Telegram'
                logger.error(message)
            time.sleep(RETRY_TIME)
        else:
            message = 'Удачная отправка сообщения в Телеграм'
            logger.info(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
