import asyncio
from typing import Dict, List
from contextlib import asynccontextmanager
from src.models import Task
from src.async_queue import AsyncTaskQueue
from src.handlers import TaskHandler
from src.logger import log_info, log_error


class AsyncTaskExecutor:
    """Асинхронный исполнитель задач"""

    def __init__(self, queue: 'AsyncTaskQueue', max_workers: int = 3) -> None:
        """Инициализируем исполнитель"""
        self.queue = queue
        self.max_workers = max_workers
        self.handlers: Dict[str, List[TaskHandler]] = {}
        self._running = False
        self._workers: List[asyncio.Task] = []
        log_info(f'Исполнитель создан (max_workers={max_workers})')

    def register_handler(self, handler: 'TaskHandler') -> None:
        """Регистрируем обработчик для определённого статуса"""
        status = handler.supported_status
        if status not in self.handlers:
            self.handlers[status] = []
        self.handlers[status].append(handler)
        log_info(f'Зарегистрирован обработчик для статуса "{status}"')

    async def _process_task(self, task: Task) -> bool:
        """Обрабатываем одну задачу через подходящие обработчики"""
        handlers = self.handlers.get(task.status, [])
        if not handlers:
            log_info(f'Нет обработчиков для задачи ID={task.id}, статус={task.status}')
            return False

        for handler in handlers:
            try:
                log_info(f'Обработка задачи ID={task.id} через {type(handler).__name__}')
                success = await handler.handle(task)
                if success:
                    return True
            except Exception as e:
                log_error(f'Ошибка в обработчике {type(handler).__name__}: {e}')
                continue
        return False

    async def _worker(self, worker_id: int) -> None:
        """Воркер: берёт задачи из очереди и обрабатывает"""
        log_info(f'Воркер <{worker_id}> запущен')
        try:
            async for task in self.queue:
                try:
                    await self._process_task(task)
                except Exception as e:
                    log_error(f'Воркер <{worker_id}> ошибка при обработке: {e}')
        except StopAsyncIteration:
            log_info(f'Воркер <{worker_id}> завершил работу')
        finally:
            log_info(f'Воркер <{worker_id}> остановлен')

    async def start(self) -> None:
        """Запускаем пул воркеров"""
        if self._running:
            log_error('Исполнитель уже запущен')
            return

        log_info(f'Запуск исполнителя с {self.max_workers} воркерами')
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(i))
            for i in range(self.max_workers)
        ]

    async def stop(self) -> None:
        """Останавливаем пул воркеров"""
        log_info('Остановка исполнителя...')
        self._running = False

        await self.queue.close()

        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
            self._workers.clear()

        log_info('Исполнитель остановлен')

    @asynccontextmanager
    async def run(self):
        """Контекстный менеджер для запуска исполнителя"""
        await self.start()
        try:
            yield self
        finally:
            await self.stop()