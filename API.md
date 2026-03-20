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
