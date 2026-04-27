import pytest
import asyncio
from src.models import Task
from src.async_queue import AsyncTaskQueue
from src.handlers import TaskHandler, CreatedTaskHandler, InProgressTaskHandler, FailedTaskHandler
from src.executor import AsyncTaskExecutor
from src.context_manager import AsyncResource


@pytest.mark.asyncio
class TestAsyncTaskQueue:
    """Тесты асинхронной очереди задач"""

    async def test_queue_put_and_get(self) -> None:
        """Асинхронное добавление и получение задачи"""
        queue = AsyncTaskQueue()
        task = Task(description='Test task')
        task.id = 1

        await queue.put(task)
        result = await queue.get()

        assert result.id == 1
        assert queue.empty() is True

    async def test_queue_multiple_tasks_fifo(self) -> None:
        """Очередь работает по принципу FIFO"""
        queue = AsyncTaskQueue()
        tasks = [Task(description=f'Task {i}') for i in range(5)]
        for i, t in enumerate(tasks):
            t.id = i + 1
            await queue.put(t)

        for i in range(5):
            task = await queue.get()
            assert task.id == i + 1

    async def test_queue_max_size_blocking(self) -> None:
        """Очередь блокирует put при переполнении"""
        queue = AsyncTaskQueue(max_size=2)
        await queue.put(Task(description='T1'))
        await queue.put(Task(description='T2'))

        # put должен ждать, пока не освободится место
        async def delayed_get():
            await asyncio.sleep(0.1)
            return await queue.get()

        get_task = asyncio.create_task(delayed_get())
        await queue.put(Task(description='T3'))  # Не должно зависнуть
        await get_task

        assert queue.qsize() == 2

    async def test_queue_close_stops_iteration(self) -> None:
        """Закрытие очереди останавливает асинхронную итерацию"""
        queue = AsyncTaskQueue()
        await queue.put(Task(description='T1'))
        await queue.close()

        # Итерация должна завершиться после получения одной задачи
        count = 0
        async for task in queue:
            count += 1
        assert count == 1

    async def test_queue_async_iteration(self) -> None:
        """Асинхронная итерация через async for"""
        queue = AsyncTaskQueue()
        for i in range(3):
            task = Task(description=f'Task {i}')
            task.id = i + 1
            await queue.put(task)
        await queue.close()

        descriptions = []
        async for task in queue:
            descriptions.append(task.description)

        assert descriptions == ['Task 0', 'Task 1', 'Task 2']

    async def test_queue_join_waits_for_completion(self) -> None:
        """join() ждёт обработки всех задач"""
        queue = AsyncTaskQueue()

        async def producer():
            for i in range(3):
                await queue.put(Task(description=f'P{i}'))
            await asyncio.sleep(0.1)  # Дать время на обработку
            await queue.close()

        async def consumer():
            while True:
                try:
                    task = await asyncio.wait_for(queue.get(), timeout=0.5)
                    queue.task_done()
                except (asyncio.TimeoutError, StopAsyncIteration):
                    break

        await asyncio.gather(producer(), consumer())
        await queue.join()

        assert queue.empty() is True

    async def test_queue_empty_and_qsize(self) -> None:
        """Проверка методов empty() и qsize()"""
        queue = AsyncTaskQueue()
        assert queue.empty() is True
        assert queue.qsize() == 0

        await queue.put(Task(description='T1'))
        assert queue.empty() is False
        assert queue.qsize() == 1


@pytest.mark.asyncio
class TestTaskHandlers:
    """Тесты обработчиков задач"""

    async def test_created_handler_transitions_status(self) -> None:
        """CreatedTaskHandler переводит задачу в in_progress"""
        handler = CreatedTaskHandler(delay=0.01)
        task = Task(description='Test', status='created')
        task.id = 1

        result = await handler.handle(task)

        assert result is True
        assert task.status == 'in_progress'

    async def test_inprogress_handler_completes_task(self) -> None:
        """InProgressTaskHandler завершает задачу"""
        handler = InProgressTaskHandler(delay=0.01)
        task = Task(description='Test', status='created')
        task.id = 1
        task.start()

        result = await handler.handle(task)

        assert result is True
        assert task.status == 'done'

    async def test_failed_handler_logs_and_returns_true(self) -> None:
        """FailedTaskHandler просто логирует и возвращает True"""
        handler = FailedTaskHandler()
        task = Task(description='Test', status='created')
        task.id = 1
        task.fail()

        result = await handler.handle(task)

        assert result is True
        assert task.status == 'failed'

    async def test_handler_protocol_runtime_check(self) -> None:
        """Проверка соответствия протоколу через isinstance"""
        handler = CreatedTaskHandler()
        assert isinstance(handler, TaskHandler)
        assert hasattr(handler, 'handle')
        assert hasattr(handler, 'supported_status')
        assert handler.supported_status == 'created'

    async def test_handler_error_handling(self) -> None:
        """Обработчик возвращает False при ошибке"""
        # Создаём задачу с невалидным статусом для вызова ошибки
        handler = CreatedTaskHandler(delay=0.01)
        task = Task(description='Test', status='done')  # Нельзя start() из done
        task.id = 1

        result = await handler.handle(task)

        assert result is False  # Ошибка поймана, возвращаем False


@pytest.mark.asyncio
class TestAsyncTaskExecutor:
    """Тесты асинхронного исполнителя"""

    async def test_executor_register_handler(self) -> None:
        """Регистрация обработчика по статусу"""
        queue = AsyncTaskQueue()
        executor = AsyncTaskExecutor(queue)
        handler = CreatedTaskHandler()

        executor.register_handler(handler)

        assert 'created' in executor.handlers
        assert len(executor.handlers['created']) == 1

    async def test_executor_process_task_success(self) -> None:
        """Успешная обработка задачи исполнителем"""
        queue = AsyncTaskQueue()
        executor = AsyncTaskExecutor(queue)
        executor.register_handler(CreatedTaskHandler(delay=0.01))

        task = Task(description='Test', status='created')
        task.id = 1

        result = await executor._process_task(task)

        assert result is True
        assert task.status == 'in_progress'

    async def test_executor_process_task_no_handlers(self) -> None:
        """Нет обработчиков для статуса — возврат False"""
        queue = AsyncTaskQueue()
        executor = AsyncTaskExecutor(queue)

        task = Task(description='Test', status='done')
        task.id = 1

        result = await executor._process_task(task)

        assert result is False

    async def test_executor_worker_processes_tasks(self) -> None:
        """Воркер обрабатывает задачи из очереди"""
        queue = AsyncTaskQueue()
        executor = AsyncTaskExecutor(queue, max_workers=1)
        executor.register_handler(CreatedTaskHandler(delay=0.01))

        # Добавляем задачи
        for i in range(3):
            task = Task(description=f'T{i}', status='created')
            task.id = i + 1
            await queue.put(task)
        await queue.close()

        # Запускаем воркера напрямую
        await executor._worker(0)

        assert queue.empty() is True

    async def test_executor_run_context_manager(self) -> None:
        """Контекстный менеджер run() корректно запускает и останавливает"""
        queue = AsyncTaskQueue()
        executor = AsyncTaskExecutor(queue, max_workers=2)
        executor.register_handler(CreatedTaskHandler(delay=0.01))

        for i in range(4):
            task = Task(description=f'T{i}', status='created')
            task.id = i + 1
            await queue.put(task)

        async with executor.run():
            await queue.join()

        assert queue.empty() is True
        assert executor._running is False


@pytest.mark.asyncio
class TestAsyncResource:
    """Тесты асинхронного контекстного менеджера"""

    async def test_resource_connects_and_disconnects(self) -> None:
        """Ресурс подключается в __aenter__ и отключается в __aexit__"""
        async with AsyncResource('TestDB') as resource:
            assert resource.is_connected is True
            assert resource.name == 'TestDB'

        assert resource.is_connected is False

    async def test_resource_cleanup_on_exception(self) -> None:
        """Ресурс отключается даже при исключении"""
        resource = AsyncResource('TestDB')

        try:
            async with resource:
                assert resource.is_connected is True
                raise ValueError('Test error')
        except ValueError:
            pass

        assert resource.is_connected is False

    async def test_resource_does_not_suppress_exceptions(self) -> None:
        """__aexit__ не подавляет исключения (return False)"""
        with pytest.raises(ValueError):
            async with AsyncResource('Test'):
                raise ValueError('Should propagate')


@pytest.mark.asyncio
class TestIntegration:
    """Интеграционные тесты всей системы"""

    async def test_multiple_tasks_parallel_processing(self) -> None:
        """Параллельная обработка нескольких задач"""
        queue = AsyncTaskQueue()
        executor = AsyncTaskExecutor(queue, max_workers=3)
        executor.register_handler(CreatedTaskHandler(delay=0.02))

        tasks = []
        for i in range(6):
            task = Task(description=f'Parallel {i}', status='created')
            task.id = i + 1
            tasks.append(task)
            await queue.put(task)

        start = asyncio.get_event_loop().time()
        async with executor.run():
            await queue.join()
        elapsed = asyncio.get_event_loop().time() - start

        # При 3 воркерах 6 задач по 0.02с должны выполниться ~за 0.04с, а не 0.12с
        assert elapsed < 0.1
        assert all(t.status == 'in_progress' for t in tasks)

    async def test_failed_tasks_handled_gracefully(self) -> None:
        """Задачи со статусом failed обрабатываются без ошибок"""
        queue = AsyncTaskQueue()
        executor = AsyncTaskExecutor(queue)
        executor.register_handler(FailedTaskHandler())

        task = Task(description='Failed', status='created')
        task.id = 1
        task.fail()
        await queue.put(task)

        async with executor.run():
            await queue.join()

        assert task.status == 'failed'