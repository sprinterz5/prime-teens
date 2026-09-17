# Восстановление из бэкапа

Бэкапы лежат в `/var/backups/primeteens/<дата>/`:

- `db.dump` — `pg_dump -Fc` дамп Postgres (кастомный формат, восстанавливается `pg_restore`)
- `storage.tar.gz` — содержимое `storage/` целиком (рисунки учеников в
  `storage/drawings/`, PDF-экспорты групп в `storage/archive/`, и всё, что
  появится там в будущем — бэкап архивирует каталог целиком, без списка)
- `bot-data.tar.gz` — содержимое `bot/data/`

Если настроен офсайт (`BACKUP_REMOTE`), там же лежит `<дата>.tar.age` — то же
самое, но упакованное в один архив и зашифрованное `age`. Расшифровка:

```bash
age -d -i /path/to/age-private-key.txt -o 2026-01-15.tar 2026-01-15.tar.age
tar -xf 2026-01-15.tar   # получится каталог 2026-01-15/ с теми же тремя файлами
```

## Восстановление Postgres (в свежую БД)

Не накатывай дамп поверх боевой базы — сначала подними отдельную БД,
проверь, что всё поднялось, и только потом переключай `DATABASE_URL`.

```bash
sudo -u postgres createdb primeteens_restore_test
sudo -u postgres pg_restore -d primeteens_restore_test /var/backups/primeteens/2026-01-15/db.dump

# проверка руками:
sudo -u postgres psql primeteens_restore_test -c '\dt'
sudo -u postgres psql primeteens_restore_test -c 'select count(*) from "Student";'
```

Если это настоящее аварийное восстановление (боевая БД потеряна), а не
проверка: разверни дамп в БД, на которую и так указывает `DATABASE_URL`
(создай её заново той же командой `createdb`, если её тоже нет), останови
`primeteens-web` и оба бота на время восстановления:

```bash
sudo systemctl stop primeteens-web primeteens-mentor primeteens-kids
sudo -u postgres createdb primeteens
sudo -u postgres pg_restore -d primeteens /var/backups/primeteens/2026-01-15/db.dump
sudo systemctl start primeteens-web primeteens-mentor primeteens-kids
```

Схему после restore руками не трогай — `pg_restore` восстанавливает и
структуру, и данные из дампа; `pnpm prisma migrate deploy` понадобится,
только если бэкап старше последних миграций в `prisma/migrations/`.

## Восстановление storage/ и bot/data

```bash
sudo systemctl stop primeteens-web   # чтобы не писать в storage/ во время распаковки
cd /opt/prime-teens
sudo tar -xzf /var/backups/primeteens/2026-01-15/storage.tar.gz
sudo tar -xzf /var/backups/primeteens/2026-01-15/bot-data.tar.gz -C bot
sudo chown -R primeteens:primeteens storage bot/data
sudo systemctl start primeteens-web
```

## Важно

Это описание процедуры, но реально отработанной (протестированной на живом
сервере) она станет только после того, как её один раз прогонят руками —
разверни дамп в `primeteens_restore_test`, как выше, хотя бы раз после
первого деплоя, и повторяй время от времени. Бэкап, который ни разу не
восстанавливали, нельзя считать бэкапом.
