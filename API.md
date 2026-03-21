## Routes
`POST /generate` (+ `app/routers/generate.py`)
`POST /infer-schema` (+ `app/routers/infer_schema.py`)

## POST /generate

Описание:
- Вход:
  - `file` (UploadFile): CSV/XLS/XLSX/PDF/DOCX/PNG/JPG
  - `schema` (str): JSON-строка примера выходной структуры
- Ответ:
  - `GenerateResponse`:
    - `code`: TypeScript строка

Ошибки:
- 400: missing/invalid input, parse error, invalid schema
- 415: unsupported media type или невалидный файл
- 500: LLM generation error

### Пример curl

```bash
curl -X POST "http://localhost:8000/generate" \
  -F "file=@./example.csv" \
  -F 'schema={"dateCreate":"2026-01-01","product":"ABC"}'
```

или с экранированием в bash:

```bash
curl -X POST "http://localhost:8000/generate" \
  -F "file=@./example.csv" \
  -F "schema={\"dateCreate\":\"2026-01-01\",\"product\":\"ABC\"}"
```

---

## POST /infer-schema

Описание:
- Вход:
  - `file` (UploadFile)
- Ответ:
  - `InferSchemaResponse`:
    - `schema`: JSON в строке

Ошибки:
- 400: parse/missing file
- 415: unsupported media type

### Пример curl

```bash
curl -X POST "http://localhost:8000/infer-schema" \
  -F "file=@./example.csv"
```
---

## Профиль и история генераций

## PATCH /profile

Описание:
- Bearer: требуется
- Вход:
  - `login` (optional): строка
  - `current_password`: обязательная строка
  - `new_password` (optional): строка
- Ответ:
  - `UserPublic`: `id`, `email`, `login`, `is_email_verified`

Ошибки:
- 400: нечего обновлять
- 401: неверный `current_password` или нет Bearer
- 409: `login` уже занят

### Пример curl
```bash
curl -X PATCH "http://localhost:8000/profile" \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"login":"new_login","current_password":"oldpass","new_password":"newpass"}'
```

---

## GET /me/generations

Описание:
- Bearer: требуется
- Ответ:
  - массив `GenerationHistoryItem`:
    - `id`
    - `created_at`
    - `main_file_name`

---

## GET /me/generations/{id}

Описание:
- Bearer: требуется
- Ответ:
  - `GenerationHistoryDetail`:
    - `id`, `created_at`, `main_file_name`
    - `generated_ts_code`: строка с TS-кодом
