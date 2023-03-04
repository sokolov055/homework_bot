import time
import logging
import requests
import telegram
from logging.handlers import RotatingFileHandler
import os
from dotenv import load_dotenv, find_dotenv
from http import HTTPStatus
import exception

load_dotenv(find_dotenv())

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    'my_logger.log', maxBytes=50000000, backupCount=5)
logger.addHandler(handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    check_up = all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))
    return check_up


def send_message(bot, message):
    """Отправляет сообщение в телеграмм-чат с ботом."""
    failed_message = 'Не удалось отправить сообщение'
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError:
        logger.error(failed_message)
        raise Exception(failed_message)
    else:
        logger.debug(f'Бот отправил сообщение {message}')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    data = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=data,
        )
        logger.info(f'Отправлен запрос к API Практикума. '
                    f'Код ответа API: {homework_statuses.status_code}')
        if homework_statuses.status_code != HTTPStatus.OK:
            raise Exception('Запрошеный URL не может быть получен')
    except requests.exceptions.RequestException as error:
        message = f'Эндпойнт недоступен: {error}'
        logger.error(message)
        raise Exception(message)
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(f'В переменной {response} ожидался словарью')
    if response.get('homeworks') is None:
        raise KeyError('Возможно введены неверные переменные.')
    elif not isinstance(response['homeworks'], list):
        raise TypeError('Данные пришли не ввиде списка')
    return response['homeworks']


def parse_status(homework):
    """Извлекает из информации статус домашней работы."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    except KeyError as error:
        message = f'Ключ {error} не найден в информации о домашней работе'
        logger.error(message)
        raise KeyError(message)

    try:
        verdict = HOMEWORK_VERDICTS[homework_status]
        logger.info('Сообщение подготовлено для отправки')
    except KeyError as error:
        message = f'Неизвестный статус домашней работы: {error}'
        logger.error(message)
        raise exception.UnknownStatus(message)
    result = (f'Изменился статус проверки работы "{homework_name}". '
              f'{verdict}')
    return result


def main():
    """Основная логика работы бота."""
    logger.info('Запуск бота')

    if not check_tokens():
        message = 'Отсутствует одна из переменных окружения'
        logger.critical(message)
        raise exception.MissingVariable(message)

    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    except telegram.error.InvalidToken as error:
        message = f'Ошибка при создании бота: {error}'
        logger.critical(message)
        raise telegram.error.InvalidToken

    timestamp = int(time.time())
    last_homework = None
    last_error = None

    while True:
        try:
            response = get_api_answer(timestamp - RETRY_PERIOD)
            homework = check_response(response)
            if homework and homework != last_homework:
                message = parse_status(homework[0])
                send_message(bot, message)
                last_homework = homework
            else:
                logger.debug('Статус домашней работы не изменился')
            timestamp = response.get('current_date')
            time.sleep(RETRY_PERIOD)

        except Exception as error:
            if str(error) != last_error:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
                last_error = str(error)
                time.sleep(600)
            else:
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
