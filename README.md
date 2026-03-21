# SyharikTS

Веб‑сервис генерации TypeScript‑кода функции по загруженному файлу и JSON‑примеру структуры выходных данных. Проект создан командой 42x САУ "Хакатон Весна 2026" партнёр Сбербанк.

## Что умеет

- Регистрация и вход (**email**, **логин**, **пароль**), подтверждение email кодом из письма, сброс пароля.
- Загружает файл, парсит данные/текст и формирует `extracted_input_json`.
- Генерирует TypeScript-код через LLM (`/generate`) — **только для авторизованных пользователей**.
- Строит пример схемы по файлу (`/infer-schema`) — **только для авторизованных пользователей**.
- Хранит историю генераций и позволяет управлять профилем пользователя (`/profile`) — тоже **только для авторизованных пользователей**.
- Возвращает стабильные коды ошибок парсинга (`UNSUPPORTED_FILE_TYPE`, `OCR_NO_TEXT`, `TEXT_DECODE_FAILED`).

## Поддерживаемые форматы

- Табличные: `csv`, `xls`, `xlsx`
- Документы/текст: `pdf`, `docx`, `txt`, `md`, `rtf`, `odt`, `xml`, `epub`, `fb2`, `doc`
- Изображения (OCR): `png`, `jpg`, `jpeg`, `tiff`, `tif`

## Стек

- Backend: `Python`, `FastAPI`, `LangChain`
- Frontend: `React` (`Vite`)
- Контейнеризация: `Docker`, `docker compose`

## Быстрый старт

### 1) Подготовка окружения

Скопируйте `.env` из примера:

```bash
copy .env.example .env
```

Или создайте вручную и заполните нужные переменные.

### 2) Запуск backend в Docker

```bash
docker compose up --build
```

Backend будет доступен на `http://localhost:8000`.

### 3) Запуск frontend локально

```bash
cd frontend
npm install
npm run dev
```

Frontend по умолчанию: `http://localhost:5173`.

**Прокси:** при пустом `VITE_API_BASE_URL` dev-сервер Vite перенаправляет `/auth`, `/me`, `/generate`, `/infer-schema`, `/health`, `/stats`, `/observability` и `PATCH /profile` на uvicorn (по умолчанию `http://127.0.0.1:8000`, переопределение: `DEV_API_PROXY_TARGET` в `.env`). На продакшене nginx должен проксировать те же префиксы; образец — [`test_files/nginx.config`](test_files/nginx.config) (`/me`, `/stats`, `/observability` и отдельно `/profile` для PATCH, иначе фронт получит HTML вместо JSON).

## Авторизация и БД

- Таблицы создаются SQL-файлами в `backend/migrations/`:
  - [`backend/migrations/001_auth_tables.sql`](backend/migrations/001_auth_tables.sql) — пользователи/почта/refresh-токены
  - [`backend/migrations/002_generation_history.sql`](backend/migrations/002_generation_history.sql) — история генераций (TS-код + схема)
  - [`backend/migrations/003_generation_history_input_base64.sql`](backend/migrations/003_generation_history_input_base64.sql) — опционально сохраняемый исходный файл (base64) для проверки TS из истории
  - [`backend/migrations/004_generation_history_tokens.sql`](backend/migrations/004_generation_history_tokens.sql) — токены (`prompt/completion/total`) по каждому запросу генерации
  - [`backend/migrations/005_generation_history_cache_fingerprints.sql`](backend/migrations/005_generation_history_cache_fingerprints.sql) — fingerprint-ключи и поля кэша генераций
- На Ubuntu после создания БД (см. `scripts/init_syharikts_db.sh`) примените миграции:
  ```bash
  export DATABASE_URL='postgresql+asyncpg://USER:PASS@127.0.0.1:5432/syharikts'
  bash scripts/run_migrations.sh
  ```
- Скрипты `scripts/*.sh` должны быть с переводами строк **LF** (Linux). Если видите `$'\r': command not found`, см. [`scripts/README.md`](scripts/README.md). В репозитории: `.gitattributes` + `.editorconfig`; после `git pull` при необходимости выполните `git add --renormalize .` один раз.
- Для работы входа и защищённых API нужны **`DATABASE_URL`** и **`JWT_SECRET`** (не менее 32 символов).
- Регистрация и сброс пароля отправляют **6-значный код** на email (настройте **SMTP** в `.env`). Если `SMTP_HOST` пустой, письма не уходят, текст пишется в лог backend (только для разработки).
- **reCAPTCHA v2** (обязательно для регистрации и запроса сброса пароля): ключи в [Google reCAPTCHA](https://www.google.com/recaptcha/admin); в backend — `RECAPTCHA_SECRET_KEY`, при сборке frontend — `VITE_RECAPTCHA_SITE_KEY`. Без секрета backend отклоняет проверку; без site key формы регистрации / шага 1 сброса на фронте заблокированы.

### Маршруты frontend (SPA)

- `/login` — вход и регистрация  
- `/verify-email` — только после успешной регистрации (email хранится в `sessionStorage`, прямой заход редиректит на `/login`); ввод кода и повторная отправка с таймером 1 мин  
- `/reset-password` — запрос кода и установка нового пароля  
- `/upload` — генерация и проверка TS в одном интерфейсе (режимы внутри страницы) — только для авторизованных пользователей  
- `/profile` — профиль и история генераций — только для авторизованных пользователей  
- `/profile/tech` — техническая страница observability/Langfuse — только для авторизованных пользователей  

`POST /generate` и `POST /infer-schema` требуют заголовок **`Authorization: Bearer <access_token>`**.

## API

### Routes
- `POST /auth/register`, `POST /auth/verify-email`, `POST /auth/resend-registration-code`, `POST /auth/login`, `POST /auth/refresh`
- `POST /auth/reset-request`, `POST /auth/reset-confirm`
- `GET /auth/me` (Bearer)
- `PATCH /profile` (Bearer)
- `GET /me/generations` (Bearer)
- `GET /me/generations/{id}` (Bearer)
- `GET /me/generations/{id}/check-input` (Bearer) — сохранённый base64 исходного файла для клиентской проверки (если есть)
- `GET /me/token-usage` (Bearer) — персональная статистика токенов (по запросам + суммы)
- `GET /stats/generations` (Bearer) — общее число генераций за всё время
- `GET /observability/summary` (Bearer) — техническая сводка по observability/Langfuse
- `POST /generate` (Bearer)
- `POST /infer-schema` (Bearer)

### `POST /generate`

Описание:
- Вход:
  - `file` (UploadFile): CSV/XLS/XLSX/PDF/DOCX/PNG/JPG
  - `schema` (str): JSON-строка примера выходной структуры
- Ответ:
  - `GenerateResponse`:
    - `code`: TypeScript строка

Оптимизация токенов:
- backend вычисляет fingerprint входа (`file bytes + schema + file_kind`) и fingerprint генератора (`provider + model + PROMPT_VERSION`);
- если найдена идентичная запись в истории (глобально), возвращается сохранённый `code` без вызова LLM;
- в историю текущего пользователя добавляется audit-запись cache-hit (токены = `0`), без раскрытия чужих метаданных.
- в `GET /observability/summary` доступны метрики эффекта кэша:
  - `generation_cache_total_requests`
  - `generation_cache_hit_count`
  - `generation_cache_hit_ratio`
  - `generation_cache_saved_total_tokens_estimate` (оценка экономии: `cache_hits * avg(total_tokens на cache_miss)`).

Ошибки:
- 401: нет или невалидный Bearer-токен
- 400: missing/invalid input, parse error, invalid schema
- 415: unsupported media type или невалидный файл
- 500: LLM generation error

Пример (подставьте `ACCESS_TOKEN` после `POST /auth/login`):

```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -F "file=@./example.csv" \
  -F 'schema={"dateCreate":"2026-01-01","product":"ABC"}'
```

или с экранированием в bash:

```bash
curl -X POST "http://localhost:8000/generate" \
  -F "file=@./example.csv" \
  -F "schema={\"dateCreate\":\"2026-01-01\",\"product\":\"ABC\"}"
```

### `POST /infer-schema`

Описание:
- Вход:
  - `file` (UploadFile)
- Ответ:
  - `InferSchemaResponse`:
    - `schema`: JSON в строке

Ошибки:
- 400: parse/missing file
- 415: unsupported media type

Пример:

```bash
curl -X POST "http://localhost:8000/infer-schema" \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -F "file=@./example.csv"
```

---

## Профиль и история генераций

### `PATCH /profile`

Описание:
- Вход:
  - `login` (str, опционально)
  - `current_password` (str, обязательно)
  - `new_password` (str, опционально)
- Ответ:
  - `UserPublic`:
    - `id`, `email`, `login`, `is_email_verified`

Ошибки:
- 400: нечего обновлять
- 401: неверный `current_password` или нет Bearer-токена
- 409: `login` уже занят

### `GET /me/generations`

Описание:
- Ответ: массив `GenerationHistoryItem`:
  - `id`
  - `created_at`
  - `main_file_name`

### `GET /me/generations/{id}`

Описание:
- Ответ: `GenerationHistoryDetail`:
  - `id`, `created_at`, `main_file_name`
  - `generated_ts_code`: сгенерированный TypeScript-код (как строка)

## Парсинг и OCR

- Для `txt/md/xml/fb2` используется извлечение текста с декодированием (`utf-8-sig`, `utf-8`, `cp1251`, fallback).
- Для `rtf` используется `striprtf`.
- Для `odt` используется `odfpy`.
- Для `epub` используется `ebooklib` + `BeautifulSoup`.
- Для `doc` используется best-effort извлечение текста из бинарного контента.
- Для изображений (`png/jpg/tiff`) используется локальный OCR через `Tesseract` (backend извлекает текст до этапа LLM-генерации).

Если OCR/декодирование не смогли извлечь текст, backend возвращает контролируемую ошибку с кодом.

## Переменные окружения

### LLM

- `LLM_PROVIDER` (`stub`, `openai_compatible`, `gigachat`)
- `PROMPT_VERSION` (версия шаблона/логики генерации для безопасного cache busting)
- `OPENAI_COMPAT_BASE_URL`
- `OPENAI_COMPAT_API_KEY`
- `OPENAI_COMPAT_MODEL`
- `GIGACHAT_BASE_URL`
- `GIGACHAT_API_KEY`
- `GIGACHAT_AUTHORIZATION_KEY`
- `GIGACHAT_MODEL`
- `GIGACHAT_VERIFY_TLS`
- `GIGACHAT_SCOPE`
- `GIGACHAT_MAX_TOKENS`
- `GIGACHAT_RETRY_ATTEMPTS`
- `GIGACHAT_TIMEOUT_SECONDS`
- `LANGFUSE_ENABLED`
- `LANGFUSE_HOST`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_ENV`
- `LANGFUSE_RELEASE`

### Парсер

- `PARSE_MAX_ROWS`
- `PARSE_MAX_TEXT_CHARS`
- `OCR_LANG` (например, `rus+eng`)
- `OCR_PSM` (режим сегментации страницы)
- `OCR_FALLBACK_PSM` (fallback-режим, используется для TIFF)

### Auth / почта / reCAPTCHA

- `JWT_SECRET`, `JWT_ACCESS_EXPIRE_MINUTES`, `JWT_REFRESH_EXPIRE_DAYS`
- `VERIFICATION_CODE_TTL_MINUTES` (по умолчанию 15)
- `RESEND_VERIFICATION_COOLDOWN_SECONDS` (пауза между повторной отправкой кода регистрации, по умолчанию 60)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_TLS`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`
- `RECAPTCHA_SECRET_KEY` (backend)
- `VITE_RECAPTCHA_SITE_KEY` (сборка frontend)

### Прочее

- `CORS_ALLOW_ORIGINS`
- `VITE_API_BASE_URL` (для frontend)
- `DATABASE_URL`, `DATABASE_CONNECT_TIMEOUT`

Актуальный пример смотрите в `.env.example`.

## Настройка Langfuse (гайд)

### 1) Создайте проект в Langfuse
- Зарегистрируйтесь в Langfuse Cloud или поднимите self-host.
- Создайте проект и получите ключи:
  - `LANGFUSE_PUBLIC_KEY`
  - `LANGFUSE_SECRET_KEY`
- Скопируйте URL инстанса в `LANGFUSE_HOST` (например, `https://cloud.langfuse.com`).

### 2) Настройте переменные окружения backend
В `.env`:

```bash
LANGFUSE_ENABLED=true
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_ENV=prod
LANGFUSE_RELEASE=v0.1.0
```

Важно:
- `LANGFUSE_SECRET_KEY` хранится только на backend.
- Не передавайте secret/public ключи во frontend.

### 3) Примените миграции и перезапустите backend
- Примените SQL миграции, включая `004_generation_history_tokens.sql`.
- Перезапустите backend (`docker compose up --build -d` или ваш способ запуска).

### 4) Проверьте работу
- Выполните несколько `POST /generate`.
- Откройте `/profile/tech`:
  - увидите суммарные токены пользователя;
  - график токенов по последним запросам.
- В Langfuse проверьте появление trace/span для `generate_request`.

### 5) Если видите HTML вместо JSON
- Проверьте nginx-прокси для префиксов:
  - `/me`
  - `/stats`
  - `/observability`
- Иначе frontend получит `index.html` и покажет ошибку JSON parse.

## Тесты

Backend-тесты:

```bash
cd backend
python -m unittest discover -s tests -v
```

Проверка новых API (после авторизации):

```bash
curl -H "Authorization: Bearer ACCESS_TOKEN" http://localhost:8000/stats/generations
curl -H "Authorization: Bearer ACCESS_TOKEN" http://localhost:8000/observability/summary
```

Покрыты базовые сценарии:

- детекция форматов
- парсинг `txt/md/xml/rtf`
- контролируемые ошибки unsupported/OCR

## Важные замечания

- Для `doc` используется эвристический best-effort парсинг (без внешних системных утилит).
- Качество OCR зависит от качества изображения и установленного языка Tesseract (`OCR_LANG`).
- В production рекомендуется ограничивать `PARSE_MAX_TEXT_CHARS` и `PARSE_MAX_ROWS`.