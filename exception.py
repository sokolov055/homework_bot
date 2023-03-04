class MissingVariable(Exception):
    """Отсутствует одна из переменных окружения."""

    pass


class KeyNotFound(Exception):
    """Отсутствует ключ."""

    pass


class UnknownStatus(Exception):
    """Изменился статус проверки."""

    pass
