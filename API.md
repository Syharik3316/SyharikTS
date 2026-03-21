# SyharikTS API

Актуальная спецификация backend API для веб-клиента и Telegram-бота.

Base URL (локально): `http://localhost:8000`

## Аутентификация

- **Bearer JWT**: для пользовательских endpoint’ов (`Authorization: Bearer <access_token>`).
- **Internal token**: для внутренних endpoint’ов Telegram (`X-Internal-Token: <TELEGRAM_INTERNAL_TOKEN>`).

## Форматы и ошибки

- JSON для большинства endpoint’ов.
- `multipart/form-data` для загрузки файлов (`/generate`, `/infer-schema`, `/telegram/generate`).
- Частые статусы:
  - `400` invalid input
  - `401` auth failed
  - `403` forbidden
  - `404` not found
  - `409` conflict
  - `415` unsupported media type
  - `429` rate limit/upstream limit
  - `500` internal error
  - `503` service misconfigured (например, БД/JWT/internal token)

## Public/Utility

### `GET /health`

Health-check приложения и БД.

Response:

```json
{
  "status": "ok",
  "database": {
    "state": "ok",
    "detail": null
  }
}
```

## Auth

### `POST /auth/register`

Регистрация пользователя и отправка email-кода.

Request:

```json
{
  "email": "user@example.com",
  "login": "user_login",
  "password": "StrongPassword123",
  "recaptcha_token": "..."
}
```

Response:

```json
{ "message": "Код подтверждения отправлен на email." }
```

### `POST /auth/verify-email`

Подтверждение email 6-значным кодом.

### `POST /auth/resend-registration-code`

Повторная отправка кода подтверждения.

### `POST /auth/login`

Логин по email или login + пароль.

Response:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer"
}
```

### `POST /auth/refresh`

Обновление пары токенов по refresh token.

### `POST /auth/reset-request`

Запрос кода сброса пароля.

### `POST /auth/reset-confirm`

Подтверждение кода сброса и установка нового пароля.

### `GET /auth/me` (Bearer)

Текущий пользователь.

Response (`UserPublic`):

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "login": "user_login",
  "is_email_verified": true,
  "telegram_chat_id": "123456789",
  "telegram_username": "my_username",
  "telegram_first_name": "Ivan",
  "telegram_linked_at": "2026-03-21T17:00:00+00:00"
}
```

## Profile & History

### `PATCH /profile` (Bearer)

Обновление логина/пароля.

Request:

```json
{
  "login": "new_login",
  "current_password": "old_password",
  "new_password": "new_password_or_null"
}
```

### `GET /me/generations` (Bearer)

История генераций пользователя.

Response: массив `GenerationHistoryItem`:

```json
[
  {
    "id": "uuid",
    "created_at": "2026-03-21T17:00:00+00:00",
    "main_file_name": "input.xlsx"
  }
]
```

### `GET /me/generations/{generation_id}` (Bearer)

Детали генерации + `generated_ts_code`.

### `GET /me/generations/{generation_id}/check-input` (Bearer)

Возвращает сохраненный base64 исходного файла (если файл был сохранен).

Response:

```json
{
  "input_base64": ".... or null"
}
```

### `GET /me/token-usage` (Bearer)

Токен-статистика пользователя.

Response (`TokenUsageSummaryResponse`):

```json
{
  "total_prompt_tokens": 1000,
  "total_completion_tokens": 500,
  "total_tokens": 1500,
  "requests_count": 12,
  "requests": [
    {
      "id": "uuid",
      "created_at": "2026-03-21T17:00:00+00:00",
      "main_file_name": "input.xlsx",
      "prompt_tokens": 100,
      "completion_tokens": 50,
      "total_tokens": 150
    }
  ]
}
```

## Generation

### `POST /generate` (Bearer)

Генерация TypeScript-кода.

Request (`multipart/form-data`):
- `file`: загруженный файл
- `schema`: JSON-строка примера структуры ответа

Response:

```json
{
  "code": "export default function ..."
}
```

Особенности:
- backend считает fingerprint входа (`file bytes + schema + file_kind`);
- считает fingerprint генератора (`provider + model + PROMPT_VERSION`);
- на cache hit возвращает ранее сгенерированный код и пишет новую audit-запись с токенами `0`.

### `POST /infer-schema` (Bearer)

Инференс JSON-примера по входному файлу.

Request: `multipart/form-data` с полем `file`.

Response:

```json
{
  "schema": "{\"date\":\"2026-01-01\",\"amount\":0}"
}
```

## Telegram Linkage (Web user endpoints)

### `POST /me/telegram/link-code` (Bearer)

Создать одноразовый код привязки Telegram.

Response:

```json
{
  "link_command": "/link ABCD1234",
  "code_expires_at": "2026-03-21T17:10:00+00:00",
  "bot_url": "https://t.me/syharikts_bot",
  "bot_username": "syharikts_bot"
}
```

### `GET /me/telegram/status` (Bearer)

Статус привязки Telegram.

Response:

```json
{
  "is_linked": true,
  "telegram_chat_id": "123456789",
  "telegram_username": "my_username",
  "telegram_first_name": "Ivan",
  "telegram_linked_at": "2026-03-21T17:05:00+00:00"
}
```

### `POST /me/telegram/unlink` (Bearer)

Отвязка Telegram от аккаунта.

Response:

```json
{ "message": "Telegram account unlinked" }
```

## Telegram Internal API (bot -> backend)

Требуют заголовок:

```http
X-Internal-Token: <TELEGRAM_INTERNAL_TOKEN>
```

### `POST /telegram/consume-link`

Привязка Telegram по коду `/link`.

Request:

```json
{
  "code": "ABCD1234",
  "chat_id": "123456789",
  "username": "my_username",
  "first_name": "Ivan"
}
```

Response: `TelegramStatusResponse` (`is_linked=true` и Telegram поля).

### `GET /telegram/me?chat_id=<chat_id>`

Профиль для Telegram-бота.

Response (`BotProfileResponse`):

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "login": "user_login",
  "telegram_username": "my_username",
  "recent_generations": [
    {
      "id": "uuid",
      "created_at": "2026-03-21T17:00:00+00:00",
      "main_file_name": "input.xlsx"
    }
  ],
  "token_usage": {
    "total_prompt_tokens": 1000,
    "total_completion_tokens": 500,
    "total_tokens": 1500,
    "requests_count": 12,
    "requests": []
  }
}
```

### `POST /telegram/generate`

Генерация из Telegram (та же логика кэша и учета токенов, что в web).

Request (`multipart/form-data`):
- `chat_id` (text)
- `schema` (text, JSON string)
- `file` (binary)

Response:

```json
{
  "code": "export default function ...",
  "cache_hit": false,
  "main_file_name": "input.xlsx"
}
```

## Observability & Stats

### `GET /stats/generations` (Bearer)

Общее число генераций.

### `GET /observability/summary` (Bearer)

Техническая сводка (provider, cache metrics, Langfuse state и др.).

## Примеры curl

### Логин

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"login_or_email\":\"user@example.com\",\"password\":\"StrongPassword123\"}"
```

### Генерация (web)

```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -F "file=@./example.csv" \
  -F "schema={\"date\":\"2026-01-01\",\"amount\":0}"
```

### Инференс схемы

```bash
curl -X POST "http://localhost:8000/infer-schema" \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -F "file=@./example.csv"
```

### Внутренний consume-link

```bash
curl -X POST "http://localhost:8000/telegram/consume-link" \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: INTERNAL_TOKEN" \
  -d "{\"code\":\"ABCD1234\",\"chat_id\":\"123456789\",\"username\":\"my_username\",\"first_name\":\"Ivan\"}"
```
