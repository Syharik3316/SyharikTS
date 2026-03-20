# SyharikTS

Веб‑сервис генерации TypeScript‑кода функции по загруженному файлу и JSON‑примеру структуры выходных данных. Проект создан командой 42x САУ "Хакатон Весна 2026" партнёр Сбербанк.

## Что умеет

- Загружает файл, парсит данные/текст и формирует `extracted_input_json`.
- Генерирует TypeScript-код через LLM (`/generate`).
- Строит пример схемы по файлу (`/infer-schema`).
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

## API

### `POST /generate`

`multipart/form-data`:

- `file` - входной файл одного из поддерживаемых форматов
- `schema` - JSON-строка с примером выходного объекта

Ответ:

```json
{ "code": "export default function ... " }
```

Пример:

```bash
curl -X POST "http://localhost:8000/generate" ^
  -F "file=@./example.csv" ^
  -F "schema={\"dateCreate\":\"2026-01-01\",\"dateLastUpdate\":\"2026-01-02\",\"product\":\"ABC\"}"
```

### `POST /infer-schema`

`multipart/form-data`:

- `file` - входной файл

Ответ:

```json
{ "schema": "{\"field\":\"example\"}" }
```

## Парсинг и OCR

- Для `txt/md/xml/fb2` используется извлечение текста с декодированием (`utf-8-sig`, `utf-8`, `cp1251`, fallback).
- Для `rtf` используется `striprtf`.
- Для `odt` используется `odfpy`.
- Для `epub` используется `ebooklib` + `BeautifulSoup`.
- Для `doc` используется best-effort извлечение текста из бинарного контента.
- Для изображений (`png/jpg/tiff`) используется `pytesseract` с предобработкой (`grayscale + autocontrast`) и fallback по `PSM`.

Если OCR/декодирование не смогли извлечь текст, backend возвращает контролируемую ошибку с кодом.

## Переменные окружения

### LLM

- `LLM_PROVIDER` (`stub`, `ollama`, `openai_compatible`, `gigachat`)
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
- `OLLAMA_BASE_URL`

### Парсер

- `PARSE_MAX_ROWS`
- `PARSE_MAX_TEXT_CHARS`
- `OCR_LANG` (например `eng+rus`)
- `OCR_PSM` (например `6`)
- `OCR_FALLBACK_PSM` (например `11`)

### Прочее

- `CORS_ALLOW_ORIGINS`
- `VITE_API_BASE_URL` (для frontend)

Актуальный пример смотрите в `.env.example`.

## Тесты

Backend-тесты:

```bash
cd backend
python -m unittest discover -s tests -v
```

Покрыты базовые сценарии:

- детекция форматов
- парсинг `txt/md/xml/rtf`
- контролируемые ошибки unsupported/OCR

## Важные замечания

- Для `doc` используется эвристический best-effort парсинг (без внешних системных утилит).
- Качество OCR зависит от качества изображения и установленного языка Tesseract (`OCR_LANG`).
- В production рекомендуется ограничивать `PARSE_MAX_TEXT_CHARS` и `PARSE_MAX_ROWS`.

