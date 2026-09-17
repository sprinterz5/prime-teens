# HTTPS без домена: что реально сейчас (сентябрь 2026)

Коротко: сертификаты Let's Encrypt на голый IP уже существуют, но живут
6 дней и требуют ручной донастройки nginx на каждое обновление. Для
Telegram Mini App это, скорее всего, вообще не сработает — production
принимает только настоящий домен. **Рекомендация: купить дешёвый домен**
(вариант Б ниже), вариант с IP — только если домен совсем не вариант.

## Вариант А: сертификат Let's Encrypt прямо на IP-адрес

**Подтверждено** (первоисточник — блог Let's Encrypt):

- 15 января 2026 Let's Encrypt объявил, что IP-сертификаты (IPv4 и IPv6)
  доступны всем ("Generally Available"), без домена вообще —
  [letsencrypt.org/2026/01/15/6day-and-ip-general-availability](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability)
- Такие сертификаты обязательно короткоживущие: срок жизни **160 часов
  (~6.7 суток)**. Это не настройка, а требование CA/Browser Forum для
  IP-сертификатов — обычный 90-дневный профиль для IP недоступен.
- 11 марта 2026 вышла поддержка в Certbot 5.4+ —
  [letsencrypt.org/2026/03/11/shorter-certs-certbot](https://letsencrypt.org/2026/03/11/shorter-certs-certbot),
  подтверждено также EFF —
  [eff.org/deeplinks/2026/03/certbot-and-lets-encrypt-now-support-ip-address-certificates](https://www.eff.org/deeplinks/2026/03/certbot-and-lets-encrypt-now-support-ip-address-certificates)

Команда получения (webroot, есть у нас в `deploy/nginx/primeteens.conf` —
location `/.well-known/acme-challenge/`):

```bash
sudo certbot certonly \
  --preferred-profile shortlived \
  --webroot --webroot-path /var/www/certbot \
  --ip-address <ваш публичный IP>
```

**Важная оговорка, тоже подтверждена официальной документацией Certbot**:
certbot умеет только *получить* IP-сертификат, но не умеет сам вписать его
в nginx (`--nginx` плагин с IP не работает) — путь к файлам придётся
прописать в конфиге руками (уже сделано, как placeholder, в
`deploy/nginx/primeteens.conf`), а автопродление настраивать через
`--deploy-hook`, который перезагружает nginx:

```bash
sudo certbot renew --deploy-hook "systemctl reload nginx"
```

Из-за 6-дневного срока жизни `certbot renew` (обычно раз в сутки по таймеру,
который сам ставит пакет certbot) должен отрабатывать без сбоев постоянно —
пропущенное продление на пару дней означает страницу с ошибкой сертификата
у всех посетителей.

### А как же Telegram — примет ли он https://IP?

**Не подтверждено однозначно, но признаков "да" нет, признаков "скорее нет"
достаточно, чтобы не полагаться на это в проде:**

- Официальная документация Mini Apps
  ([core.telegram.org/bots/webapps](https://core.telegram.org/bots/webapps))
  не формулирует явно "URL должен быть доменом, не IP" — но и не
  подтверждает обратное.
- Практический опыт разработчиков (форумные и community-ответы, не
  первоисточник Telegram) говорит: Telegram принимает только HTTPS-ссылки
  с валидным сертификатом, и **использовать голый IP разрешено только в
  тестовом окружении** (`test` DC Telegram), не в основном/боевом. Локальный
  Bot API сервер тоже допускает IP, но это отдельный self-hosted режим, не
  наш случай.
- Настройка `/setdomain` у @BotFather (нужна для login-виджета и части
  Mini-App сценариев) явно просит именно "domain name", что тоже намекает —
  инфраструктура Telegram заточена под домены, а не IP-литералы.

Итог: попробовать можно (сертификат для этого получить реально), но
рассчитывать на это в проде рискованно вдвойне — и потому, что неясно,
примет ли Telegram сам URL, и потому, что каждые 6 дней нужна безотказная
автоматика продления+релоада nginx, иначе сайт (и Mini App) на несколько
часов/дней недоступны.

## Вариант Б (рекомендуется): дешёвый домен

Если варианта с IP хватит только "на посмотреть", для реальной работы
Mini App нужен домен — тогда обычный сертификат Let's Encrypt (профиль по
умолчанию, 90 дней, `certbot --nginx`, полностью автоматическое продление,
никаких плясок с deploy-hook) работает так, как все привыкли, и Telegram
точно его принимает.

Варианты домена:

- **`.kz`** — регистратор верхнего уровня nic.kz
  ([nic.kz](https://www.nic.kz/)), резидентство не требуется, регистрация
  занимает около 3 рабочих дней. У `.kz` есть техническое требование —
  NS-записи должны отвечать с разных подсетей на момент регистрации; это
  обычно закрывается DNS-хостингом регистратора/реселлера "из коробки", но
  стоит уточнить у конкретного реселлера перед покупкой. Актуальную цену
  смотри на nic.kz или у реселлера (uneon.kz, hoster.kz и т.п.) — на момент
  подготовки этого документа точная цена не проверялась, не полагайся на
  цифру из памяти.
- **Любой недорогой `.com`/`.online`/`.site` и т.п.** через обычного
  международного регистратора (например Namecheap, Cloudflare Registrar) —
  проще и быстрее `.kz` (без требования к NS на разных подсетях), обычно
  дешевле в первый год. Из Казахстана оплата иностранной картой/через
  посредника — уточни у регистратора.

После покупки: направь A-запись (и AAAA, если есть IPv6) домена на IP
сервера, поставь `server_name` в `deploy/nginx/primeteens.conf` (вместо
`_`), получи обычный сертификат:

```bash
sudo certbot --nginx -d your-domain.kz
```

Certbot сам впишет пути в конфиг nginx и поставит таймер/systemd-unit на
автопродление — руками ничего донастраивать не нужно, в отличие от
IP-варианта.

## Источники

- [Let's Encrypt: 6-day and IP Address Certificates are Generally Available](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability)
- [Let's Encrypt: Six-Day and IP Address Certificates Available in Certbot](https://letsencrypt.org/2026/03/11/shorter-certs-certbot)
- [EFF: Certbot and Let's Encrypt Now Support IP Address Certificates](https://www.eff.org/deeplinks/2026/03/certbot-and-lets-encrypt-now-support-ip-address-certificates)
- [core.telegram.org/bots/webapps — Telegram Mini Apps docs](https://core.telegram.org/bots/webapps)
- [nic.kz — реестр домена .kz](https://www.nic.kz/)
