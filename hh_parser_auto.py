import requests
from datetime import datetime
import pytz
import time
from bs4 import BeautifulSoup
import telebot
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)

moscow_tz = pytz.timezone('Europe/Moscow')

# ------------------------- Настройки -------------------------
include_keywords = []
exclude_keywords = [
    "Junior", "стажировка", "тестовое задание", "гибридный", "офисный",
    "высшее", "Крутейший вайб+", "gamedev", "геймдев", "игры", "автоматизированное",
    "нагрузочное", "образование", "офис", "стажёр", "не it", "оффлайн", "office",
    "автоматизации", "1С", "1C"
]

search_text = "Тестировщик ПО"

excluded_title_keywords = [
    "Стажер", "Нагрузочное", "Auto", "Автоматизированое", "Junior",
    "стажёр", "техники", "не it", "в офисе", "не айти", "начинающий",
    "office", "mobile", "автотестировщик", "AQA", "мобильное", "Яндекс", "1C", "1С", "мобильных"
]

search_params = {
    "area": 1  # Поиск в Москве
}

max_vacancies = 50

TOKEN = "7529463228:AAGgqXhXYEfcEA8B-8Dffs7H3nZdvAk1i5g"
bot = telebot.TeleBot(TOKEN)

reminder_sent = False  # Флаг для отправки напоминания

# ------------------------- Функции -------------------------

def is_user_online():
    """Проверяет, онлайн ли пользователь в Telegram."""
    chat_id = "493952412"  # Укажите правильный chat_id
    url = f"https://api.telegram.org/bot{TOKEN}/getChatMember?chat_id={chat_id}&user_id={chat_id}"
    try:
        response = requests.get(url).json()
        status = response.get("result", {}).get("status", "")
        return status in ["online", "recently"]
    except Exception as e:
        logging.error(f"Ошибка проверки статуса пользователя: {e}")
        return False

def parse_vacancies():
    logging.info("Начало парсинга вакансий...")
    url = "https://api.hh.ru/vacancies"
    headers = {
        "HH-User-Agent": "Mozilla/5.0 (qqqvexx@vk.com)"
    }
    vacancies_found = []
    page = 0

    while len(vacancies_found) < max_vacancies:
        params = {
            "text": search_text,
            "page": page,
            "per_page": 20
        }
        params.update(search_params)
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка запроса: {e}")
            break

        data = response.json()
        items = data.get("items", [])
        if not items:
            break

        for item in items:
            if len(vacancies_found) >= max_vacancies:
                break

            vacancy_id = item.get("id")
            vacancy_detail_url = f"https://api.hh.ru/vacancies/{vacancy_id}"
            try:
                detail_response = requests.get(vacancy_detail_url, headers=headers)
                detail_response.raise_for_status()
            except requests.exceptions.RequestException as e:
                logging.error(f"Ошибка запроса деталей вакансии {vacancy_id}: {e}")
                continue

            vacancy_data = detail_response.json()
            title = vacancy_data.get("name", "")
            if any(ex_kw.lower() in title.lower() for ex_kw in excluded_title_keywords):
                continue

            description_html = vacancy_data.get("description", "")
            soup = BeautifulSoup(description_html, "html.parser")
            description_text = soup.get_text(separator="\n")
            description_lower = description_text.lower()

            if not all(kw.lower() in description_lower for kw in include_keywords):
                continue
            if any(kw.lower() in description_lower for kw in exclude_keywords):
                continue

            salary_data = vacancy_data.get("salary")
            if salary_data:
                salary_from = salary_data.get("from") or 0
                salary_to = salary_data.get("to")
                currency = salary_data.get("currency")
                salary = f"{salary_from if salary_from else ''} - {salary_to if salary_to else ''} {currency}".strip(" -")
            else:
                salary = "Не указана"

            vacancy_info = {
                "id": vacancy_id,
                "name": vacancy_data.get("name", ""),
                "url": vacancy_data.get("alternate_url", ""),
                "salary": salary,
                "description": description_text
            }
            vacancies_found.append(vacancy_info)

        total_pages = data.get("pages", 0)
        if page >= total_pages - 1:
            break
        page += 1

    logging.info(f"Парсинг завершён. Найдено {len(vacancies_found)} вакансий.")
    return vacancies_found

def send_vacancies_to_telegram(vacancies):
    global reminder_sent
    chat_id = "493952412"  # Укажите правильный chat_id
    current_time = datetime.now(pytz.UTC).astimezone(moscow_tz)
    current_hour = current_time.hour

    for vac in vacancies:
        vacancy_message = (
            f"Ссылка на вакансию: {vac['url']}\n"
            f"Зарплата: {vac['salary']}\n"
            f"Сопроводительное письмо: {'нужно' if any(kw in vac['description'].lower() for kw in ['сопроводительное письмо', 'мотивационное письмо', 'прикрепите письмо']) else 'не нужно'}"
        )
        try:
            bot.send_message(chat_id, vacancy_message, disable_notification=(8 <= current_hour < 19))
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения для вакансии {vac['id']}: {e}")

    # Если пользователь онлайн и время между 12 и 19, отправляем напоминание (один раз)
    if (12 <= current_hour < 19) and not reminder_sent and is_user_online():
        try:
            bot.send_message(chat_id, "Ты появился онлайн! Не забудь проверить вакансии 😉")
            reminder_sent = True
        except Exception as e:
            logging.error(f"Ошибка отправки напоминания: {e}")

def reset_reminder():
    global reminder_sent
    current_time = datetime.now(pytz.UTC).astimezone(moscow_tz)
    if current_time.hour == 19:
        reminder_sent = False

# ------------------------- Основной цикл -------------------------
if __name__ == "__main__":
    send_times = [1, 8, 15, 22]  # Часы запуска (по МСК)
    while True:
        current_time = datetime.now(pytz.UTC).astimezone(moscow_tz)
        if current_time.hour in send_times and current_time.minute == 0:
            logging.info(f"Время отправки вакансий ({current_time.hour}:00). Парсим вакансии...")
            vacancies = parse_vacancies()
            if vacancies:
                send_vacancies_to_telegram(vacancies[:30])  # Отправляем только первые 30 вакансий
        reset_reminder()
        time.sleep(60)