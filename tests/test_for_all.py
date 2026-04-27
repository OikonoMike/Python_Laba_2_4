import pytest
from datetime import datetime
from src.models import Task, TaskSource
from src.sources import GeneratorTaskSource, ApiStubTaskSource
from src.collector import TaskCollector
from src.exceptions import TaskValidationError, TaskStateError
from src.models import Task
from src.queue import TaskQueue, TaskQueueIterator
from src.lazy_filters import filter_by_status, filter_by_priority, filter_by_ready, filter_combined, get_priority_stats


class TestTaskDescriptors:
    """Тесты дескрипторов задачи"""

    def test_priority_valid(self) -> None:
        """Приоритет в допустимом диапазоне"""
        task = Task(description='Тест', priority=5)
        assert task.priority == 5

    def test_priority_default(self) -> None:
        """Приоритет по умолчанию = 5"""
        task = Task(description='Тест')
        assert task.priority == 5

    def test_priority_too_low(self) -> None:
        """Приоритет < 1, который вызывает ошибку"""
        with pytest.raises(TaskValidationError):
            Task(description='Тест', priority=0)

    def test_priority_too_high(self) -> None:
        """Приоритет > 10, который вызывает ошибку"""
        with pytest.raises(TaskValidationError):
            Task(description='Тест', priority=11)

    def test_priority_not_int(self) -> None:
        """Приоритет не int, который вызывает ошибку"""
        with pytest.raises(TaskValidationError):
            Task(description='Тест', priority='high')

    def test_status_valid(self) -> None:
        """Допустимый статус"""
        task = Task(description='Тест', status='in_progress')
        assert task.status == 'in_progress'

    def test_status_default(self) -> None:
        """Статус по умолчанию = created"""
        task = Task(description='Тест')
        assert task.status == 'created'

    def test_status_invalid(self) -> None:
        """Недопустимый статус , который вызывает ошибк"""
        with pytest.raises(TaskValidationError):
            Task(description='Тест', status='unknown')

    def test_created_at_automatic(self) -> None:
        """Время создания устанавливается автоматически"""
        task = Task(description='Тест')
        assert isinstance(task.created_at, datetime)

    def test_id_generated_by_service(self) -> None:
        """ID генерируется сервисом, не пользователем"""
        task = Task(description='Тест')
        assert task.id == 0  # Пока не установлен
        task.id = 1  # Может установить сервис
        assert task.id == 1

    def test_id_cannot_change(self) -> None:
        """ID нельзя изменить после установки"""
        task = Task(description='Тест')
        task.id = 1
        with pytest.raises(TaskStateError):
            task.id = 2

    def test_description_required(self) -> None:
        """Описание обязательно"""
        with pytest.raises(TaskValidationError):
            Task(description='')

    def test_description_not_string(self) -> None:
        """Описание должно быть строкой"""
        with pytest.raises(TaskValidationError):
            Task(description=123)


class TestTaskIsReady:
    """Тесты вычисляемого свойства is_ready"""

    def test_is_ready_created(self) -> None:
        """Задача со статусом created готова"""
        task = Task(description='Тест', priority=5, status='created')
        assert task.is_ready is True

    def test_is_ready_in_progress(self) -> None:
        """Задача со статусом in_progress не готова"""
        task = Task(description='Тест', status='in_progress')
        assert task.is_ready is False

    def test_is_ready_done(self) -> None:
        """Задача со статусом done не готова"""
        task = Task(description='Тест', status='done')
        assert task.is_ready is False


class TestTaskStatusTransitions:
    """Тесты перехода статусов"""

    def test_start_from_created(self) -> None:
        """Можно начать задачу из статуса created"""
        task = Task(description='Тест')
        task.start()
        assert task.status == 'in_progress'

    def test_start_from_in_progress(self) -> None:
        """Нельзя начать задачу из статуса in_progress"""
        task = Task(description='Тест')
        task.start()
        with pytest.raises(TaskStateError):
            task.start()

    def test_complete_from_in_progress(self) -> None:
        """Можно завершить задачу из статуса in_progress"""
        task = Task(description='Тест')
        task.start()
        task.complete()
        assert task.status == 'done'

    def test_complete_from_created(self) -> None:
        """Нельзя завершить задачу из статуса created"""
        task = Task(description='Тест')
        with pytest.raises(TaskStateError):
            task.complete()

    def test_fail_from_created(self) -> None:
        """Можно отменить задачу из статуса created"""
        task = Task(description='Тест')
        task.fail()
        assert task.status == 'failed'

    def test_fail_from_done(self) -> None:
        """Нельзя отменить завершённую задачу"""
        task = Task(description='Тест')
        task.start()
        task.complete()
        with pytest.raises(TaskStateError):
            task.fail()


class TestTaskCollector:
    """Тесты сборщика задач"""

    def test_collector_generates_ids(self) -> None:
        """Сборщик генерирует уникальные ID"""
        collector = TaskCollector()
        collector.add_source(GeneratorTaskSource(count=3))
        tasks = collector.collect_all()

        ids = [task.id for task in tasks]
        assert len(ids) == 3
        assert len(set(ids)) == 3  # Все ID уникальны
        assert ids == [1, 2, 3]  # Последовательные

    def test_collector_validates_source(self) -> None:
        """Сборщик проверяет контракт источника"""
        collector = TaskCollector()
        result = collector.add_source('invalid')
        assert result is False


class TestTaskSource:
    """Тесты контракта источников"""

    def test_generator_source_contract(self) -> None:
        """GeneratorSource соответствует контракту"""
        source = GeneratorTaskSource()
        assert isinstance(source, TaskSource)

    def test_api_source_contract(self) -> None:
        """ApiStubTaskSource соответствует контракту"""
        source = ApiStubTaskSource()
        assert isinstance(source, TaskSource)



#-------------------------------------------------------------------------------------
# Тесты для третьей лабы (очередь задач)
class TestTaskQueueIterator:
    """Тесты итератора очереди задач"""

    def test_iterator_basic(self) -> None:
        """Базовая итерация по задачам"""
        tasks = [
            Task(description='Task 1', priority=5),
            Task(description='Task 2', priority=3),
        ]
        iterator = TaskQueueIterator(tasks)

        result = list(iterator)
        assert len(result) == 2
        assert result[0].description == 'Task 1'

    def test_iterator_empty(self) -> None:
        """Итерация по пустому списку"""
        iterator = TaskQueueIterator([])
        result = list(iterator)
        assert len(result) == 0

    def test_iterator_stopiteration(self) -> None:
        """StopIteration при завершении итерации"""
        tasks = [Task(description='Single')]
        iterator = TaskQueueIterator(tasks)

        next(iterator)
        with pytest.raises(StopIteration):
            next(iterator)


class TestTaskQueue:
    """Тесты очереди задач"""

    def test_queue_create_empty(self) -> None:
        """Создание пустой очереди"""
        queue = TaskQueue()
        assert len(queue) == 0
        assert queue.is_empty() is True

    def test_queue_add_task(self) -> None:
        """Добавление задачи в очередь"""
        queue = TaskQueue()
        task = Task(description='Test task')
        result = queue.add(task)

        assert result is True
        assert len(queue) == 1
        assert queue.is_empty() is False

    def test_queue_add_with_max_size(self) -> None:
        """Добавление задачи при заполненной очереди"""
        queue = TaskQueue(max_size=2)
        queue.add(Task(description='Task 1'))
        queue.add(Task(description='Task 2'))
        result = queue.add(Task(description='Task 3'))

        assert result is False
        assert len(queue) == 2

    def test_queue_remove_task(self) -> None:
        """Удаление задачи по ID"""
        queue = TaskQueue()
        task = Task(description='Test')
        task.id = 1
        queue.add(task)

        result = queue.remove(1)
        assert result is True
        assert len(queue) == 0

    def test_queue_remove_not_found(self) -> None:
        """Удаление несуществующей задачи"""
        queue = TaskQueue()
        result = queue.remove(999)
        assert result is False

    def test_queue_iteration(self) -> None:
        """Итерация по очереди"""
        queue = TaskQueue()
        for i in range(3):
            task = Task(description=f'Task {i}')
            task.id = i + 1
            queue.add(task)

        descriptions = [t.description for t in queue]
        assert descriptions == ['Task 0', 'Task 1', 'Task 2']

    def test_queue_repeated_iteration(self) -> None:
        """Повторная итерация по очереди"""
        queue = TaskQueue()
        queue.add(Task(description='Task A'))
        queue.add(Task(description='Task B'))

        # Первая итерация
        first = [t.description for t in queue]
        # Вторая итерация
        second = [t.description for t in queue]

        assert first == second
        assert len(first) == 2

    def test_queue_getitem(self) -> None:
        """Доступ по индексу"""
        queue = TaskQueue()
        task = Task(description='Indexed task')
        queue.add(task)

        assert queue[0].description == 'Indexed task'

    def test_queue_clear(self) -> None:
        """Очистка очереди"""
        queue = TaskQueue()
        queue.add(Task(description='To clear'))
        queue.clear()

        assert len(queue) == 0
        assert queue.is_empty() is True

    def test_queue_repr(self) -> None:
        """Строковое представление"""
        queue = TaskQueue(max_size=10)
        queue.add(Task(description='Test'))

        assert 'TaskQueue' in repr(queue)
        assert 'size=1' in repr(queue)


class TestFilters:
    """Тесты ленивых фильтров"""

    @pytest.fixture
    def sample_tasks(self) -> list:
        """Набор тестовых задач"""
        tasks = []
        for i in range(5):
            task = Task(description=f'Task {i}', priority=i + 1)
            task.id = i + 1
            tasks.append(task)
        # Меняем статусы для тестов
        tasks[0].status = 'created' # В очереди
        tasks[1].status = 'created' # В очереди (намеренно дублирую для теста)
        tasks[2].status = 'in_progress' # В работе
        tasks[3].status = 'done' # Готовые
        tasks[4].status = 'failed'
        return tasks

    def test_filter_by_status(self, sample_tasks) -> None:
        """Фильтр по статусу"""
        result = list(filter_by_status(sample_tasks, 'created'))
        assert len(result) == 2
        assert all(t.status == 'created' for t in result)

    def test_filter_by_status_no_matches(self, sample_tasks) -> None:
        """Фильтр без совпадений"""
        result = list(filter_by_status(sample_tasks, 'unknown'))
        assert len(result) == 0

    def test_filter_by_priority_min(self, sample_tasks) -> None:
        """Фильтр по минимальному приоритету"""
        result = list(filter_by_priority(sample_tasks, min_priority=3))
        assert len(result) == 3
        assert all(t.priority >= 3 for t in result)

    def test_filter_by_priority_range(self, sample_tasks) -> None:
        """Фильтр по диапазону приоритетов"""
        result = list(
            filter_by_priority(sample_tasks, min_priority=2, max_priority=4)
        )
        assert len(result) == 3
        for t in result:
            assert 2 <= t.priority <= 4

    def test_filter_by_ready(self, sample_tasks) -> None:
        """Фильтр готовых задач"""
        result = list(filter_by_ready(sample_tasks))
        # Только задачи со статусом 'created' и priority >= 1
        assert all(t.is_ready for t in result)

    def test_filter_combined(self, sample_tasks) -> None:
        """Комбинированный фильтр"""
        result = list(
            filter_combined(
                sample_tasks,
                status='created',
                min_priority=1,
                max_priority=5
            )
        )
        assert len(result) == 2
        for t in result:
            assert t.status == 'created'

    def test_filter_combined_no_criteria(self, sample_tasks) -> None:
        """Комбинированный фильтр без критериев"""
        result = list(filter_combined(sample_tasks))
        assert len(result) == len(sample_tasks)

    def test_get_priority_stats(self, sample_tasks) -> None:
        """Статистика по приоритетам"""
        stats = list(get_priority_stats(sample_tasks))
        assert len(stats) == 5  # 5 разных приоритетов
        assert (1, 1) in stats
        assert (5, 1) in stats

    def test_filter_is_lazy(self, sample_tasks) -> None:
        """Проверка ленивости фильтра (возвращает генератор)"""
        result = filter_by_status(sample_tasks, 'created')
        # Генератор не вычисляется пока не итерируем
        assert hasattr(result, '__next__')
        assert hasattr(result, '__iter__')


class TestIntegration:
    """Интеграционные тесты очереди и фильтров"""

    def test_queue_with_filters(self) -> None:
        """Очередь с применением фильтров"""
        queue = TaskQueue()
        for i in range(10):
            task = Task(description=f'Task {i}', priority=i + 1)
            task.id = i + 1
            if i < 5:
                task.status = 'created'
            else:
                task.status = 'done'
            queue.add(task)

        # Фильтруем задачи в очереди
        created_tasks = list(filter_by_status(queue, 'created'))
        assert len(created_tasks) == 5

    def test_queue_iteration_with_modification(self) -> None:
        """Итерация не влияет на исходную очередь"""
        queue = TaskQueue()
        queue.add(Task(description='Original'))

        # Итерируем
        list(queue)

        # Очередь не изменилась
        assert len(queue) == 1