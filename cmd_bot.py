import re
import requests
import json
import logging.config
from bot_config import dict_config
from dataclasses import dataclass
from decouple import config

logging.config.dictConfig(dict_config)
cmd_bot_logger = logging.getLogger('root_logger.cmd_bot_logger')


def get_lst_hotel(sort_order: str, cls_user: dataclass, extra_options: bool = False) -> list[str]:
    """
    Производит запрос к API https://hotels4.p.rapidapi.com/properties/list
    Проверяет соответствие отеля параметрам запроса

    :param sort_order: Метод сортировки в запросе
    :param cls_user: Класс данных на основание которых производится запрос
    :param extra_options: Нажатая пользователем кнопка

    :return: Список отелей соответствующий критериям запроса
    """

    url: str = "https://hotels4.p.rapidapi.com/properties/list"
    str_query: dict = {
        "pageNumber": '1',
        "pageSize": '25',
        "destinationId": cls_user.id_city,
        "sortOrder": sort_order,
        "locale": cls_user.locale,
        "currency": f'{"RUB" if cls_user.locale == "ru_RU" else "USD"}'
    }
    if extra_options is True:
        str_query['priceMin'] = cls_user.min_price
        str_query['priceMax'] = cls_user.max_price
        str_query['landmarkIds'] = f'{"Центр города" if cls_user.locale == "ru_RU" else "City center"}'
    cmd_bot_logger.debug(f'сформировали запрос: {str_query}')
    lst_res = []
    while True:
        response = requests.request("GET", url, headers=json.loads(config('headers')), params=str_query)
        cmd_bot_logger.debug(f'получили ответ сервера {response.status_code}')
        if response.status_code == 200:
            dct_result = json.loads(response.text.encode('utf-8'))
            for hotel in dct_result['data']['body']['searchResults']['results']:
                dist = float(re.sub(r'[^0-9.,]', '', hotel['landmarks'][0]['distance']).replace(',', '.'))
                dist_city_center = f'удаленность от центра: ' \
                                   f'{dist if cls_user.locale == "ru_RU" else round(dist * 1.61, 2)} км.'

                if extra_options is True and not float(cls_user.min_dist) <= dist <= float(cls_user.max_dist):
                    cmd_bot_logger.debug(f'не прошел по удаленности: {dist_city_center}')
                    continue

                name_hotel = f'название отеля: {hotel["name"]}'

                adr_hotel = f'адрес: ' \
                            f'{hotel["address"]["countryName"]}; ' \
                            f'{hotel["address"]["locality"]}; ' \
                            f'{"" if "streetAddress" not in hotel["address"] else hotel["address"]["streetAddress"]}'

                price = f'стоимость: ' \
                        f'{"нет информации" if "ratePlan" not in hotel else hotel["ratePlan"]["price"]["current"]}'

                str_res = f'{name_hotel}\n{adr_hotel}\n{dist_city_center}\n{price}\n'
                cmd_bot_logger.debug(f'{str_res}')
                if len(lst_res) < int(cls_user.count_hotel):
                    lst_res.append(str_res)
                    cmd_bot_logger.debug(f'добавили отель в список')
                else:
                    cmd_bot_logger.debug(f'возврат списка отелей: {lst_res}')
                    return lst_res
            next_page = 'nextPageNumber' in dct_result['data']['body']['searchResults']['pagination']
            cmd_bot_logger.debug(f'Наличие следующей страницы: {next_page}')
            if next_page:
                str_query['pageNumber'] = str(int(str_query['pageNumber']) + 1)
                cmd_bot_logger.debug(f'сформировали запрос для следующей страницы ')
            else:
                return lst_res
        else:
            cmd_bot_logger.error(f'ошибка запроса: {response.status_code}')
            return [f'{response.status_code}']
