# IsoArch · Изотопные сигнатуры

> **Лабораторная работа №3 · Вариант 18**<br>
> Веб-сервис исследований костных останков: δ¹⁵N, δ¹³C, описание рациона, фото, короткое видео и лайки.

**Backend:** FastAPI · **ORM:** SQLAlchemy · **СУБД:** PostgreSQL 16 · **Медиа:** MinIO

## REST API

Базовый адрес: **`http://localhost:8000`** · JSON · Загрузка файлов: `multipart/form-data`

| Метод | Маршрут | Назначение |
|:---:|---|---|
| **GET** | `/api/services/` | Опубликованные услуги; фильтры `c13_max` и `filter`; признак `is_creator` |
| **GET** | `/api/services/feed` | Первая опубликованная услуга в ленте |
| **GET** | `/api/services/feed/{id}?next=true` | Следующая публикация; переход по кругу |
| **GET** | `/api/services/draft` | Собственный черновик без передачи ID |
| **POST** | `/api/services/` | Создание черновика: `title`, файлы `image` и `video` |
| **PUT** | `/api/services/{id}/publish` | Публикация: `description`, `delta_n15`, `delta_c13` |
| **DELETE** | `/api/services/{id}` | Логическое удаление собственной услуги |
| **POST** | `/api/services/{id}/like` | Установка или отмена лайка: `{"like": 1}` / `{"like": 0}` |
| **POST** | `/api/users/register` | Регистрация: `username`, `password`, `full_name`, `email` |
| **POST** | `/api/users/login` | Заглушка аутентификации для ЛР4 |
| **POST** | `/api/users/logout` | Заглушка деавторизации для ЛР4 |

## Таблицы PostgreSQL

| Таблица | Назначение | Поля |
|---|---|---|
| **`users`** | Пользователи | `id`, `username`, `password`, `full_name`, `email`, `created_at` |
| **`isotopic_signatures`** | Услуги — изотопные исследования | `id`, `title`, `description`, `status`, `image_file`, `video_file`, `delta_n15`, `delta_c13`, `creator_id`, `moderator_id`, `created_at`, `formed_at`, `completed_at` |
| **`signature_likes`** | Связь пользователя с понравившейся услугой | `id`, `user_id`, `signature_id`, `created_at` |

**Связи:** `creator_id`, `moderator_id`, `user_id` → `users.id`; `signature_id` → `isotopic_signatures.id`.<br>
**Ограничения:** один черновик на пользователя; один лайк на пару пользователь–услуга; `ON DELETE RESTRICT`.

<details>
<summary><strong>Типы полей, ключи и индексы</strong></summary>

Модели находятся в `models/`. FK используют `ON DELETE RESTRICT`; каскадного
удаления нет. `alembic_version` — служебная таблица номера миграции.

| Таблица | Поле | Тип / смысл |
|---|---|---|
| users | id | Integer, PK |
| users | username | String(100), обязательный, уникальный |
| users | password | String(255), обязательный, хеш |
| users | full_name | String(255), NULL допустим |
| users | email | String(255), уникальный, NULL допустим |
| users | created_at | DateTime, автоматически при создании |
| isotopic_signatures | id | Integer, PK |
| isotopic_signatures | title | String(255), обязательный |
| isotopic_signatures | description | Text, описание |
| isotopic_signatures | status | String(50), CHECK: draft/published/deleted |
| isotopic_signatures | image_file / video_file | String(500), имена объектов MinIO |
| isotopic_signatures | delta_n15 / delta_c13 | Float, δ¹⁵N / δ¹³C |
| isotopic_signatures | creator_id | Integer, обязательный FK → users.id |
| isotopic_signatures | moderator_id | Integer, необязательный FK → users.id |
| isotopic_signatures | created_at | DateTime, дата создания |
| isotopic_signatures | formed_at | DateTime, дата публикации, NULL до публикации |
| isotopic_signatures | completed_at | DateTime, дата удаления, NULL до удаления |
| signature_likes | id | Integer, PK |
| signature_likes | user_id | Integer, обязательный FK → users.id |
| signature_likes | signature_id | Integer, обязательный FK → isotopic_signatures.id |
| signature_likes | created_at | DateTime, дата лайка |
| alembic_version | version_num | String(32), PK, применённая миграция |

Индексы: `uq_user_single_draft` — уникальный creator_id только при status=draft;
`uq_user_signature_like` — уникальная пара user_id/signature_id.


</details>

<details>
<summary><strong>Форматы ответов, HTTP-статусы и загрузка медиа</strong></summary>

| Операция | Успешный ответ |
|---|---|
| Список | `200` — массив публикаций |
| Лента | `200` — одна публикация; без `next=true` маршрут по ID возвращает текущую запись |
| Черновик | `200` — объект или `null`, если черновика нет |
| Создание услуги | `201` — созданный черновик |
| Публикация | `200` — опубликованная услуга |
| Удаление | `204` — без тела ответа |
| Лайк | `200` — `like`, `likes_count` |
| Регистрация | `201` — пользователь без пароля; `full_name` и `email` необязательны |
| Login / logout | `200` — сообщение заглушки |

Фильтры списка можно использовать совместно: `c13_max` задаёт верхний порог
δ¹³C, `filter` ищет по названию. Лента упорядочена по возрастанию ID; после
последней публикации возвращается первая. Пустая лента и скрытые ID дают 404.

Ответ публикации содержит поля услуги, `is_creator` и `is_liked` (0/1),
`likes_count`, `image_url`, `video_url`. Ответ черновика содержит ID, название,
описание, изотопные значения и имена файлов. Системные поля доступны только
для чтения в ответе публикации.

Создание принимает PNG/JPEG/WebP до 10 МиБ и MP4 до 64 МиБ и 60 секунд.
Проверяются MIME, сигнатура изображения, структура MP4 и длительность `mvhd`.
Имена объектов — UUID с расширением из проверенного MIME, всегда на латинице.
Оба файла проверяются перед загрузкой. При отказе MinIO черновик не сохраняется;
при ошибке второй загрузки или записи БД уже загруженные объекты удаляются.
Если MinIO недоступен и при уборке, ошибка уборки записывается в серверный лог.

Ошибки: 403 — чужая услуга; 404 — отсутствующая/скрытая запись;
409 — повторный черновик, недопустимый статус или занятый логин/email;
413 — превышен размер; 422 — неверные поля/файлы; 503 — отказ MinIO.
Пароли новых пользователей хранятся как scrypt-хеш, в ответах не возвращаются.
Старые пользователи ЛР2 без пароля получают техническое значение `legacy-account`;
оно не используется для входа, поскольку login пока является заглушкой.


</details>

---

[Диаграмма классов](architecture_diagram.md) · [Коллекция Postman](postman_collection.json) · [Порядок сдачи](docs/lr3_submission.md) · [Соответствие ЛР3](docs/compliance.md)

## Бизнес-правила

`get_current_user()` в `api/dependencies.py` — общая singleton dependency:
пользователь всегда определяется константой `CURRENT_USER_ID = 1`.
FastAPI переиспользует результат в пределах запроса. Регистрация, login/logout
не меняют текущего создателя: полноценная авторизация относится к ЛР4.

У пользователя не более одного черновика. Разрешены только переходы
`draft → published`, `draft → deleted`, `published → deleted`.
Публикация и удаление доступны только создателю. Возврата в черновик нет.
Удаление сохраняет строку и файлы: это soft delete. Удалённые и чужие
черновики не выдаются в списке/ленте; даже страница ошибки не раскрывает их поля.

`id`, `status`, `creator_id`, `moderator_id`, `created_at`, `formed_at`,
`completed_at` нельзя передать для изменения. Дополнительные входные поля
отклоняются с 422. Создание вычисляет `created_at` и создателя; публикация
выставляет `formed_at`; удаление — `completed_at`. У черновика `formed_at=NULL`.
Модератор остаётся NULL: в задании нет метода модерации. Даты — UTC.

Лайки доступны только опубликованным услугам. Повторная установка/отмена
идемпотентна; уникальная пара пользователь–услуга исключает дубли.

## Страницы приложения

| URL | Шаблон | Используемые сценарии |
|---|---|---|
| `/api/pages/isotopic_signatures/list` | `tiles.html` | Общая ORM-выборка списка; JS вызывает DELETE API только для своих услуг |
| `/api/pages/isotopic_signatures/feed/{id}` | `feed.html` | Общая выборка ленты; JS вызывает GET следующей записи и POST like |
| `/api/pages/isotopic_signatures/draft` | `add.html` | Общая выборка собственного черновика; POST с файлами, PUT публикации, DELETE черновика |
| `/api/pages/isotopic_signatures/unavailable` | `deleted.html` | Нейтральная страница 404 без полей записи; общая выборка для навигации |

Шаблоны первоначально формируются сервером; сценарии изменения данных используют
те же JSON API, что и будущая SPA. Старых POST-обработчиков HTML больше нет.
Служебные GET: `/api/docs`, `/api/docs/oauth2-redirect`, `/api/redoc`,
`/api/openapi.json`; `/static/{path}` обслуживает CSS/JS и локальные запасные медиа.

## Запуск

Python 3.10+, Docker и Docker Compose:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d --wait
python main.py
```

При запуске Alembic создаёт новую схему или обновляет старую схему ЛР2
без удаления записей, затем настраивается MinIO и добавляются демонстрационные
данные в пустую БД. В MinIO помещаются настоящие демонстрационные фото/видео.
Если БД или MinIO недоступны, запуск завершается с ошибкой, а не имитирует успех.
Перед обновлением собственной БД рекомендуется сохранить её резервную копию.
Обратная миграция с удалением новых полей не предусмотрена.

- Каталог: http://localhost:8000/api/pages/isotopic_signatures/list
- Лента: http://localhost:8000/api/pages/isotopic_signatures/feed/1
- Создание/публикация: http://localhost:8000/api/pages/isotopic_signatures/draft
- Недоступная запись: http://localhost:8000/api/pages/isotopic_signatures/unavailable
- Swagger: http://localhost:8000/api/docs
- Adminer: http://localhost:8080 — PostgreSQL, сервер `postgres`,
  БД `isoarch_db`, пользователь `isoarch_user`, пароль `isoarch_password`.
- MinIO: API http://localhost:9000, консоль http://localhost:9001,
  пользователь `root`, пароль `rootpassword`.

Настройки через переменные окружения:

| Переменная | По умолчанию |
|---|---|
| `DATABASE_URL` | `postgresql://isoarch_user:isoarch_password@localhost:5432/isoarch_db` |
| `MINIO_ENDPOINT` | `http://localhost:9000` |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | `root` / `rootpassword` |
| `MEDIA_BUCKET` | `isoarchservice` |

Для тестов поддерживается `DATABASE_URL=sqlite:///...`: частичный уникальный
индекс черновика есть и для SQLite. Основная БД лабораторной — PostgreSQL.
Порт MinIO должен быть доступен браузеру, поскольку API возвращает URL медиа.

## Проверки и сдача

```bash
pip install -r requirements-dev.txt
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

HTTP-тесты используют SQLite в памяти и имитируют MinIO; миграции проверяются
на пустой БД и старой схеме с сохранением данных. Настоящие PostgreSQL/MinIO
проверяются отдельно командой `python scripts/check_integration.py` с явными
тестовыми настройками окружения и `LR3_INTEGRATION=1`. Эта проверка создаёт
демонстрационную услугу и пользователя в выбранной тестовой БД.

[Диаграмма](architecture_diagram.md), [Postman](postman_collection.json),
[порядок сдачи](docs/lr3_submission.md), [SELECT](docs/lr3_select.sql),
[контрольные вопросы](docs/control_questions.md), [этапы исправлений](AGENTS.md).
Результат интеграционной проверки сохраняется в `docs/verification.json`.
Postman-коллекция проверена Newman: 21 проверка без ошибок; краткий результат —
`docs/postman_verification.json`. Браузерные результаты —
`docs/browser_verification.json`, реальные снимки интерфейса — `docs/screenshots/`.
Эти снимки не заменяют скриншоты Postman/SQL-клиента из порядка сдачи.

При наличии Node.js и Playwright браузерную проверку можно повторить на
отдельном тестовом сервере:

```bash
npm install --prefix /tmp/isoarch-playwright playwright
node /tmp/isoarch-playwright/node_modules/playwright/cli.js install chromium
LR3_INTEGRATION=1 LR3_BASE_URL=http://127.0.0.1:58000 \
LR3_PLAYWRIGHT_MODULE=/tmp/isoarch-playwright/node_modules/playwright \
node scripts/browser_check.cjs
```

Для существующего Chromium можно указать `LR3_CHROME_PATH`. Среда должна
содержать системные библиотеки, необходимые браузеру.

Остановка: `Ctrl+C`, затем `docker compose down`; данные в volumes сохраняются.
