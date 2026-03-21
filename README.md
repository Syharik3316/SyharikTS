# SyharikTS

SyharikTS — full-stack сервис генерации TypeScript-кода по входному файлу и JSON-примеру структуры результата.  
Проект включает веб-приложение и Telegram-бота с привязкой к веб-аккаунту.

## Что в проекте

- `backend` — FastAPI API, авторизация, генерация, кэш по fingerprint, история, статистика токенов.
- `frontend` — React/Vite SPA (авторизация, upload/generate, профиль, техническая статистика).
- `telegram-bot` — отдельный сервис на aiogram (меню Профиль/Генерация, связка с веб-аккаунтом).
- `backend/migrations` — SQL миграции схемы БД.

## Основные возможности

- Регистрация/логин, подтверждение email, сброс пароля.
- Генерация TS-кода через `POST /generate` только для авторизованных.
- Автоинференс JSON-примера из файла через `POST /infer-schema`.
- История генераций и статистика токенов в профиле.
- Telegram-привязка через одноразовый `/link XXXXXX` код из веб-профиля.
- Генерация в Telegram доступна только привязанным пользователям.
- Кэш генераций по fingerprint: при совпадении входа возвращается готовый TS без повторного LLM-вызова.

## Поддерживаемые входные файлы

- Таблицы: `csv`, `xls`, `xlsx`
- Документы/текст: `pdf`, `docx`, `txt`, `md`, `rtf`, `odt`, `xml`, `epub`, `fb2`, `doc`
- Изображения (OCR): `png`, `jpg`, `jpeg`, `tiff`, `tif`

## Архитектура

- **Backend — источник истины**: Telegram-бот не дублирует бизнес-логику, а ходит в backend.
- **Web API**:
  - публичные и защищенные auth/profile/generate endpoints,
  - Telegram endpoints для веба (`/me/telegram/*`) и внутренние bot->backend (`/telegram/*`).
- **DB**:
  - пользователи, refresh-токены, история генераций,
  - токены LLM (`prompt/completion/total`),
  - поля Telegram у пользователя,
  - одноразовые link-коды (`telegram_link_codes`).

## Быстрый старт

### 1. Подготовка `.env`

```bash
copy .env.example .env
```

Заполните минимум:
- `DATABASE_URL`
- `JWT_SECRET`
- `RECAPTCHA_SECRET_KEY` + `VITE_RECAPTCHA_SITE_KEY`
- SMTP-переменные (если нужны реальные письма)
- Telegram-переменные (если запускаете бота):
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_BOT_USERNAME`
  - `TELEGRAM_INTERNAL_TOKEN`

### 2. Применение миграций

```bash
bash scripts/run_migrations.sh
```

Или вручную примените SQL-файлы из `backend/migrations` по порядку.

### 3. Запуск сервисов

```bash
docker compose up --build
```

Сервисы:
- backend: `http://localhost:8000`
- telegram-bot: отдельный polling-процесс

### 4. Локальный запуск frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

## Важные переменные окружения

### Core/Auth

- `DATABASE_URL`
- `JWT_SECRET`
- `JWT_ACCESS_EXPIRE_MINUTES`
- `JWT_REFRESH_EXPIRE_DAYS`
- `CORS_ALLOW_ORIGINS`

### Generation/LLM

- `LLM_PROVIDER`
- `PROMPT_VERSION`
- `OPENAI_COMPAT_*` или `GIGACHAT_*`
- `PARSE_MAX_ROWS`, `PARSE_MAX_TEXT_CHARS`
- `OCR_LANG`, `OCR_PSM`, `OCR_FALLBACK_PSM`
- `GENERATION_HISTORY_MAX_INPUT_BYTES`

### Observability

- `LANGFUSE_ENABLED`
- `LANGFUSE_HOST`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_ENV`
- `LANGFUSE_RELEASE`

### Telegram

- `TELEGRAM_BOT_TOKEN` — токен BotFather.
- `TELEGRAM_BOT_USERNAME` — username бота (для ссылки в UI).
- `TELEGRAM_INTERNAL_TOKEN` — общий секрет bot->backend (`X-Internal-Token`).
- `BACKEND_INTERNAL_URL` — URL backend для сервиса бота.
- `TELEGRAM_LINK_TTL_MINUTES` — время жизни link-кода.
- `TELEGRAM_LINK_MAX_ATTEMPTS` — лимит попыток кода.
- `TELEGRAM_BACKEND_TIMEOUT_SECONDS` — timeout запросов бота к backend.

## Telegram flow

1. Пользователь логинится на сайте.
2. В `Профиль` нажимает «Получить код привязки».
3. Получает команду вида `/link XXXXXX`.
4. Отправляет команду в Telegram-боте.
5. После успешной связки доступны:
   - `Профиль` (имя/почта, последние генерации, токен-статистика),
   - `Генерация` (файл -> JSON -> TS).

Если пользователь не привязан, генерация в боте блокируется с инструкцией по привязке.

## API и контракты

Полная спецификация с endpoint’ами, payload’ами и примерами — в [`API.md`](API.md).

## Тесты

Backend:

```bash
cd backend
python -m unittest discover -s tests -v
```

Быстрая проверка OpenAPI:

```bash
cd backend
python -m unittest tests.test_openapi_auth -v
```

## Troubleshooting

- Если видите HTML вместо JSON во frontend:
  - проверьте `VITE_API_BASE_URL` и Vite/nginx proxy на `/auth`, `/me`, `/generate`, `/infer-schema`, `/stats`, `/observability`, `/profile`.
- Если бот получает `401` на внутренних endpoint’ах:
  - проверьте совпадение `TELEGRAM_INTERNAL_TOKEN` у backend и telegram-bot.
- Если `/link` не работает:
  - проверьте TTL/попытки (`TELEGRAM_LINK_TTL_MINUTES`, `TELEGRAM_LINK_MAX_ATTEMPTS`) и применены ли миграции.