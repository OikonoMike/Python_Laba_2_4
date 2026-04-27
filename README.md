# Лабораторная работа №4. Асинхронный исполнитель задач

---

## Структура репозитория
```
Python_Laba_2_4/
├── src/
│   ├── __init__.py
│   ├── models.py          # Модель задачи с дескрипторами и контракт для источников
│   ├── descriptors.py     # Пользовательские дескрипторы для валидации атрибутов задачи
│   ├── exceptions.py      # Исключения для задач платформы
│   ├── sources.py         # Источники задач
│   ├── collector.py       # Сборщик (который теперь генерирует ID)
│   ├── logger.py          # Логирование
│   ├── queue.py           # Очередь задач с пользовательским итератором
│   ├── lazy_filters.py    # Ленивые фильтры на генераторах
│   ├── async_queue.py     # Асинхронная очередь
│   ├── handlers.py        # Контракт через Protocol + обработчики
│   ├── executor.py        # AsyncTaskExecutor с пулом воркеров и контекстным менеджером
│   ├── context_manager.py # AsyncResource — пример асинхронного контекстного менеджера
│   └── main.py            # Основной файл запуска
├── tests/
│   ├── __init__.py
│   ├── test_for_laba4.py  # Тесты для лабы 4
│   └── test_for_all.py    # Тесты (от лаб 1, 2 и 3)
├── .gitignore
├── .pre-commit-config.yaml
├── pyproject.toml
├── README.md
└── requirements.txt
```
---

## Цель работы

Научиться реализовывать приложения с асинхронной моделью управления

---

### Ключевые концепции
 - **`async` / `await`** - Синтаксис для объявления и выполнения корутин; позволяет писать неблокирующий код
 - **Асинхронная итерация** - Протокол `__aiter__` / `__anext__` для использования `async for`
 - **`asyncio.Condition`** - Примитив синхронизации для координации `put()` / `get()` в очереди
 - **Protocol + runtime_checkable** - Контракт для обработчиков задач с проверкой через `isinstance()`
 - **Асинхронный контекстный менеджер** - Класс с `__aenter__` / `__aexit__` для управления ресурсами через `async with`
 - **Ленивые вычисления** - Обработка «по требованию» через генераторы (`yield`), без промежуточных списков
 - **Пул воркеров** - Параллельная обработка задач через `asyncio.create_task()` и `asyncio.gather()`

### Описание компонентов

 - `src/models.py` - Класс `Task` с дескрипторами, property и методами перехода статусов
 - `src/descriptors.py` - Пользовательские дескрипторы: `PriorityDescriptor`, `StatusDescriptor`, `CreatedAtDescriptor`
 - `src/exceptions.py` - Специализированные исключения: `TaskValidationError`, `TaskStateError`
 - `src/sources.py` - Источники задач (обновлены под новую модель `Task`)
 - `src/collector.py` - Сборщик задач — генерирует уникальные ID для задач
 - `src/logger.py` - Логирование — записывает события в `src/shell.log`
 - `src/main.py` - Точка входа — демонстрирует работу всех компонентов
 - `src/queue.py`  - Класс `TaskQueue` с методом `__iter__`, возвращающим `TaskQueueIterator`; поддержка `add()`, `remove()`, `__len__`, `__getitem__`
 - `src/filters.py` - Ленивые фильтры: `filter_by_status()`, `filter_by_priority()`, `filter_by_ready()`, `filter_combined()`, `get_priority_stats()` — все возвращают генераторы
 - `src/async_queue.py` - `AsyncTaskQueue` на базе `asyncio.Condition`: `async put()`, `async get()`, `async for` итерация, `close()`, `join()`
 - `src/handlers.py` - Контракт `TaskHandler` через `Protocol`; обработчики `CreatedTaskHandler`, `InProgressTaskHandler`, `FailedTaskHandler`
 - `src/executor.py` - `AsyncTaskExecutor` с пулом воркеров, регистрацией обработчиков и контекстным менеджером `run()`
 - `src/context_manager.py` - `AsyncResource` — пример асинхронного контекстного менеджера для управления ресурсами
 - `tests/test_for_all.py` - Тесты для всех компонентов

## Для запуска программы

### 1) Клонирование репозитория
```bash
git clone https://github.com/OikonoMike/Python_Laba_2_4.git  
```

### 2) Установка зависимостей
```bash
pip install -r requirements.txt
```

### 3) Запуск программы
```bash
python -m src.main
```
P.S. Вывод в консоль отсутствует — все логи пишутся в `src/shell.log` (этот файл создаётся при первом запуске программы)

### 4) Запуск всех тестов
```bash
pytest -v
```
ИЛИ запуск тестов только для лабы №4 (асинхронные тесты)
```bash
# Для асинхронных тестов сначала нужно pytest-asyncio
pip install pytest-asyncio
```

```bash
pytest tests/test_for_laba4.py -v
```