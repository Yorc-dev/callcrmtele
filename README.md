# callcrmtele

## О проекте

**callcrmtele** — асинхронный парсер публичных Telegram-каналов, сохраняющий данные в PostgreSQL.
Проект является прототипом платформы для семантического анализа контента и спроектирован как
**модульный и легко расширяемый** — в будущем сюда добавятся векторизация, Neo4j, Whisper,
PaddleOCR, LangGraph и другие компоненты.

---

## Архитектура

```
callcrmtele/
├── parser.py                  # Точка входа: python parser.py
├── requirements.txt           # Зависимости проекта
├── .env.example               # Шаблон файла конфигурации
├── docker-compose.yml         # PostgreSQL + запуск скрипта
├── Dockerfile                 # Образ для запуска парсера
└── src/
    ├── __init__.py
    ├── config.py              # Конфигурация (dataclass + argparse + python-dotenv)
    ├── db/
    │   ├── __init__.py
    │   ├── database.py        # AsyncEngine, AsyncSession, init_db, get_session
    │   ├── models.py          # SQLAlchemy ORM-модели: Channel, Post
    │   └── repository.py      # upsert_channel, upsert_post, bulk_upsert_posts
    └── parser/
        ├── __init__.py
        ├── telegram_client.py # TelegramParser — Telethon-клиент с retry и обработкой ошибок
        ├── channel_parser.py  # ChannelDataCollector — оркестрация сбора данных
        └── channels_list.py   # Список 1000+ username'ов публичных Telegram-каналов
```

### Модули

| Модуль | Назначение |
|---|---|
| `src/config.py` | Загрузка настроек из `.env` / переменных окружения, поддержка CLI-аргументов |
| `src/db/database.py` | Создание async-движка SQLAlchemy, фабрики сессий, инициализация схемы БД |
| `src/db/models.py` | ORM-модели таблиц `channels` и `posts` |
| `src/db/repository.py` | Upsert-операции для защиты от дублирования данных |
| `src/parser/telegram_client.py` | Telethon-клиент с обработкой `FloodWaitError` и retry (1s/2s/4s) |
| `src/parser/channel_parser.py` | Оркестратор: перебирает каналы, сохраняет в БД, собирает статистику |
| `src/parser/channels_list.py` | Список 1000+ каналов из различных тематик |

---

## Структура базы данных

### Таблица `channels`

| Поле | Тип | Описание |
|---|---|---|
| `id` | `BIGSERIAL PK` | Внутренний идентификатор |
| `channel_id` | `BIGINT UNIQUE` | Telegram ID канала |
| `username` | `VARCHAR(255)` | @username канала |
| `title` | `TEXT` | Название канала |
| `description` | `TEXT` | Описание/bio |
| `subscribers_count` | `INTEGER` | Количество подписчиков |
| `avatar_url` | `TEXT` | Ссылка на аватар |
| `is_verified` | `BOOLEAN` | Верифицирован ли канал |
| `is_scam` | `BOOLEAN` | Помечен ли как скам |
| `created_at` | `TIMESTAMPTZ` | Дата создания записи |
| `updated_at` | `TIMESTAMPTZ` | Дата обновления записи |

### Таблица `posts`

| Поле | Тип | Описание |
|---|---|---|
| `id` | `BIGSERIAL PK` | Внутренний идентификатор |
| `message_id` | `BIGINT` | ID сообщения в Telegram |
| `channel_id` | `BIGINT FK` | Ссылка на `channels.channel_id` |
| `text` | `TEXT` | Текст поста |
| `published_at` | `TIMESTAMPTZ` | Дата публикации |
| `views` | `INTEGER` | Просмотры |
| `forwards` | `INTEGER` | Репосты |
| `replies_count` | `INTEGER` | Комментарии |
| `reactions_count` | `INTEGER` | Реакции |
| `has_media` | `BOOLEAN` | Наличие медиафайла |
| `media_type` | `VARCHAR(50)` | Тип медиа: photo, video, document… |
| `created_at` | `TIMESTAMPTZ` | Дата создания записи |
| `updated_at` | `TIMESTAMPTZ` | Дата обновления записи |

**Обоснование проектных решений:**
- `UNIQUE (channel_id, message_id)` гарантирует отсутствие дубликатов постов.
- `ON CONFLICT DO UPDATE` позволяет перезаписывать изменившиеся счётчики (views, forwards и т.д.) при повторном запуске.
- Индексы `idx_posts_channel_id` и `idx_posts_published_at` ускоряют выборки по каналу и дате.
- Использование `asyncpg` и `SQLAlchemy 2.x` async API обеспечивает высокую пропускную способность при работе с большим числом каналов.

---

## Установка и настройка

### Предварительные требования

- Python 3.11+
- PostgreSQL 14+ (или Docker)
- Telegram-аккаунт и API-ключи (см. ниже)

### Получение Telegram API credentials

1. Перейдите на [https://my.telegram.org](https://my.telegram.org) и войдите в аккаунт.
2. Перейдите в раздел **API development tools**.
3. Создайте новое приложение — получите `api_id` и `api_hash`.

### Установка зависимостей

```bash
git clone https://github.com/Yorc-dev/callcrmtele.git
cd callcrmtele
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Настройка окружения

```bash
cp .env.example .env
# Отредактируйте .env — укажите TG_API_ID, TG_API_HASH, DB_PASSWORD и другие значения
```

---

## Запуск

### Локально (без Docker)

1. Убедитесь, что PostgreSQL запущен и доступен с настройками из `.env`.
2. Первый запуск потребует авторизации в Telegram (введите номер телефона и код):

```bash
python parser.py
```

3. После успешной авторизации сессия сохраняется в файл `tg_session.session`.
   Последующие запуски не требуют повторной авторизации.

```bash
# Ограничить количество каналов и постов:
python parser.py --channels-limit 100 --posts-limit 5
```

### С Docker Compose

```bash
cp .env.example .env
# Отредактируйте .env

docker-compose up --build
```

> **Примечание:** при первом запуске в Docker также потребуется интерактивная авторизация Telegram.
> Смонтируйте папку с файлом сессии (`tg_session.session`) как volume, чтобы не авторизовываться каждый раз.

---

## Параметры запуска

### Аргументы командной строки

| Аргумент | Описание | По умолчанию |
|---|---|---|
| `--channels-limit N` | Количество каналов для парсинга | значение из `CHANNELS_LIMIT` |
| `--posts-limit N` | Количество постов на канал | значение из `POSTS_LIMIT` |

### Переменные окружения (`.env`)

| Переменная | Описание | По умолчанию |
|---|---|---|
| `TG_API_ID` | Telegram API ID (обязательно) | — |
| `TG_API_HASH` | Telegram API Hash (обязательно) | — |
| `TG_SESSION_NAME` | Имя файла сессии Telethon | `tg_session` |
| `DB_HOST` | Хост PostgreSQL | `localhost` |
| `DB_PORT` | Порт PostgreSQL | `5432` |
| `DB_NAME` | Имя базы данных | `telegram_parser` |
| `DB_USER` | Пользователь PostgreSQL | `postgres` |
| `DB_PASSWORD` | Пароль PostgreSQL (обязательно) | — |
| `CHANNELS_LIMIT` | Количество каналов для парсинга | `1000` |
| `POSTS_LIMIT` | Количество постов на канал | `10` |

---

## Расширяемость

Проект спроектирован таким образом, чтобы новые компоненты добавлялись легко:

| Компонент | Место интеграции |
|---|---|
| **Векторизация текста** (sentence-transformers, OpenAI Embeddings) | `src/db/repository.py` — дополнить `upsert_post` сохранением эмбеддингов |
| **Neo4j** (граф связей между каналами) | Новый модуль `src/db/neo4j_repository.py` + вызов из `channel_parser.py` |
| **Whisper** (транскрипция аудио/видео) | Новый модуль `src/media/transcriber.py` — обрабатывать посты с `media_type=audio/video` |
| **PaddleOCR** (распознавание текста на изображениях) | Новый модуль `src/media/ocr.py` — обрабатывать посты с `media_type=photo` |
| **LangGraph** (пайплайн семантического анализа) | Новый модуль `src/analysis/pipeline.py` — граф обработки после сбора данных |
| **Celery / RQ** (фоновые задачи) | Вынести парсинг каждого канала в отдельную задачу для масштабирования |
| **Prometheus / Grafana** (мониторинг) | Добавить метрики в `channel_parser.py` через `prometheus_client` |

Структура пакетов `src/db`, `src/parser`, `src/media`, `src/analysis` позволяет развивать каждое
направление независимо, не затрагивая остальной код.
