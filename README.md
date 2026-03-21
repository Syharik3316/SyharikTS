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

- Backend: `Python`, `FastAPI`, `LangChain`, опционально `PostgreSQL` через `SQLAlchemy` (async) + `asyncpg`
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

### `GET /health`

Проверка живости процесса и (если задан `DATABASE_URL`) доступности БД.

Ответ:

```json
{
  "status": "ok",
  "database": { "state": "skipped", "detail": null }
}
```

Поле `database.state`: `skipped` (URL не задан), `ok`, `error` (в `detail` — краткий текст ошибки). При ошибке подключения процесс всё равно стартует; статус смотрите в `/health`.

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
- `DATABASE_URL` (опционально) — строка для async-подключения к PostgreSQL, формат: `postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME` (спецсимволы в пароле — URL-encoding)
- `DATABASE_CONNECT_TIMEOUT` (опционально) — секунды на TCP-подключение к Postgres (asyncpg), по умолчанию `10`; уменьшает «подвисание» `/health`, если БД недоступна

Актуальный пример смотрите в `.env.example`.

## PostgreSQL с нуля (Ubuntu Server)

Ниже — установка **внешней** по отношению к `docker compose` этого репозитория базы на том же сервере или на отдельной машине. Production-хостинг предполагается на **Ubuntu Server**.

Чтобы создать БД `syharikts`, пользователя `syharikts_usr` и сразу получить в терминале готовые строки `DATABASE_URL`, на сервере после установки PostgreSQL выполните: `sudo bash scripts/init_syharikts_db.sh` (файл в каталоге [`scripts/`](scripts/)). Скрипт должен быть с переводами строк **LF** (Unix); если при запуске видно `bash\r` или ошибку у `set -o pipefail`, выполните на сервере: `sed -i 's/\r$//' scripts/init_syharikts_db.sh`, либо заново скопируйте файл из репозитория (в проекте для `*.sh` задано `eol=lf` в [`.gitattributes`](.gitattributes)).

### Установка и сервис

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
```

Конфигурация обычно в `/etc/postgresql/<версия>/main/postgresql.conf` и `pg_hba.conf`.

### Пользователь и база

```bash
sudo -u postgres psql
```

В консоли `psql`:

```sql
CREATE USER appuser WITH PASSWORD 'your-secure-password';
CREATE DATABASE appdb OWNER appuser;
GRANT ALL PRIVILEGES ON DATABASE appdb TO appuser;
\q
```

### Доступ с другой машины

Если приложение подключается **не с localhost**, в `postgresql.conf` задайте `listen_addresses` (например `'*'` или конкретный IP). В `pg_hba.conf` добавьте строку вида `host appdb appuser <подсеть_приложения>/24 scram-sha-256` (уточните метод под вашу версию PostgreSQL). Затем:

```bash
sudo systemctl restart postgresql
```

При необходимости откройте порт только для нужной подсети:

```bash
sudo ufw allow from <подсеть_приложения> to any port 5432 proto tcp
```

Избегайте открытия `5432` для всего интернета без крайней необходимости.

### Backend в Docker, PostgreSQL на том же Ubuntu

[`docker-compose.yml`](docker-compose.yml) использует **`network_mode: host`** — backend делит сеть с хостом, поэтому в `DATABASE_URL` указывайте **`127.0.0.1`**:

```
DATABASE_URL=postgresql+asyncpg://appuser:secret@127.0.0.1:5432/appdb
```

Nginx по-прежнему обращается к `127.0.0.1:8000`. Никаких iptables и шлюзов Docker.

### Проверка

Задайте `DATABASE_URL` и вызовите `GET /health` — при успехе будет `database.state`: `ok`.

### Ошибки подключения

С `network_mode: host` backend и PostgreSQL оба на хосте — `127.0.0.1:5432` должен быть доступен. Если `/health` возвращает `database.state: error`:
- **`Connection refused`** — проверьте `ss -tlnp | grep 5432` и `listen_addresses` в PostgreSQL.
- **`TimeoutError`** — маловероятно при host-режиме; проверьте, что `DATABASE_URL` указывает на `127.0.0.1`, а не на `172.x.x.x`.

### Разработка на Windows

При локальном запуске backend в Docker без `network_mode: host` используйте `host.docker.internal` в `DATABASE_URL` (Docker Desktop на Windows его поддерживает). Для production на Ubuntu используется host-режим.

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
- `GET /health` без `DATABASE_URL` (`database.state` = `skipped`)

## Важные замечания

- Для `doc` используется эвристический best-effort парсинг (без внешних системных утилит).
- Качество OCR зависит от качества изображения и установленного языка Tesseract (`OCR_LANG`).
- В production рекомендуется ограничивать `PARSE_MAX_TEXT_CHARS` и `PARSE_MAX_ROWS`.

