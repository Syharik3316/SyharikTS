# Converter Agent MVP

MVP веб‑сервиса генерации TypeScript‑кода функции по загруженному файлу и JSON‑примеру структуры выходных данных.

## Стек

- Backend: Python + FastAPI + LangChain
- Frontend: React (Vite)
- Контейнеризация: Docker + docker-compose

## Быстрый старт (Docker)

1. Создайте файл `converter-agent/.env` (или используйте `converter-agent/.env.example`).
2. Запустите:

```bash
docker compose up --build
```

Сервис:
- Backend: http://localhost:8000
- Frontend: http://localhost:5173

## API

`POST /generate` (`multipart/form-data`)

- `file`: загружаемый файл (CSV/XLS/XLSX/PDF/DOCX/PNG/JPG)
- `schema`: JSON‑строка с примером структуры выходного объекта (например `{"dateCreate":"2026-01-01","product":"ABC"}`)

Ответ:

```json
{ "code": "export default function ... " }
```

Требование:
- Вызовы защищены JWT. Отправляйте заголовок `Authorization: Bearer <accessToken>`.

Пример:

```bash
curl -X POST "http://localhost:8000/generate" ^
  -F "file=@./example.csv" ^
  -F "schema={\"dateCreate\":\"2026-01-01\",\"dateLastUpdate\":\"2026-01-02\",\"product\":\"ABC\"}"
```

`POST /infer-schema` (`multipart/form-data`)

- `file`: загружаемый файл
- Ответ: `{ "schema": "{\"field\":\"example\"}" }`

Требование:
- Также защищено JWT: `Authorization: Bearer <accessToken>`.

## Авторизация (JWT + email-код)

Роуты (все требуют `ReCaptcha v2` токен для операций, где это указано ниже):

1. Регистрация:
   - `POST /auth/register` (`email`, `login`, `password`, `recaptchaToken`)
   - Сервер отправляет код подтверждения на email
2. Подтверждение email:
   - `POST /auth/verify-email` (`email`, `code`)
3. Вход:
   - `POST /auth/login` (`identifier` = email или login, `password`, `recaptchaToken`)
   - Ответ: `{ "accessToken": "...", "user": { "id", "email", "login", "emailVerified" } }`
4. Восстановление пароля:
   - `POST /auth/request-password-reset` (`identifier`, `recaptchaToken`)
   - `POST /auth/reset-password` (`identifier`, `code`, `newPassword`)

Дополнительно:
- `GET /auth/me` — получить данные текущего пользователя (требует `Authorization: Bearer <accessToken>`).

## Auth/Email/Captcha (ReCaptcha v2 + MySQL + SMTP)

Backend:
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` (MySQL; при отсутствии будет использован `sqlite auth.db`)
- `JWT_SECRET`, `JWT_ACCESS_EXPIRES_MINUTES`
- `RECAPTCHA_V2_SECRET_KEY`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`
- `AUTH_CODE_TTL_SECONDS`

Frontend:
- `VITE_RECAPTCHA_SITE_KEY` (должен соответствовать `RECAPTCHA_V2_SITE_KEY` на backend)

## Настройка модели (LLM_PROVIDER)

По умолчанию используется `stub` (детерминированная заглушка без API‑ключей).

Доступные провайдеры:
- `stub`
- `ollama` (через локальный Ollama)
- `openai_compatible` (для OpenAI‑совместимых API; сюда можно подключить GigaChat при наличии совместимого endpoint)
- `gigachat` (для GigaChat через OpenAI‑совместимый endpoint)

Переменные окружения:

- `LLM_PROVIDER`
- `OPENAI_COMPAT_BASE_URL`
- `OPENAI_COMPAT_API_KEY`
- `OPENAI_COMPAT_MODEL`
- `GIGACHAT_BASE_URL`
- `GIGACHAT_API_KEY`
- `GIGACHAT_AUTHORIZATION_KEY`
- `GIGACHAT_MODEL`
- `GIGACHAT_VERIFY_TLS` (по умолчанию `false`, отключает проверку SSL для self-signed цепочек)
- `GIGACHAT_MAX_TOKENS` (по умолчанию `1400`, увеличьте если ответ обрезается)
- `GIGACHAT_TIMEOUT_SECONDS` (по умолчанию `90`)
- `OLLAMA_BASE_URL`
- `CORS_ALLOW_ORIGINS`

Пример `.env` смотрите в `converter-agent/.env.example`.

