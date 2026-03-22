![SyharikTS Logo](frontend/public/logo.png)

# SyharikTS

SyharikTS — full-stack сервис генерации TypeScript-кода по входному файлу и JSON-примеру структуры результата.
Проект включает веб-приложение и Telegram-бот со связывае​мым веб-аккаунтом.

## Что в проекте

- `backend` — FastAPI API: auth, генерация TS, infer-schema, history, мониторинг, Telegram internals.
- `frontend` — React/Vite SPA: страницы Login/Register/Upload/Profile/TechInfo.
- `telegram-bot` — aiogram сервис, который вызывает backend internal endpoints.
- `backend/migrations` — SQL-схема таблиц и индексов.

## Ключевые возможности и преимущества

- Детерминированный prompt: чёткие правила и fallback-логика, исключает лишнюю вариативность LLM.
- Регистрация/вход/refresh-token, подтверждение email, сброс пароля.
- Поддержка многопоточности и асинхронного FastAPI.
- Генерация TypeScript парсеров из табличных/документных/ocr/изображений.
- Авто-инферс структуры через `/infer-schema`.
- Кэш генераций по fingerprint (вход + prompt вариант) для экономии токенов.
- История генераций и токен-статистика пользователя (`/me/generations`, `/me/token-usage`).
- Telegram-привязка `/link` и генерация через бота.
- PostgreSQL: надёжная БД с миграциями и аналитикой.
- Удобный фронтенд: upload, schema, live-code, usage/metrics.
- Docker-контейнеризация (`docker compose up --build`) и масштабируемость.
- Cloud-Ready сервис

## Поддерживаемые входные форматы

- Таблицы: `csv`, `xls`, `xlsx`
- Документы/текст: `pdf`, `docx`, `txt`, `md`, `rtf`, `odt`, `xml`, `epub`, `fb2`, `doc`
- Изображения (OCR): `png`, `jpg`, `jpeg`, `tiff`, `tif`

## Архитектура

В папке `architecture` находятся схемы и диаграммы:

#### Последовательность генерации

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant B as Backend API
    participant FP as File Parser
    participant GC as Generation Cache
    participant PB as Prompt Builder
    participant LC as LLM Client
    participant DB as Database
    participant LF as Langfuse

    U->>F: Upload file & schema
    F->>B: POST /generate (file, schema, auth)
    B->>FP: Parse file to text/data
    FP-->>B: Parsed content
    B->>GC: Check fingerprint cache
    alt Cache hit
        GC-->>B: Cached result
        B-->>F: Return cached TS code
    else Cache miss
        B->>PB: Build prompt
        PB-->>B: Prompt ready
        B->>LC: Call LLM with prompt
        LC->>LF: Start trace
        LC->>LC: Send to LLM API
        LC-->>B: TS code response
        B->>DB: Save generation history
        B->>GC: Store in cache
        B-->>F: Return TS code
    end
    F-->>U: Display generated code
```

## Стек технологий

-`Python: fastapi, pandas, PIL, beautifulsoap4...`
-`React`
-`TypeScript`
-`Docker`
-`PostreSQL`

## Быстрый старт

### 1. Подготовка `.env`

```bash
cp .env.example .env
```

Заполните минимум:
- `DATABASE_URL`
- `JWT_SECRET`
- `RECAPTCHA_SECRET_KEY` + `VITE_RECAPTCHA_SITE_KEY`
- SMTP-настройки (если email)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_INTERNAL_TOKEN`

### 2. Миграции

```bash
bash scripts/run_migrations.sh
```

### 3. Запуск через Docker

```bash
docker compose up --build
```

Frontend: `http://localhost:5173`, backend: `http://localhost:8000`.

### 4. Локально frontend

```bash
cd frontend
npm install
npm run dev
```

## Распространённый деплой на свой сервер

1. Установите Docker и Docker Compose на сервер.
2. Склонируйте репозиторий, перейдите в корень:

```bash
git clone <repo-url> syharikts
cd syharikts
```

3. Создайте `.env` из шаблона:

```bash
cp .env.example .env
```

4. Установите обязательные переменные (пример):

```bash
export DATABASE_URL=postgresql+asyncpg://user:pass@127.0.0.1:5432/syharikts
export JWT_SECRET="ОченьСекретнаяСтрока"
export RECAPTCHA_SECRET_KEY="..."
export VITE_RECAPTCHA_SITE_KEY="..."
export SMTP_HOST="smtp.example.com"
export SMTP_PORT="587"
export SMTP_USER="..."
export SMTP_PASSWORD="..."
export SMTP_FROM="noreply@example.com"
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_BOT_USERNAME="syharikts_bot"
export TELEGRAM_INTERNAL_TOKEN="зашифрованный_секрет"
```

5. Создайте и запустите базу Postgres на сервере (docker/локальная). Пример через Docker:

```bash
docker run -d --name syharikts-db -e POSTGRES_USER=user -e POSTGRES_PASSWORD=pass -e POSTGRES_DB=syharikts -p 5432:5432 postgres:15
```

6. Запустите миграции:

```bash
bash scripts/run_migrations.sh
```

7. Запустите сервисы через Docker Compose:

```bash
docker compose up -d --build
```

Важно отметить, что телеграм бот вынесен в отдельный контейнер и если вы не хотите его билдить, то достаточно закомментить соответсвующие строки в  yml файле

8. Проверьте доступ:
- Backend: `http://<server-ip>:8000/health`
- Frontend: `http://<server-ip>:5173` (если используется прокси/nginx)
- Swagger: `http://<server-ip>:8000/docs`

9. Настройте прокси nginx (опционально) для HTTPS и `/` маршрутизации:

```nginx
server {
  listen 80;
  server_name your.domain.com;

  location / {
    proxy_pass http://127.0.0.1:5173;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }

  location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }
}
```

10. Для HTTPS используйте `certbot`.

11. Перезапуск:

```bash
docker compose down && docker compose up -d --build
```

## Список эндпоинтов (см. API.md)

- `GET /health`
- `POST /auth/register`, `/auth/verify-email`, `/auth/resend-registration-code`, `/auth/login`, `/auth/refresh`, `/auth/reset-request`, `/auth/reset-confirm`, `GET /auth/me`
- `PATCH /profile`
- `GET /me/generations`, `GET /me/generations/{generation_id}`, `GET /me/generations/{generation_id}/check-input`, `GET /me/token-usage`
- `POST /generate`, `POST /infer-schema`
- `POST /me/telegram/link-code`, `GET /me/telegram/status`, `POST /me/telegram/unlink`
- `POST /telegram/consume-link`, `GET /telegram/me`, `POST /telegram/generate`
- `GET /stats/generations`, `GET /observability/summary`

## Важные переменные окружения (все поддерживается из кода)

см. разделы Core/Auth, Generation/LLM, Observability, Telegram в оригинале.

## Тесты

Backend:

```bash
cd backend
python -m unittest discover -s tests -v
```