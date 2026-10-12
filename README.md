# IsoArch — изотопные сигнатуры, ЛР2

Учебное приложение для хранения результатов изотопного анализа костных
останков: δ¹⁵N, δ¹³C, описание, фото и видео. FastAPI и Jinja2 формируют
страницы на сервере; SQLAlchemy работает с PostgreSQL. MinIO хранит медиа.

## Запуск

```bash
docker compose up -d
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Приложение создаёт таблицы и демонстрационные данные в базе `isoarch_lr2_db`.
Если база ещё не создана:

```bash
docker compose exec postgres createdb -U isoarch_user -O isoarch_user isoarch_lr2_db
```

Эта база отделена от `isoarch_db`, используемой ЛР3. Подключение можно
переопределить через `DATABASE_URL`. Медиа настраиваются через
`MINIO_ENDPOINT` (по умолчанию `http://localhost:9000`) и
`MEDIA_BUCKET` (по умолчанию `isoarchservice`).

- Каталог: http://127.0.0.1:8000/isotopic_signatures/list
- Добавление: http://127.0.0.1:8000/isotopic_signatures/draft
- Лента: http://127.0.0.1:8000/isotopic_signatures/feed/1
- Adminer: http://localhost:8080 — PostgreSQL, сервер `postgres`,
  пользователь `isoarch_user`, пароль `isoarch_password`, база `isoarch_lr2_db`.
- MinIO: http://localhost:9001 — `root` / `rootpassword`.

## Структура

- `api/handlers.py` — шесть HTTP-контроллеров.
- `core/config.py` — настройки.
- `db/base.py`, `db/session.py`, `db/raw_queries.py` — база моделей, сессии и курсор.
- `models/` — пользователи, сигнатуры, лайки.
- `repositories/isotopic_signatures.py` — запросы ORM и SQL UPDATE.
- `services/` — сценарии приложения, форматирование и URL медиа.
- `templates/` — каталог, лента, добавление и страница удалённой записи.
- `static/` — CSS, локальное превью, фото и видео по умолчанию.
- `data/collections.py` — неиспользуемая коллекция из ЛР1.

Три GET: каталог, лента, черновик. Три POST: создание, публикация,
`/isotopic_signatures/{id}/delete`. Удаление меняет статус через SQL-курсор.
Следующий ID выбирается в БД, просмотр удалённой записи возвращает 404.
Пользователь фиксирован (`CURRENT_USER_ID = 1`), лайки только отображаются.
Выбранные файлы используются для локального превью и не отправляются.
Даты создания и формирования выставляются автоматически.

## Проверки

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

Тесты используют SQLite в памяти. Для сдачи отдельно нужны ER-диаграмма
StarUML, наполнение/изменение данных в Adminer и скриншоты.
Список требований и оставшихся недочётов находится в `AGENTS.md`.
