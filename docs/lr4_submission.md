# ЛР4: соответствие требованиям и демонстрация

Проект ЛР3 доработан под [Lab4_FastAPI.md](../Lab4_FastAPI.md) и
[Redis_Lab4.md](../Redis_Lab4.md). Предметная область — изотопные исследования.

| Требование | Реализация |
|---|---|
| AJAX + REST + SPA | `templates/spa.html`, `static/js/spa.js`; fetch, hash-маршруты |
| 4 экрана + авторизация + редактирование | Каталог, лента, черновик, недоступная запись, вход/регистрация, редактирование |
| Общая диаграмма, ≥10 методов, 3 модели + БД | [Диаграмма](lr4_architecture.md), 12 методов, User/IsotopicSignature/SignatureLike |
| Регистрация, вход, выход | `/auth/register`, `/auth/login`, `/auth/logout` |
| Сессии Redis и cookie | UUID в HttpOnly `session_id`; Redis хранит SHA-256 токена → user_id с TTL |
| Публичное чтение и флаг авторства 0/1 | `/services`, `/services/feed`, `is_creator` |
| Единственный черновик по сессии | `/services/draft`; частичный уникальный индекс PostgreSQL |
| Автор назначается сервером, бинарные файлы | `POST /services`, UploadFile/File, multipart; MinIO |
| Публикация и поля | `PUT /services/{id}`; публикация и повторное редактирование только автором |
| Soft delete только автором | `DELETE /services/{id}`; статус deleted, данные сохраняются |
| Лайк 1/0 | `POST /services/{id}/like`; уникальная пара пользователь–исследование |
| HTTP-коды вместо статуса операции в JSON | 200/201/204, 401/403/404/409/422/503; `detail` для ошибок |
| APIRouter, Depends, Pydantic, Swagger | `api/`, `/docs`, `/openapi.json`, схема SessionCookie |

Поле `status` исследования обозначает состояние записи, а не успех операции.
Регистрация и вход доступны гостям; изменения требуют действующей сессии.
Черновик также требует входа, хотя запрашивается методом GET.

## Порядок показа

1. Запустить проект по README. Открыть `/` и `/docs` без входа: список и лента
   читаются, запрос черновика и изменения дают 401.
2. Зарегистрироваться и войти. В Postman взять UUID из `Set-Cookie` и вручную
   задать `Cookie: session_id=<UUID>` в Headers. В задании встречаются оба
   написания; сервер принимает и `session-id`, и `session_id`. Браузер использует `session_id`.
3. Проверить Redis: команды ниже показывают ключ, ID пользователя и TTL.
4. Загрузить PNG/JPEG/WebP и короткий MP4 через экран добавления. Проверить
   `/services/draft` без ID. Второй черновик даёт 409.
5. Заполнить описание, δ¹⁵N, δ¹³C и опубликовать. Проверить `is_creator=1`,
   фильтрацию, ленту, лайк 1 и снятие лайка 0. В каталоге нажать «Изменить»,
   исправить название/описание/изотопы и сохранить. Повторный PUT не меняет дату публикации.
6. Во втором браузере войти другим пользователем. Проверить `is_creator=0`,
   собственный черновик и запрет изменения чужой записи (403).
7. Автором удалить публикацию. API скрывает её (404), строка PostgreSQL остаётся
   со статусом deleted, медиа и лайки сохранены.
8. Выйти и повторить запрос со старым UUID: 401, ключ Redis удалён.

## Просмотр Redis

```bash
docker compose exec redis redis-cli PING
docker compose exec redis redis-cli --scan --pattern 'isoarch:session:*'
docker compose exec redis redis-cli GET 'isoarch:session:<хеш из предыдущей команды>'
docker compose exec redis redis-cli TTL 'isoarch:session:<хеш из предыдущей команды>'
docker compose exec redis redis-cli CLIENT LIST
docker compose exec redis redis-cli EVAL "$(cat services/active_logins.lua)" 1 isoarch:usernames 'isoarch:session:*'
```

`PING` возвращает PONG. `GET` возвращает ID пользователя, `TTL` — оставшиеся
секунды. Токен cookie не хранится в открытом виде. Истечение TTL удаляет сессию
автоматически. Повторный вход заменяет ключ текущего браузера атомарно через
MULTI/EXEC. Несколько браузеров могут иметь независимые сессии.
`EVAL` выполняет Lua-скрипт `services/active_logins.lua`: он атомарно перебирает
сессии и возвращает пары «логин — число сессий». Логины берутся из хеша
`isoarch:usernames`, который заполняется при входе.

## Автоматические проверки

Проверено 14.10.2026: 28 тестов API/миграций, 35 интеграционных проверок
с PostgreSQL/Redis/MinIO и 8 групп браузерных проверок прошли. Postman-коллекция: 18 запросов,
31 проверка — успешно. Swagger использует локальные JS/CSS и работает без CDN.
Отчёты: [интеграция](lr4_integration_verification.json),
[браузер](lr4_browser_verification.json), [Postman](lr4_postman_verification.json), [скриншоты](lr4_screenshots/).

```bash
pip install -r requirements-dev.txt
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
node --check static/js/spa.js
node --check scripts/browser_check.cjs
```

HTTP-тесты используют SQLite, fakeredis и имитацию MinIO. Они проверяют также
TTL, замену и отзыв сессии, права двух пользователей и ответы 503 при отказе Redis.
Миграционные тесты проверяют сохранение данных и паролей ЛР3.
Таблица `auth_sessions` из промежуточной версии сохранена для совместимости
миграций; действующие сессии хранятся исключительно в Redis.

Для полной проверки используются отдельные сервисы, без изменения данных
основного приложения. В трёх терминалах из корня репозитория:

```bash
LR4_POSTGRES_PORT=25432 docker compose -p isoarch-lr4-check -f docker-compose.test.yml up -d --wait
```

Настройки для терминалов с сервером и интеграционным скриптом:

```bash
export DATABASE_URL=postgresql://isoarch_test:test_password@127.0.0.1:25432/isoarch_test
export MINIO_ENDPOINT=http://127.0.0.1:59000
export REDIS_URL=redis://127.0.0.1:56379/0
export PYTHONDONTWRITEBYTECODE=1
```

Сервер:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 58000
```

Интеграционная проверка:

```bash
LR4_INTEGRATION=1 python -m scripts.check_integration
```

Браузерная проверка (нужны Node.js, Playwright, Chromium и его системные библиотеки):

```bash
npm install --prefix /tmp/isoarch-lr4-browser playwright
/tmp/isoarch-lr4-browser/node_modules/.bin/playwright install chromium
LR4_INTEGRATION=1 LR4_PLAYWRIGHT_MODULE=/tmp/isoarch-lr4-browser/node_modules/playwright node scripts/browser_check.cjs
```

При необходимости путь к браузеру задаётся `LR4_CHROME_PATH`. Базовый URL
для скриптов — `LR4_BASE_URL`, по умолчанию `http://127.0.0.1:58000`.

Postman-коллекции не содержат переменных: адрес `http://localhost:8000`,
ID записи и UUID в `Cookie` записаны явно. Перед запуском вставьте UUID из
`Set-Cookie` вместо `00000000-0000-0000-0000-000000000000` и ID своего черновика
вместо `0` в URL; запросы выполняются по одному в Postman. Отчёт
`lr4_postman_verification.json` получен прежней версией коллекции с переменными.

Результаты полной проверки записываются в `lr4_integration_verification.json`
и `lr4_browser_verification.json`; скриншоты — `lr4_screenshots/`.
Скрипты создают собственных пользователей и публикации; повторный запуск допустим.

После проверки остановить сервер и тестовые сервисы:

```bash
docker compose -p isoarch-lr4-check -f docker-compose.test.yml down
```

Данные этого окружения временные (tmpfs). Старые отчёты без префикса `lr4_`
относятся к ЛР3.
