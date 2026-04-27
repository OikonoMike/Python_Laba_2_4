from typing import Protocol, runtime_checkable
from src.models import Task
from src.logger import log_info, log_error
import asyncio


@runtime_checkable
class TaskHandler(Protocol):
    """Контракт для асинхронного обработчика задач"""

    async def handle(self, task: Task) -> bool:
        """Обработать задачу"""
        ...

    @property
    def supported_status(self) -> str:
        """Статус задачи, который этот обработчик может обрабатывать"""
        ...


class CreatedTaskHandler:
    """Обработчик для задач со статусом 'created' """

    def __init__(self, delay: float = 0.1) -> None:
        self._delay = delay

    @property
    def supported_status(self) -> str:
        return 'created'

    async def handle(self, task: Task) -> bool:
        """Обрабатываем задачу: имитируем работу и переводим в 'in_progress' """
        try:
            log_info(f'Обработка задачи ID={task.id} (статус=created)')
            await asyncio.sleep(self._delay)
            task.start()
            log_info(f'Задача ID={task.id} переведена в статус "in_progress"')
            return True
        except Exception as e:
            log_error(f'Ошибка обработки задачи ID={task.id}: {e}')
            return False


class InProgressTaskHandler:
    """Обработчик для задач со статусом 'in_progress' """

    def __init__(self, delay: float = 0.1) -> None:
        self._delay = delay

    @property
    def supported_status(self) -> str:
        return 'in_progress'

    async def handle(self, task: Task) -> bool:
        """Обрабатываем задачу: имитируем работу и завершаем"""
        try:
            log_info(f'Обработка задачи ID={task.id} (статус=in_progress)')
            await asyncio.sleep(self._delay)
            task.complete()
            log_info(f'Задача ID={task.id} переведена в статус "done"')
            return True
        except Exception as e:
            log_error(f'Ошибка обработки задачи ID={task.id}: {e}')
            task.fail()
            return False


class FailedTaskHandler:
    """Обработчик для задач со статусом 'failed' """

    def __init__(self) -> None:
        pass

    @property
    def supported_status(self) -> str:
        return 'failed'

    async def handle(self, task: Task) -> bool:
        """Логируем неудачу, задачу не обрабатываем"""
        log_info(f'Задача ID={task.id} помечена как failed, пропускаем')
        return True