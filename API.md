# SyharikTS API

База: `http://localhost:8000` (по умолчанию). В production адрес ваш.

## Аутентификация

- `Authorization: Bearer <access_token>` для всех пользовательских endpoint’ов.
- `X-Internal-Token: <TELEGRAM_INTERNAL_TOKEN>` для внутренних Telegram endpoint’ов под `/telegram/*`.

## Форматы и ошибки

- JSON: выдача и запросы, кроме файловых эндпоинтов.
- `multipart/form-data`: `/generate`, `/infer-schema`, `/telegram/generate`.

Статусы: 400/401/403/404/409/415/429/500/503.

## Public utility

### `GET /health`

- Проверка статуса.
- Ответ: `{ "status": "ok", "database": { "state": "ok", "detail": null } }`.

## Auth

### `POST /auth/register`
- тело: `email`, `login`, `password`, `recaptcha_token`.
- отправляет проверочный email.

### `POST /auth/verify-email`
- тело: `email`, `code` (6 цифр).

### `POST /auth/resend-registration-code`
- тело: `email`.

### `POST /auth/login`
- тело: `login_or_email`, `password`.
- ответ: `{ access_token, refresh_token, token_type }`.

### `POST /auth/refresh`
- тело: `refresh_token`.

### `POST /auth/reset-request`
- тело: `login_or_email`.

### `POST /auth/reset-confirm`
- тело: `login_or_email`, `code`, `new_password`.

### `GET /auth/me`
- возвращает профиль текущего пользователя.

## Profile и генерируемые истории

### `PATCH /profile`
- тело: `login`|`new_password` + `current_password`.

### `GET /me/generations`
- список последних генераций пользователя.

### `GET /me/generations/{generation_id}`
- детали конкретной генерации, включая `generated_ts_code`.

### `GET /me/generations/{generation_id}/check-input`
- `input_base64` (если сохранено).

### `GET /me/token-usage`
- общая статистика токенов и последние запросы.

## Генерация

### `POST /generate`
- auth Bearer.
- `multipart/form-data`: `file`, `schema` (JSON string).
- ответ: `{ "code": "..." }`.
- серединные метрики генерации, кэш, fingerprint.

### `POST /infer-schema`
- auth Bearer.
- `multipart/form-data`: `file`.
- ответ: `{ "schema": "..json.." }`.

## Telegram web endpoints (пользователь)

### `POST /me/telegram/link-code`
- auth Bearer.
- вернет команду `/link XXXX`, срок жизни, bot_url.

### `GET /me/telegram/status`
- auth Bearer.
- возвращает привязку Telegram.

### `POST /me/telegram/unlink`
- auth Bearer.
- отвязка Telegram.

## Telegram internal API (bot -> backend)

Требует `X-Internal-Token`.

### `POST /telegram/consume-link`
- тело: `code`, `chat_id`, `username`, `first_name`.
- возвращает статус привязки.

### `GET /telegram/me?chat_id={chat_id}`
- возвращает профиль, последние генерации и token usage.

### `POST /telegram/generate`
- `multipart/form-data`: `chat_id`, `schema`, `file`.
- возвращает `code`, `cache_hit`, `main_file_name`.

## Статистика и observability

### `GET /stats/generations`
- auth Bearer.
- возвращает `{ "total_generations_all_time": … }`.

### `GET /observability/summary`
- auth Bearer.
- возвращает: langfuse, llm_provider, database_configured, cache stats, etc.

## Пример пользования

### Login

```bash
curl -X POST "http://localhost:8000/auth/login" -H "Content-Type: application/json" -d '{"login_or_email":"user@example.com","password":"StrongPassword123"}'
```

### Generation

```bash
curl -X POST "http://localhost:8000/generate" -H "Authorization: Bearer $TOKEN" -F "file=@example.csv" -F 'schema={"date":"2026-01-01","amount":0}'
```

### Infer schema

```bash
curl -X POST "http://localhost:8000/infer-schema" -H "Authorization: Bearer $TOKEN" -F "file=@example.csv"
```

### Telegram consume link

```bash
curl -X POST "http://localhost:8000/telegram/consume-link" -H "Content-Type: application/json" -H "X-Internal-Token: $TELEGRAM_INTERNAL_TOKEN" -d '{"code":"ABCD1234","chat_id":"123","username":"u","first_name":"Ivan"}'
```
