import requests
from datetime import datetime
import pytz
import time
from bs4 import BeautifulSoup
import telebot

moscow_tz = pytz.timezone('Europe/Moscow')
# ------------------------- Настройки -------------------------
# Список обязательных и исключаемых ключевых слов для вакансий
include_keywords = []
exclude_keywords = ["Junior", "стажировка", "тестовое задание", "гибридный", "офисный", 
                    "высшее", "Крутейший вайб+", "gamedev", "геймдев", "игры", "автоматизированное", 
                    "нагрузочное", "образование", "офис", "стажёр", "не it", "оффлайн", "office", 
                    "автоматизации", "1С", "1C"]

# Поисковый запрос для вакансий
search_text = "Тестировщик ПО"

# Список слов, которые не должны встречаться в названии вакансии
excluded_title_keywords = ["Стажер", "Нагрузочное", "Auto", "Автоматизированое", "Junior", 
                            "стажёр", "техники", "не it", "в офисе", "не айти", "начинающий", 
                            "office", "mobile", "автотестировщик", "AQA", "мобильное", "Яндекс", "1C", "1С", "мобильных"]

# Параметры для поиска вакансий
search_params = {
    "area": 1  # Пример для поиска в Москве
}

# Максимальное количество вакансий для сохранения
max_vacancies = 50

# Токен для Telegram бота
TOKEN = "7529463228:AAGgqXhXYEfcEA8B-8Dffs7H3nZdvAk1i5g"
bot = telebot.TeleBot(TOKEN)

# ------------------------- Логика -------------------------

# Функция для проверки, онлайн ли пользователь в Telegram
def is_user_online():
    """Проверяет, онлайн ли пользователь."""
    url = f"https://api.telegram.org/bot{TOKEN}/getChatMember?chat_id={CHAT_ID}&user_id={CHAT_ID}"
    response = requests.get(url).json()
    status = response.get("result", {}).get("status", "")
    return status in ["online", "recently"]

# Функция для парсинга вакансий
def parse_vacancies():
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
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            print(f"Ошибка запроса: {response.status_code}")
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
            detail_response = requests.get(vacancy_detail_url, headers=headers)
            if detail_response.status_code != 200:
                continue

            vacancy_data = detail_response.json()
            title = vacancy_data.get("name", "")
            if any(excluded.lower() in title.lower() for excluded in excluded_title_keywords):
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

    vacancies_found.sort(key=lambda x: x.get("salary_from", -1), reverse=True)

    return vacancies_found

# Функция для отправки вакансий в Telegram
def send_vacancies_to_telegram(vacancies):
    global reminder_sent
    chat_id = "493952412"  # Укажи свой chat_id
    current_hour = datetime.now(moscow_tz).hour

    for vac in vacancies:
        vacancy_message = (
            f"Ссылка на вакансию: {vac['url']}\n"
            f"Зарплата: {vac['salary']}\n"
            f"Сопроводительное письмо: {'нужно' if any(kw in vac['description'].lower() for kw in ['сопроводительное письмо', 'мотивационное письмо', 'прикрепите письмо']) else 'не нужно'}"
        )
        bot.send_message(chat_id, vacancy_message, disable_notification=(8 <= current_hour < 19))

    # Проверяем, если пользователь онлайн до 19:00 — отправляем напоминание (1 раз)
    if (12 <= current_hour < 19) and not reminder_sent and is_user_online():
        bot.send_message(chat_id, "Ты появился онлайн! Не забудь проверить вакансии 😉")
        reminder_sent = True

# Сброс флага в 19:00
def reset_reminder():
    global reminder_sent
    if datetime.now(moscow_tz).hour == 19:
        reminder_sent = False

# ------------------------- Время и выполнение -------------------------

# Список времени для отправки сообщений
send_times = [1, 8, 15, 22]  # 8:00, 15:00, 22:00

if __name__ == "__main__":
    while True:
        current_time = datetime.now(moscow_tz)

        # Получаем текущее время по МСК и проверяем, что оно совпадает с одним из запланированных
        if current_time.hour in send_times and current_time.minute == 0:
            print(f"Время отправки вакансий ({current_time.hour}:00). Парсим вакансии...")
            vacancies = parse_vacancies()
            print(f"Найдено {len(vacancies)} вакансий")
            if vacancies:  # Проверка, что вакансии найдены
                send_vacancies_to_telegram(vacancies[:30])  # Отправляем только первые 30 вакансий

        reset_reminder()
        time.sleep(60)  # Пауза на 1 минуту
