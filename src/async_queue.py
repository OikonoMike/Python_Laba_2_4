import asyncio
from collections import deque
from typing import Deque
from src.models import Task
from src.logger import log_info


class AsyncTaskQueue:
    """Асинхронная очередь задач с поддержкой итерации"""

    def __init__(self, max_size: int = 0) -> None:
        """Создаём пустую асинхронную очередь"""
        self._queue: Deque[Task] = deque()
        self._condition = asyncio.Condition() # Уведомлятор
        self._max_size = max_size if max_size > 0 else None
        self._closed = False
        log_info(f'Асинхронная очередь создана (max_size={self._max_size})')

    async def put(self, task: Task) -> None:
        """Асинхронно добавляем задачу в очередь"""
        async with self._condition:
            while self._max_size and len(self._queue) >= self._max_size:
                await self._condition.wait()

            self._queue.append(task)
            log_info(f'Задача добавлена в очередь: ID={task.id}')
            self._condition.notify()

    async def get(self) -> Task:
        """Асинхронно получаем задачу из очереди"""
        async with self._condition:
            while not self._queue and not self._closed:
                await self._condition.wait()

            if self._closed and not self._queue:
                raise StopAsyncIteration('Очередь закрыта и пуста')

            task = self._queue.popleft()
            log_info(f'Задача получена из очереди: ID={task.id}')
            self._condition.notify()
            return task

    def __aiter__(self) -> 'AsyncTaskQueue':
        """Асинхронный итератор (возвращаем саму очередь)"""
        return self

    async def __anext__(self) -> Task:
        """Получаем следующую задачу"""
        try:
            return await asyncio.wait_for(self.get(), timeout=0.5) # таймаут для проверки закрытия
        except asyncio.TimeoutError:
            if self._closed and self.empty():
                raise StopAsyncIteration
            raise

    def task_done(self) -> None:
        """Сообщаем о завершении обработки задачи"""
        pass

    async def join(self) -> None:
        """Ждём обработки всех задач в очереди"""
        async with self._condition:
            while self._queue:
                await self._condition.wait()

    async def close(self) -> None:
        """Закрываем очередь"""
        async with self._condition:
            self._closed = True
            self._condition.notify_all()
            log_info('Очередь закрыта')

    def qsize(self) -> int:
        """Текущий размер очереди"""
        return len(self._queue)

    def empty(self) -> bool:
        """Пустая ли очередь"""
        return len(self._queue) == 0