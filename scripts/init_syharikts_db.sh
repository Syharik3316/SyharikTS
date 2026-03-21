#!/usr/bin/env bash
# Создаёт БД syharikts и пользователя syharikts_usr на локальном PostgreSQL (Ubuntu Server).
# Запуск: sudo bash scripts/init_syharikts_db.sh
# Пароль по умолчанию задан ниже; для production лучше: export SYHARIKTS_DB_PASSWORD='...' перед запуском.

set -euo pipefail

DB_NAME="syharikts"
DB_USER="syharikts_usr"
DB_PASSWORD="${SYHARIKTS_DB_PASSWORD:-mBn0fiwBSvfjo]qH}"

# Хост для печати примеров DATABASE_URL (сам скрипт подключается через peer local)
PRINT_HOST="${PRINT_HOST:-127.0.0.1}"
DOCKER_BRIDGE_HOST="${DOCKER_BRIDGE_HOST:-172.17.0.1}"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Запустите от root или через sudo: sudo bash $0" >&2
  exit 1
fi

sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
  ELSE
    ALTER ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
  END IF;
END
\$\$;

SELECT format('CREATE DATABASE %I OWNER %I', '${DB_NAME}', '${DB_USER}')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}')
\gexec

ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USER};
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL

# P=... должен быть перед python3, иначе bash передаёт его как аргумент интерпретатору.
PASS_ENC="$(P="${DB_PASSWORD}" python3 -c "import urllib.parse, os; print(urllib.parse.quote(os.environ['P'], safe=''))")"

echo ""
echo "========== SyharikTS PostgreSQL — готово =========="
echo "Имя БД:     ${DB_NAME}"
echo "Пользователь: ${DB_USER}"
echo "Пароль (как задан в скрипте / в SYHARIKTS_DB_PASSWORD): ${DB_PASSWORD}"
echo "Пароль в URL-кодировке (для DATABASE_URL): ${PASS_ENC}"
echo "Порт:       5432 (по умолчанию)"
echo ""
echo "Подставьте HOST: IP или DNS сервера PostgreSQL с точки зрения backend (контейнера)."
echo "Примеры HOST на Ubuntu:"
echo "  - backend не в Docker: 127.0.0.1"
echo "  - Postgres на хосте, backend в Docker: часто ${DOCKER_BRIDGE_HOST} или host.docker.internal (с extra_hosts в compose)"
echo ""
echo "Готовые строки DATABASE_URL (asyncpg):"
echo "DATABASE_URL=postgresql+asyncpg://${DB_USER}:${PASS_ENC}@${PRINT_HOST}:5432/${DB_NAME}"
echo "DATABASE_URL=postgresql+asyncpg://${DB_USER}:${PASS_ENC}@${DOCKER_BRIDGE_HOST}:5432/${DB_NAME}"
echo ""
echo "Проверка с сервера БД:"
echo "  sudo -u postgres psql -d ${DB_NAME} -c 'SELECT current_user, current_database();'"
echo "=================================================="
