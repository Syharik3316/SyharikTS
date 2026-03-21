# Скрипты (Ubuntu / bash)

Файлы `*.sh` должны иметь окончания строк **только LF** (Unix). Если bash пишет `$'\r': command not found` или `set: pipefail: invalid option`, в файле попали символы **CRLF** (Windows).

## Один раз на сервере (если уже скопировали с CRLF)

```bash
sed -i 's/\r$//' scripts/*.sh
chmod +x scripts/*.sh   # по желанию
```

Или: `apt install dos2unix` и `dos2unix scripts/*.sh`.

## Чтобы не повторялось

- Клонировать/пуллить через Git: в проекте заданы [`.gitattributes`](../.gitattributes) (`*.sh text eol=lf`) и [`.editorconfig`](../.editorconfig).
- После обновления `.gitattributes` один раз в корне репозитория: `git add --renormalize .` и коммит — дальше Git будет выдавать `*.sh` с LF.
- На Windows в этом клоне можно задать `git config core.autocrlf false`, чтобы не подмешивался CR при коммитах.
- Не копировать скрипты через редактор/архиватор, который подменяет переводы строк; лучше `git pull` или `scp` из репозитория с нормализованными файлами.

## Миграции БД

```bash
export DATABASE_URL='postgresql+asyncpg://USER:PASS@127.0.0.1:5432/syharikts'
bash scripts/run_migrations.sh
```
