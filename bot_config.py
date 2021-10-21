dict_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'base_fmt': {"format": "%(levelname)s | %(name)s | %(asctime)s | %(lineno)s | %(message)s"}},
    'handlers': {
        'console': {
            'class': "logging.StreamHandler",
            'level': "DEBUG",
            "formatter": 'base_fmt',
        },
        'file': {
            'class': "logging.FileHandler",
            'level': "ERROR",
            'formatter': "base_fmt",
            'filename': 'log_err.log',
            'mode': "a"}
    },
    'loggers': {
        'root_logger': {'level': "DEBUG", 'handlers': ['console', 'file']},
    }
}


str_help = 'Выберете команду:\n' \
           '/lowprice — вывод самых дешёвых отелей в городе\n' \
           '/highprice — вывод самых дорогих отелей в городе\n' \
           '/bestdeal — вывод отелей, наиболее подходящих по цене и расположению от центра'


