# Проверка обновлённой ЛР3 — 14 октября 2026

Все команды выполняются из корня проекта. Нужны запущенные PostgreSQL и MinIO.
HTTP-тесты, сетевые проверки и Chromium запускались вне песочницы с разрешением.

## API и миграции

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

Результат: 22 теста, OK. Включены точный контракт 10 операций, совпадение
Postman/OpenAPI, персональный is_liked, фильтрация deleted_at, жизненный цикл,
владение, защищённые поля, ошибки MinIO, ограничения и миграции SQLite.

## Отдельная интеграционная среда

Однократно создана БД (повторно создавать существующую не требуется):

```bash
docker compose exec -T postgres createdb -U isoarch_user isoarch_lr3_audit_20261014
```

В терминале тестового сервера:

```bash
export DATABASE_URL=postgresql://isoarch_user:isoarch_password@localhost:5432/isoarch_lr3_audit_20261014
export MINIO_ENDPOINT=http://localhost:9000
export MEDIA_BUCKET=isoarch-lr3-audit-20261014
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 58000
```

В другом терминале, с теми же тремя переменными:

```bash
LR3_INTEGRATION=1 PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python scripts/check_integration.py
```

Результат: 29 проверок, включая чтение загруженных байтов MinIO,
soft delete с сохранением записи/лайка и миграцию прежней схемы PostgreSQL.
Отчёт: `docs/verification.json`.

## Postman / Newman

```bash
npm install --prefix /tmp/isoarch-lr3-tools newman
/tmp/isoarch-lr3-tools/node_modules/.bin/newman run postman_collection.json \
  --env-var base_url=http://127.0.0.1:58000 --working-dir . \
  --reporters cli,json --reporter-json-export /tmp/isoarch-lr3-newman.json
```

Результат: 10 основных запросов, 3 дополнительных GET в Tests, 24 assertions,
0 failures. Краткий отчёт: `docs/postman_verification.json`.

## Браузер

Использованы уже установленные Playwright, Chromium headless shell и временные
библиотеки. Эти пути относятся к текущему окружению; для другого окружения
установка описана в README.

```bash
LR3_INTEGRATION=1 LR3_BASE_URL=http://127.0.0.1:58000 \
LR3_PLAYWRIGHT_MODULE=/tmp/isoarch-lr4-browser/node_modules/playwright \
LR3_CHROME_PATH=/home/delomane/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell \
LD_LIBRARY_PATH=/tmp/isoarch-lr4-libs/root/usr/lib/x86_64-linux-gnu \
node scripts/browser_check.cjs
```

Результат: 10 проверок, 0 ошибок JavaScript. Проверены появление подписи «Вы поставили лайк»
при лайке, её отсутствие до лайка и после отмены, число лайков, создание с файлами, публикация, переходы,
фильтр, удаление своей записи и скрытие удалённых данных.
Отчёт: `docs/browser_verification.json`; пять свежих снимков: `docs/screenshots/`.
Обычный Chromium не смог снять экран; итоговый успешный прогон выполнен
headless shell. Ошибка ожидания URL DELETE в проверочном скрипте исправлена.

## Дополнительная проверка

`git diff --check`, разбор Python-файлов через `ast.parse`, `node --check` для
изменённых JS/CJS прошли. Основной сервер `localhost:8000` вернул 200 и
актуальный JSON с deleted_at/is_liked. Тестовый сервер после проверки остановлен;
основной оставлен работающим. Тестовые БД и объекты сохранены.

Обновлённые пользовательские скриншоты Postman/Insomnia/SQL-клиента не снимались.
Порядок их подготовки: `docs/lr3_submission.md`.
