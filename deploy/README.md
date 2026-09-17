# Деплой на VPS (Ubuntu 24.04)

Порядок действий с чистого сервера до рабочего сайта + ботов. Один VPS,
публичный IP, домена пока нет (см. [`HTTPS.md`](HTTPS.md) — короткий вывод:
для Telegram Mini App лучше всё-таки купить дешёвый домен).

Платформа (сайт с Workbook/Mentor view), Postgres и оба бота живут **вместе,
на одном сервере** — не сайт отдельно на Vercel, а всё вместе здесь. Почему:
SSE-стримы (`/api/workbook/<id>/stream`, `/api/mentor/groups/<id>/stream`) и
`LISTEN/NOTIFY` в Postgres требуют одного длинно живущего процесса рядом с
базой, а не serverless-функций; плюс персональные данные детей по закону РК
должны храниться на территории Казахстана. См. также правку в
`bot/README.md` — тот же вывод с точки зрения ботов.

## 1. Пользователь и базовые пакеты

```bash
sudo adduser --system --group --home /opt/prime-teens --shell /bin/bash primeteens
sudo apt update && sudo apt install -y curl git build-essential ufw nginx
```

## 2. Node.js 24 + pnpm

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs
corepack enable
corepack prepare pnpm@latest --activate
node -v   # ожидаем v24.x
pnpm -v
```

## 3. PostgreSQL 16 (локально, без внешнего доступа)

```bash
sudo apt install -y postgresql postgresql-contrib
```

Проверь, что слушает только `127.0.0.1` (по умолчанию на Ubuntu так и есть —
`listen_addresses = 'localhost'` в `/etc/postgresql/16/main/postgresql.conf`).
Postgres наружу светить не нужно — и веб-приложение, и оба бота обращаются к
нему как к `localhost`.

```bash
sudo -u postgres psql -c "CREATE USER primeteens WITH PASSWORD 'ЗАМЕНИ_НА_СЛУЧАЙНЫЙ_ПАРОЛЬ';"
sudo -u postgres psql -c "CREATE DATABASE primeteens OWNER primeteens;"
```

Пароль — не короткая фраза, а что-то вроде
`openssl rand -base64 24`.

## 4. Код на сервер

```bash
sudo git clone <URL-репозитория> /opt/prime-teens
sudo chown -R primeteens:primeteens /opt/prime-teens
```

## 5. `.env` (корень репозитория)

`.env` в git не попадает — создаётся на сервере руками (см. `.env.example`
для полного списка с комментариями). Обязательные переменные:

| Переменная | Значение |
|---|---|
| `DATABASE_URL` | `postgresql://primeteens:ПАРОЛЬ@localhost:5432/primeteens?schema=public` |
| `SESSION_SECRET` | `openssl rand -hex 32` |
| `TELEGRAM_MENTOR_BOT_TOKEN` | токен менторского бота от @BotFather |
| `TELEGRAM_KIDS_BOT_TOKEN` | токен детского бота от @BotFather |
| `NODE_ENV` | `production` |
| `DEV_LOGIN` | **отсутствует или `0`** — с `1` в проде включается обход авторизации |

```bash
sudo -u primeteens cp /opt/prime-teens/.env.example /opt/prime-teens/.env
sudo -u primeteens nano /opt/prime-teens/.env
```

## 6. Установка, миграции, сборка

```bash
cd /opt/prime-teens
sudo -u primeteens pnpm install --frozen-lockfile
sudo -u primeteens pnpm prisma migrate deploy
sudo -u primeteens pnpm build
```

## 7. Боты (Python)

Полная инструкция — `bot/README.md`, раздел «Перенос на сервер (Linux)»:
venv, `requirements.txt`, `bot/.env`, юнит-файлы из `bot/deploy/`. Коротко:

```bash
cd /opt/prime-teens/bot
sudo -u primeteens python3.14 -m venv .venv
sudo -u primeteens .venv/bin/pip install -r requirements.txt
sudo -u primeteens cp .env.example .env
sudo -u primeteens nano .env
```

## 8. nginx + HTTPS

Конфиг — `deploy/nginx/primeteens.conf` (проксирует на `127.0.0.1:3000`,
без буферизации на SSE-роутах, security-заголовки без `X-Frame-Options
DENY`/жёсткого `frame-ancestors`, чтобы не сломать открытие в Telegram
webview и собственный iframe `/workbook/frame`).

```bash
sudo mkdir -p /var/www/certbot
sudo cp deploy/nginx/primeteens.conf /etc/nginx/sites-available/primeteens.conf
sudo ln -s /etc/nginx/sites-available/primeteens.conf /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Дальше — сертификат. Подробный разбор вариантов (IP-сертификат Let's
Encrypt на 6 дней vs обычный домен) и точные команды — в
[`HTTPS.md`](HTTPS.md). Коротко: если есть возможность купить домен —
бери домен, `sudo certbot --nginx -d your-domain.kz` и живи спокойно с
автопродлением; если совсем без домена — вариант с IP-сертификатом
работает, но требует ручной wiring в nginx и надёжного `--deploy-hook`
каждые 6 дней, и не факт, что Telegram примет такой URL для Mini App в
проде.

После получения сертификата пропиши реальные пути в
`ssl_certificate`/`ssl_certificate_key` в
`/etc/nginx/sites-available/primeteens.conf` (плейсхолдеры там сейчас) и
`server_name`, если появился домен, затем `sudo nginx -t && sudo systemctl
reload nginx`.

## 9. systemd: веб-приложение

```bash
sudo cp deploy/systemd/primeteens-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now primeteens-web
```

Юниты ботов — из `bot/deploy/` (`primeteens-mentor.service`,
`primeteens-kids.service`), ставятся так же, см. `bot/README.md`.

Проверка:

```bash
curl -s http://127.0.0.1:3000/api/health
sudo systemctl status primeteens-web primeteens-mentor primeteens-kids
```

## 10. Файрвол

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Postgres (5432) наружу не открываем — он и так слушает только `127.0.0.1`.

## 11. Бэкапы

Скрипт и юниты — `deploy/backup/`. Дампит Postgres (`pg_dump -Fc`) и архивирует
`storage/` (рисунки + PDF-архивы групп) и `bot/data/` в
`/var/backups/primeteens/<дата>/`, хранит 7 ежедневных + 4 воскресных бэкапа.

```bash
sudo mkdir -p /var/backups/primeteens
sudo cp deploy/backup/backup.sh /opt/prime-teens/deploy/backup/backup.sh   # уже там после git clone
sudo chmod +x /opt/prime-teens/deploy/backup/backup.sh
sudo cp deploy/backup/primeteens-backup.service deploy/backup/primeteens-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now primeteens-backup.timer
```

Разово прогони руками, чтобы проверить, что всё пишется:

```bash
sudo systemctl start primeteens-backup.service
sudo journalctl -u primeteens-backup -n 50
```

Офсайт-копия (необязательно) — переменные `BACKUP_REMOTE`
(`user@host:/path`) и `BACKUP_AGE_RECIPIENT` (публичный ключ `age`) в
`/etc/primeteens/backup.env` (см. `EnvironmentFile=` в
`primeteens-backup.service`). Без них скрипт просто не пытается копировать
наружу — только локальный бэкап.

Процедура восстановления — `deploy/backup/restore.md`. **Прогони её один
раз руками** после первого деплоя, не откладывай на момент реальной аварии.

## 12. Ночная архивация (сжатие рисунков + PDF по группам)

`deploy/systemd/primeteens-archive.service` + `.timer` запускают `pnpm
archive:pending` в `/opt/prime-teens` от пользователя `primeteens` каждую
ночь в 04:30 по Алматы — то есть через час после бэкапа (03:30), чтобы
бэкап успевал забрать ещё несжатые рисунки до того, как job их тронет.
Скрипт (`scripts/archive-*`) сжимает рисунки в WebP и собирает PDF для
групп, которые бот автоматически закрыл после хакатона.

```bash
sudo cp deploy/systemd/primeteens-archive.service deploy/systemd/primeteens-archive.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now primeteens-archive.timer
```

Проверка разово вручную:

```bash
sudo systemctl start primeteens-archive.service
sudo journalctl -u primeteens-archive -n 50
```

Сбои этой джобы покрывает `monitor.sh` (пункт 13 ниже) — он проверяет
`systemctl is-failed primeteens-archive.service` и шлёт алерт не чаще раза
в 24 часа, по той же логике, что и для бэкапов, без самолечения (чинить
здесь нечего — просто вручную разобраться, что упало, и перезапустить
`sudo systemctl start primeteens-archive.service` после исправления).

## 13. Мониторинг

Скрипт `deploy/monitor/monitor.sh` раз в минуту проверяет `/api/health`,
статус трёх systemd-юнитов, место на диске, свежесть последнего бэкапа и
успешность последнего запуска ночной архивации (пункт 12) — политика
(тихое самолечение, алерт только на переходах состояния) описана в
комментарии в начале скрипта.

```bash
sudo mkdir -p /var/lib/primeteens-monitor
sudo cp deploy/monitor/monitor.sh /opt/prime-teens/deploy/monitor/monitor.sh   # уже там после git clone
sudo chmod +x /opt/prime-teens/deploy/monitor/monitor.sh
sudo cp deploy/monitor/primeteens-monitor.service deploy/monitor/primeteens-monitor.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now primeteens-monitor.timer
```

**Почему монитор работает от root**: ему нужно `systemctl restart` на трёх
юнитах для самолечения. Вместо узкого sudoers-файла (тоже вариант, но
больше движущихся частей ради скрипта, который и так делает только
read-only проверки плюс перезапуск трёх заранее известных юнитов) — проще
и не менее безопасно просто запускать его от root через systemd, как в
`primeteens-monitor.service`. Если хочешь именно sudoers — замени `User=root`
на обычного пользователя и добавь в `/etc/sudoers.d/primeteens-monitor`:

```
primeteens ALL=(root) NOPASSWD: /usr/bin/systemctl restart primeteens-web, /usr/bin/systemctl restart primeteens-mentor, /usr/bin/systemctl restart primeteens-kids
```

Telegram-алерты — заведи `/etc/primeteens/monitor.env`:

```bash
sudo mkdir -p /etc/primeteens
sudo tee /etc/primeteens/monitor.env >/dev/null <<'EOF'
MONITOR_BOT_TOKEN=токен_любого_бота_например_менторского
MONITOR_CHAT_ID=твой_telegram_chat_id
EOF
sudo chmod 600 /etc/primeteens/monitor.env
```

Можно переиспользовать токен менторского бота — отдельный "бот для
алертов" не обязателен. `MONITOR_CHAT_ID` — свой личный chat_id (напиши
боту что угодно, потом глянь в `getUpdates` или используй @userinfobot).
Без этого файла монитор просто пишет в журнал (`journalctl -u
primeteens-monitor`), ничего никуда не шлёт — тоже рабочий режим, просто
без Telegram-уведомлений.

**Важная оговорка**: монитор живёт на том же сервере, что и всё
остальное — если сервер целиком упал (питание, сеть, хостер), монитор
тоже не работает и никого не предупредит. Для этого стоит завести один
бесплатный внешний uptime-чекер (например UptimeRobot, Better Uptime,
healthchecks.io — любой), который дёргает `https://<ваш-адрес>/api/health`
снаружи. Эндпоинт не отдаёт персональных данных, так что светить его
наружу безопасно. В настройках такого чекера поставь уведомление только
"down after 5 min" — без "всё ок" писем, по той же логике, что и у
`monitor.sh`.

## 14. Обновление кода

```bash
cd /opt/prime-teens
sudo -u primeteens git pull
sudo -u primeteens pnpm install --frozen-lockfile
sudo -u primeteens pnpm prisma migrate deploy
sudo -u primeteens pnpm build
sudo systemctl restart primeteens-web

cd bot
sudo -u primeteens .venv/bin/pip install -r requirements.txt   # если requirements.txt менялся
sudo systemctl restart primeteens-mentor primeteens-kids
```

## 15. Telegram: адрес Mini App в кнопках ботов

Когда появился рабочий HTTPS-адрес (домен или, экспериментально,
IP-сертификат — см. `HTTPS.md`), пропиши его в @BotFather для каждого
бота:

- Менторский бот → `/setmenubutton` (или Bot Settings → Menu Button) →
  `https://<ваш-адрес>/mentor`
- Детский бот → `/setmenubutton` → `https://<ваш-адрес>/workbook`

Если где-то в сценариях бота используется login-виджет/`/setdomain` —
там тоже нужен именно домен (см. `HTTPS.md`, там же — почему голый IP тут
под вопросом).
