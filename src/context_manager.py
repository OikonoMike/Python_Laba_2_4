import asyncio
from src.logger import log_info, log_error


class AsyncResource:
    """Пример асинхронного контекстного менеджера для управления ресурсами"""

    def __init__(self, name: str) -> None:
        self.name = name
        self._connected = False

    async def __aenter__(self) -> 'AsyncResource':
        """Подключаемся к ресурсу"""
        log_info(f'Ресурс "{self.name}": подключение...')
        await asyncio.sleep(0.05)  # имитация асинхронного подключения
        self._connected = True
        log_info(f'Ресурс "{self.name}": подключён')
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Отключаемся от ресурса"""
        log_info(f'Ресурс "{self.name}": отключение...')
        await asyncio.sleep(0.05)  # имитация асинхронного отключения
        self._connected = False
        log_info(f'Ресурс "{self.name}": отключён')
        if exc_type:
            log_error(f'Ресурс "{self.name}": ошибка в контексте: {exc_val}')
        return False

    @property
    def is_connected(self) -> bool:
        """Проверяем, подключён ли ресурс"""
        return self._connected