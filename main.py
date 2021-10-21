import logging.config
import requests
import telebot
import re
import json
import cmd_bot
from bot_config import dict_config, str_help
from dataclasses import dataclass
from decouple import config
from typing import Optional


bot = telebot.TeleBot(config('TOKEN'))
bot_logger = logging.getLogger("root_logger.bot_logger")
dct_users: dict = {}


@dataclass
class User:
    """Класс данных, хранит критерии запроса пользователя и id чата"""
    chat_id: str
    id_city: Optional[str] = None
    name_city: Optional[str] = None
    call_method: Optional[str] = None
    dist_min: Optional[str] = None
    dist_max: Optional[str] = None
    locale: Optional[str] = None
    count_hotel: Optional[str] = None
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    min_dist: Optional[str] = None
    max_dist: Optional[str] = None


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call: telebot.types.CallbackQuery) -> None:
    """
    Обработчик нажатия кнопки выбора города пользователем
    :param call: Нажатая пользователем кнопка
    """
    message: telebot.types.Message = call.message
    cls_user: User = dct_users[f'{message.chat.id}']
    bot.answer_callback_query(callback_query_id=int(call.id), text='Ok')
    inline_keyboard: list[list] = message.json['reply_markup']['inline_keyboard']
    dct_select_city: dict = json.loads(call.data)
    cls_user.id_city, cls_user.call_method = dct_select_city['id_city'], dct_select_city['call_method']
    for city in inline_keyboard:
        id_city = json.loads(city[0]['callback_data'])['id_city']
        if id_city == cls_user.id_city:
            cls_user.name_city = city[0]['text']
            break
    bot.edit_message_reply_markup(cls_user.chat_id, message_id=message.message_id, reply_markup=None)
    bot.send_message(cls_user.chat_id, cls_user.name_city)
    if cls_user.call_method in ['/lowprice', '/highprice']:
        bot.send_message(cls_user.chat_id, 'Укажите количество отелей:')
        bot.register_next_step_handler(message, count_hotel_handler)
    if cls_user.call_method == '/bestdeal':
        choice_price_and_dist(message)


def is_number(string: str) -> bool:
    """
    Проверяет является ли строка числом с плавающей точкой
    :param string: Строка
    """
    try:
        return float(string) >= 0
    except ValueError:
        return False


def choice_price_and_dist(message: telebot.types.Message) -> None:
    """
    Запрашивает ввод параметров запроса для команды /bestdeal
    (минимальная, максимальная цена и расстояние от центра города)
    :param message: Сообщение пользователя
    """
    cls_user: User = dct_users[f'{message.chat.id}']
    dct_atr: dict = {
        'минимальная цена': cls_user.min_price,
        'максимальная цена': cls_user.max_price,
        'минимальное расстояние от центра (км.)': cls_user.min_dist,
        'максимальное расстояние от центра (км.)': cls_user.max_dist
    }
    for count, (key, val) in enumerate(dct_atr.items()):
        if val is None:
            bot.send_message(cls_user.chat_id, f'Ввод {key}:')
            bot.register_next_step_handler(message, input_param, count)
            break
    else:
        bot.send_message(cls_user.chat_id, 'Ввод количество отелей:')
        bot.register_next_step_handler(message, count_hotel_handler)


def input_param(message: telebot.types.Message, step: int) -> None:
    """
    Проверяет корректность ввода параметров запроса для команды /bestdeal
    (минимальная, максимальная цена и расстояние от центра города)
    В случае некорректности полученных данных запрашивает повтор ввода
    :param message: Сообщение пользователя
    :param step: Определяет параметр запрашиваемый на данный момент
    """
    cls_user: User = dct_users[f'{message.chat.id}']
    if is_number(message.text):
        if step == 0:
            cls_user.min_price = message.text
        elif step == 1:
            if float(message.text) > float(cls_user.min_price):
                cls_user.max_price = message.text
            else:
                bot.send_message(cls_user.chat_id, f'Максимальная цена должна быть больше минимальной.\n'
                                                   f'Указанная минимальная цена: {cls_user.min_price} '
                                                   f'{"RUB" if cls_user.locale == "ru_RU" else "USD"}')
        elif step == 2:
            cls_user.min_dist = message.text
        elif step == 3:
            if float(message.text) > float(cls_user.min_dist):
                cls_user.max_dist = message.text
            else:
                bot.send_message(cls_user.chat_id, f'Максимальная удаленность должна быть больше минимальной.\n'
                                                   f'Указанная минимальная удаленность: {cls_user.min_dist} км.')
    else:
        bot.send_message(cls_user.chat_id, f'Повторите ввод, цифрами')
    choice_price_and_dist(message)


def count_hotel_handler(message: telebot.types.Message) -> None:
    """
    Запрашивает количество отелей, которые необходимо вывести в итоговом результате.
    Производит итоговый запрос к API https://hotels4.p.rapidapi.com/properties/list
    Отправляет пользователю найденные по установленным критериям отели
    :param message: Сообщение пользователя
    """
    cls_user: User = dct_users[f'{message.chat.id}']
    if message.text.isdigit():
        cls_user.count_hotel = message.text
        param_query = f'<b>Поиск отелей с параметрами:</b>\n' \
                      f'Город поиска: {cls_user.name_city}\n' \
                      f'Количество отелей: {cls_user.count_hotel}\n' \
                      f'Минимальная стоимость: {"не задана" if cls_user.min_price is None else cls_user.min_price}\n' \
                      f'Максимальная стоимость: {"не задана" if cls_user.max_price is None else cls_user.max_price}\n' \
                      f'Минимальная удаленность от центра (км.): ' \
                      f'{"не задана" if cls_user.min_dist is None else cls_user.min_dist}\n' \
                      f'Максимальная удаленность от центра (км.):' \
                      f'{"не задана" if cls_user.max_dist is None else cls_user.max_dist}\n'
        bot.send_message(chat_id=cls_user.chat_id, text=param_query, parse_mode='HTML')
        bot_logger.debug(f'сохранили количество отелей : {cls_user.count_hotel}')
        if cls_user.call_method == '/lowprice':
            lst_res = cmd_bot.get_lst_hotel(sort_order='PRICE', cls_user=cls_user)
        elif cls_user.call_method == '/highprice':
            lst_res = cmd_bot.get_lst_hotel(sort_order='PRICE_HIGHEST_FIRST', cls_user=cls_user)
        elif cls_user.call_method == '/bestdeal':
            lst_res = cmd_bot.get_lst_hotel(sort_order='PRICE', cls_user=cls_user, extra_options=True)
        else:
            lst_res = ['В этом городе отелей нет']
        if lst_res:
            for count, str_res in enumerate(lst_res, 1):
                str_res = f'{str(count)}: {str_res}'
                bot.send_message(chat_id=cls_user.chat_id, text=str_res)
        bot.send_message(chat_id=cls_user.chat_id, text=str_help)
    else:
        bot.send_message(cls_user.chat_id, 'Повторите ввод, цифрами')
        bot.send_message(cls_user.chat_id, 'Ввод количество отелей:')
        bot.register_next_step_handler(message, count_hotel_handler)


def create_keyboard(lst: list) -> telebot.types.InlineKeyboardMarkup:
    """
    Создание клавиатуры InlineKeyboardMarkup:
    :param lst: Список полученных городов после запроса к API https://hotels4.p.rapidapi.com/locations/search
    """
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    buttons: list[telebot.types.InlineKeyboardButton] = [
        telebot.types.InlineKeyboardButton(text=name_city, callback_data=json.dumps(
            {'id_city': f'{id_city}', 'call_method': f'{call_method}'}), name_city=name_city)
        for id_city, name_city, call_method in lst
    ]
    keyboard.add(*buttons)
    return keyboard


def choice_city(message: telebot.types.Message, call_method: str) -> None:
    """
    Осуществляет запрос к API https://hotels4.p.rapidapi.com/locations/search
    Отправляет клавиатуру выбора города
    :param message: Сообщение пользователя
    :param call_method: Команда боту
    """
    url: str = "https://hotels4.p.rapidapi.com/locations/search"
    cls_user: User = dct_users[f'{message.chat.id}']
    cls_user.locale = 'en_US' if all(ord(symb) < 128 for symb in message.text) else 'ru_RU'
    cls_user.call_method = call_method
    str_query = {"query": message.text, "locale": cls_user.locale}
    response = requests.request("GET", url, headers=json.loads(config('headers')), params=str_query)
    bot_logger.debug(f'Получили ответ сервера {response.status_code}')
    if response.status_code == 200:
        dct_result = json.loads(response.text)
        lst_city = [
            (city['destinationId'], re.sub(r'<.*>', message.text.capitalize(), city['caption']), cls_user.call_method)
            for city in dct_result['suggestions'][0]['entities'] if city['type'] == 'CITY'
        ]
        if len(lst_city) > 1:
            keyboard = create_keyboard(lst_city)
            bot.send_message(cls_user.chat_id, text="Выберете город:", reply_markup=keyboard)
        elif len(lst_city) == 1:
            cls_user.id_city, cls_user.name_city = lst_city[0][0], lst_city[0][1]
            bot.send_message(cls_user.chat_id, cls_user.name_city)
            if cls_user.call_method in ['/lowprice', '/highprice']:
                bot.send_message(cls_user.chat_id, 'Укажите количество отелей:')
                bot.register_next_step_handler(message, count_hotel_handler)
            elif cls_user.call_method == '/bestdeal':
                choice_price_and_dist(message)
        else:
            bot.send_message(cls_user.chat_id, f'Город - {message.text} не найден')
            bot.send_message(cls_user.chat_id, str_help)
    else:
        bot.send_message(cls_user.chat_id, f'Ошибка запроса: {response.status_code}')


@bot.message_handler(content_types=['text'])
def bot_cmd(message: telebot.types.Message) -> None:
    """
    Отправляет str_help в случае отсутствия сообщения в списке команд,
    либо производится переход на следующий шаг в зависимости от команды
    :param message: Сообщение пользователя
    """
    chat_id: str = checking_user_instance(message)
    bot_logger.debug(f'Получили сообщение {message}')
    if message.text in ['/lowprice', '/highprice', '/bestdeal']:
        bot.send_message(chat_id, 'Укажите город, в котором будет проводиться поиск отелей')
        bot.register_next_step_handler(message, choice_city, message.text)
    else:
        bot.send_message(chat_id, str_help)


def checking_user_instance(message: telebot.types.Message) -> str:
    """
    Проверка существования экземпляра класса для пользователя в словаре dct_users.
    При его отсутствие в словарь по ключу message.chat.id добавляется класс User
    :param message: Сообщение пользователя
    """
    bot_logger.debug(f'Проверка существования чата: {message.chat.id}')
    if message.chat.id not in dct_users:
        dct_users[f'{message.chat.id}'] = User(chat_id=str(message.chat.id))
        bot_logger.debug(f'Создали класс для чата с пользователем и добавили в словарь')
    return dct_users[f'{message.chat.id}'].chat_id


if __name__ == '__main__':
    while True:
        try:
            logging.config.dictConfig(dict_config)
            bot.polling(none_stop=True, interval=0)
        except Exception as exc:
            bot_logger.error(f'ошибка {exc.args}')
