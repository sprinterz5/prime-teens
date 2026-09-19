"""
Сборка ВЕБ-версии рабочей тетради из тех же parts/*.html + theme.css.
Отличия от build.py (печатной версии):
  - шрифты подключаются с Google Fonts, а не вшиваются base64 (файл ~200 КБ вместо 6 МБ)
  - поля для письма превращаются в <input>/<textarea>
  - чекбоксы становятся настоящими
  - области для рисования получают <canvas>
  - добавлена навигация, масштабирование под экран и автосохранение

Стабильные ID полей
--------------------
Раньше ключ каждого поля (data-f) собирался по ПОРЯДКУ на странице во время
сборки (p{страница}f{номер}). Это ломалось при любой правке: добавил поле
выше — все ключи ниже съехали, и сохранённые ответы приклеились не к тем
вопросам.

Теперь у каждого поля есть явный, человекочитаемый id, прописанный прямо
в исходнике (parts/*.html):
  - {{L n|id=база}}, {{LS n|id=база}}, {{LD n|id=база}} — n строк письма,
    id получаются как "база-1".."база-n" (или просто "база", если n == 1)
  - {{K подпись|id=id}} — одно поле с моноширинной подписью слева
  - <div class="ck" data-id="id">...</div> — чекбокс
  - <td data-id="id"></td> — пустая ячейка таблицы
  - <div class="wbox dot ..." data-id="id">...</div> — область для рисования

Сборка ПАДАЕТ с понятной ошибкой, если у поля нет id или id повторяется
где-то ещё в тетради — так проще заметить опечатку, чем потом гадать,
почему у два разных задания делят один ответ.

На выходе, помимо ../index.html, пишется ../dist/manifest.json — список
всех полей в порядке документа (id, страница, день курса, тип, подпись,
раздел) с версией-хэшем. Он нужен бэкенду, который будет хранить ответы
в Postgres по id поля вместо позиционного ключа.
"""
import re, json, glob, os, hashlib

CSS = open('theme.css', encoding='utf-8').read()
B = json.load(open('assets/b64.json'))
LOGO = f"data:image/png;base64,{B['logo_web']}"
ANCHORS = {}


class BuildError(Exception):
    """Ошибка сборки: отсутствующий/повторяющийся/некорректный id поля."""


FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Unbounded:wght@400;700;800&'
    'family=Inter:wght@400;500;600;700&'
    'family=Source+Serif+4:ital,wght@0,400;0,600;1,400&'
    'family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">'
)

# ─────────────────────────────────────────── реестр id полей (для манифеста)
ID_FORMAT = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
SEEN_IDS = {}          # id -> номер страницы, где он впервые встретился
MANIFEST_FIELDS = []    # список полей в порядке документа

TAG_RE = re.compile(r'<[^>]+>')
LABEL_RE = re.compile(r'<div class="label">(.*?)</div>', re.S)
TT_RE = re.compile(r'<span class="tt">(.*?)</span>', re.S)
SEC_RE = re.compile(r'<div class="sec">(.*?)</div>', re.S)


def strip_tags(s):
    return re.sub(r'\s+', ' ', TAG_RE.sub('', s)).strip()


def context_before(s, pos):
    """Ближайшая предшествующая подпись (.label) и заголовок задания
    (.tt из .task, либо .sec) — для label/section в манифесте.

    Если найденный .label старше (стоит раньше), чем заголовок задания —
    он относится к прошлому блоку (например, к плашке дня сверху страницы),
    а не к текущему полю. В этом случае используем сам заголовок задания
    как label — это ближе к «подписи к полю», чем случайно зацепленный
    чужой .label."""
    label, label_pos = None, -1
    for m in LABEL_RE.finditer(s):
        if m.start() >= pos:
            break
        label, label_pos = strip_tags(m.group(1)), m.start()
    section, section_pos = None, -1
    for rx in (TT_RE, SEC_RE):
        for m in rx.finditer(s):
            if m.start() >= pos:
                break
            if m.start() > section_pos:
                section_pos = m.start()
                section = strip_tags(m.group(1))
    if label_pos < section_pos:
        label = section
    return label, section


def validate_id(fid, page_no, what):
    if not fid:
        raise BuildError(f"страница {page_no}: у {what} нет id (используй |id=... или data-id=\"...\")")
    if not ID_FORMAT.fullmatch(fid):
        raise BuildError(
            f"страница {page_no}: id '{fid}' ({what}) должен быть ascii kebab-case "
            f"(латиница, цифры, дефис, без дефиса в начале/конце)"
        )


def register(fid, page_no, day, ftype, label, section):
    if fid in SEEN_IDS:
        raise BuildError(
            f"страница {page_no}: id '{fid}' уже используется на странице {SEEN_IDS[fid]} "
            f"— id должен быть уникален по всей тетради"
        )
    SEEN_IDS[fid] = page_no
    MANIFEST_FIELDS.append({
        'id': fid, 'page': page_no, 'day': day,
        'type': ftype, 'label': label, 'section': section,
    })


def require_data_id(attrs, page_no, what):
    m = re.search(r'data-id="([^"]*)"', attrs or '')
    fid = m.group(1) if m else None
    validate_id(fid, page_no, what)
    return fid


def strip_data_id(attrs):
    return re.sub(r'\s*data-id="[^"]*"', '', attrs or '')


# ─────────────────────────────────────────── извлечение полей в порядке документа
def extract_manifest(raw, page_no, day):
    """Сканирует ИСХОДНОЕ (домакросное) содержимое страницы, находит все
    поля в порядке появления в документе, проверяет id и складывает
    записи в MANIFEST_FIELDS. Бросает BuildError на первой проблеме."""
    found = []
    for m in re.finditer(r'\{\{(L|LS|LD)\s+(\d+)(?:\|id=([^|}]*))?(\|ta)?\}\}', raw):
        found.append((m.start(), 'L', m))
    for m in re.finditer(r'\{\{K\s+(.*?)(?:\|id=([^}]*))?\}\}', raw):
        found.append((m.start(), 'K', m))
    for m in re.finditer(r'<div class="ck"([^>]*)>(.*?)</div>', raw, re.S):
        found.append((m.start(), 'CK', m))
    for m in re.finditer(r'<td([^>]*)>\s*</td>', raw):
        found.append((m.start(), 'TD', m))
    for m in re.finditer(r'<div class="(wbox dot[^"]*)"([^>]*)>(.*?)</div>\s*(?=<|$)', raw, re.S):
        found.append((m.start(), 'WBOX', m))
    found.sort(key=lambda t: t[0])

    for pos, kind, m in found:
        label, section = context_before(raw, pos)
        if kind == 'L':
            n, fid, ta = int(m.group(2)), m.group(3), m.group(4)
            validate_id(fid, page_no, f'{{{{{m.group(1)} {n}}}}}')
            if ta and n >= 2:
                # Группа строк — один связный ответ (не список отдельных
                # пунктов): в вебе это один растущий textarea на весь fid,
                # без суффиксов -1..-n. См. |ta в macros().
                register(fid, page_no, day, 'textarea', label, section)
            else:
                for i in range(1, n + 1):
                    sub_id = fid if n == 1 else f'{fid}-{i}'
                    register(sub_id, page_no, day, 'text', label, section)
        elif kind == 'K':
            text, fid = m.group(1), m.group(2)
            validate_id(fid, page_no, f'{{{{K {text}}}}}')
            register(fid, page_no, day, 'text', text.strip(), section)
        elif kind == 'CK':
            attrs, inner = m.group(1), m.group(2)
            fid = require_data_id(attrs, page_no, 'чекбокса (div.ck)')
            register(fid, page_no, day, 'checkbox', strip_tags(inner), section)
        elif kind == 'TD':
            attrs = m.group(1) or ''
            fid = require_data_id(attrs, page_no, 'пустой ячейки таблицы (td)')
            register(fid, page_no, day, 'text', label, section)
        elif kind == 'WBOX':
            attrs = m.group(2)
            fid = require_data_id(attrs, page_no, 'области для рисования (wbox dot)')
            register(fid, page_no, day, 'canvas', label, section)


# ─────────────────────────────────────────── макросы (как в печатной версии)
def macros(s, page_no):
    def rep(m):
        kind, n, fid, ta = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        validate_id(fid, page_no, f'{{{{{kind} {n}}}}}')
        if ta and n >= 2:
            cls = {'L': 'wlta', 'LS': 'wlta s', 'LD': 'wlta d'}[kind]
            return f'<div class="{cls}" data-id="{fid}" data-lines="{n}"></div>'
        cls = {'L': 'wl', 'LS': 'wl s', 'LD': 'wl d'}[kind]
        parts = []
        for i in range(1, n + 1):
            sub_id = fid if n == 1 else f'{fid}-{i}'
            parts.append(f'<div class="{cls}" data-id="{sub_id}"></div>')
        return ''.join(parts)
    s = re.sub(r'\{\{(L|LS|LD)\s+(\d+)(?:\|id=([^|}]*))?(\|ta)?\}\}', rep, s)
    s = re.sub(r'\{\{K\s+(.*?)(?:\|id=([^}]*))?\}\}',
               lambda m: f'<div class="wlbl" data-id="{m.group(2)}"><span class="k">{m.group(1)}</span></div>', s)
    return s.replace('{{LOGO}}', LOGO)


# ─────────────────────────────────────────── превращение в интерактив
def interactive(html, page_no):
    """Заменяет статичные поля на рабочие элементы формы. Id уже
    проверены в extract_manifest() — здесь просто переносим их в data-f."""

    # группы строк для одного связного ответа -> один растущий textarea
    def wlta_rep(m):
        cls, fid, n = m.group(1), m.group(2), int(m.group(3))
        line_mm = 7.5 if cls.endswith(' s') else 9
        min_h = round(n * line_mm, 1)
        return (f'<textarea class="{cls}" data-f="{fid}" data-lines="{n}" '
                f'rows="{n}" style="min-height:{min_h}mm"></textarea>')
    html = re.sub(r'<div class="(wlta(?:\s+[sd])?)" data-id="([^"]+)" data-lines="(\d+)"></div>',
                  wlta_rep, html)

    # линейки для письма -> текстовые поля
    def wl_rep(m):
        cls, fid = m.group(1), m.group(2)
        return f'<input class="{cls}" type="text" data-f="{fid}" autocomplete="off">'
    html = re.sub(r'<div class="(wl(?:\s+[sd])?)" data-id="([^"]+)"></div>', wl_rep, html)

    # поле с моноширинной подписью слева
    def wlbl_rep(m):
        fid, label = m.group(1), m.group(2)
        return (f'<div class="wlbl"><span class="k">{label}</span>'
                f'<input class="wlbl-in" type="text" data-f="{fid}" autocomplete="off"></div>')
    html = re.sub(r'<div class="wlbl" data-id="([^"]+)"><span class="k">(.*?)</span></div>', wlbl_rep, html)

    # чекбоксы
    def ck_rep(m):
        attrs, inner = m.group(1), m.group(2)
        fid = require_data_id(attrs, page_no, 'чекбокса (div.ck)')
        attrs_clean = strip_data_id(attrs)
        return (f'<label class="ck"{attrs_clean}><input type="checkbox" data-f="{fid}">'
                f'<span class="ck-box"></span>{inner}</label>')
    html = re.sub(r'<div class="ck"(.*?)>(.*?)</div>', ck_rep, html, flags=re.S)

    # пустые ячейки таблиц -> поля ввода
    def td_rep(m):
        attrs = m.group(1) or ''
        fid = require_data_id(attrs, page_no, 'пустой ячейки таблицы (td)')
        attrs_clean = strip_data_id(attrs)
        return f'<td{attrs_clean}><input class="td-in" type="text" data-f="{fid}" autocomplete="off"></td>'
    html = re.sub(r'<td([^>]*)>\s*</td>', td_rep, html)

    # области для рисования -> холст (любые классы, с содержимым и без)
    CANVAS_TOOLS = (
        '<div class="canvas-tools">'
        '<button class="ctool" type="button" data-act="thin" title="Тонкая линия">•</button>'
        '<button class="ctool" type="button" data-act="medium" title="Средняя линия">●</button>'
        '<button class="ctool" type="button" data-act="thick" title="Толстая линия">⬤</button>'
        '<button class="ctool" type="button" data-act="eraser" title="Ластик">🩹</button>'
        '<button class="ctool" type="button" data-act="undo" title="Отменить штрих">↶</button>'
        '<button class="ctool" type="button" data-act="clear" title="Стереть всё">✕</button>'
        '</div>'
    )

    def canvas_rep(m):
        cls, attrs, inner = m.group(1), m.group(2), m.group(3)
        fid = require_data_id(attrs, page_no, 'области для рисования (wbox dot)')
        attrs_clean = strip_data_id(attrs)
        return (f'<div class="{cls} canvas-wrap"{attrs_clean}>'
                f'<canvas data-f="{fid}"></canvas>'
                f'<div class="canvas-over">{inner}</div>'
                f'{CANVAS_TOOLS}</div>')
    html = re.sub(r'<div class="(wbox dot[^"]*)"([^>]*)>(.*?)</div>\s*(?=<|$)',
                  canvas_rep, html, flags=re.S)

    return html


# ─────────────────────────────────────────── день курса по странице
DAY_HR_RE = re.compile(r'ДЕНЬ\s+(\d+)')
ANCHOR_DAY_RE = re.compile(r'^d(\d+)$')


# ─────────────────────────────────────────── сборка страниц
def build_pages():
    files = sorted(glob.glob('parts/*.html'))
    raw = '\n'.join(open(f, encoding='utf-8').read() for f in files)
    chunks = re.split(r'<!--PAGE(.*?)-->', raw)[1:]
    pages, nav, n = [], [], 0
    total = len(chunks) // 2
    current_day = None
    for i in range(0, len(chunks), 2):
        attrs, content = chunks[i], chunks[i + 1]
        get = lambda k: (re.search(k + r'="(.*?)"', attrs).group(1)
                         if re.search(k + r'="(.*?)"', attrs) else '')
        cls, hl, hr, fl, anchor = get('class'), get('hl'), get('hr'), get('fl'), get('anchor')
        n += 1

        m = ANCHOR_DAY_RE.match(anchor) if anchor else None
        if m:
            current_day = int(m.group(1))
        m = DAY_HR_RE.search(hr)
        if m:
            current_day = int(m.group(1))
        is_generic = ('cover' in cls.split()) or (hl == 'ЗАМЕТКИ')
        day = None if is_generic else current_day

        if anchor:
            ANCHORS[anchor] = f'{n:02d}'
            nav.append((n, hr or hl or anchor))

        extract_manifest(content, n, day)

        head = f'<div class="hd"><span>{hl}</span><span class="r">{hr}</span></div>' if hl or hr else ''
        foot = (f'<div class="ft"><span>{fl or "PRIMETEENS · РАБОЧАЯ ТЕТРАДЬ"}</span>'
                f'<span>{n:02d} / {total:02d}</span></div>') if 'nofoot' not in cls else ''
        body = interactive(macros(content, n), n)
        # На узких экранах таблицы не сжимаются в колонку — им нужна
        # собственная горизонтальная прокрутка (см. .tbl-scroll в WEB_CSS).
        body = re.sub(r'(<table\b[^>]*>.*?</table>)', r'<div class="tbl-scroll">\1</div>', body, flags=re.S)
        day_attr = f' data-day="{day}"' if day is not None else ''
        pages.append(
            f'<section class="page {cls}" id="page-{n}" data-page="{n}"{day_attr}>'
            f'{head}<div class="body">{body}</div>{foot}</section>'
        )
    return '\n'.join(pages), n, nav


WEB_CSS = """
/* ============ ВЕБ-СЛОЙ. Печатный theme.css не тронут ============ */
body{ margin:0; background:#E8EDF2; font-family:'Inter',sans-serif; }

/* панель навигации */
.topbar{ position:sticky; top:0; z-index:50; background:#12324F; color:#fff;
  display:flex; align-items:center; gap:14px; padding:10px 16px; flex-wrap:wrap;
  box-shadow:0 2px 10px rgba(0,0,0,.18); }
.topbar .brand{ font-family:'Unbounded',sans-serif; font-weight:700; font-size:15px; letter-spacing:-.01em; }
.topbar .spacer{ flex:1 1 auto; }
.topbar button, .topbar select{ font-family:'Inter',sans-serif; font-size:13px; border:0;
  border-radius:7px; padding:7px 12px; cursor:pointer; background:#24557E; }
.topbar button{ background:#24557E; color:#fff; }
.topbar button:hover{ background:#2E6796; }
.topbar select{ background:#fff; color:#12324F; font-weight:600; }
.topbar .counter{ font-size:13px; opacity:.75; font-variant-numeric:tabular-nums; }
.topbar .saved{ font-size:12px; opacity:0; transition:opacity .25s; }
.topbar .saved.on{ opacity:.8; }

/* сцена со страницами */
.stage{ padding:26px 10px 60px; display:flex; flex-direction:column; align-items:center; gap:22px; }
.page{ box-shadow:0 4px 22px rgba(16,40,64,.16); }

/* поля ввода поверх исходных стилей */
input.wl, input.wl.s, input.wl.d{ width:100%; display:block; background:transparent;
  border:0; border-bottom:.9pt solid var(--line-s); border-radius:0; padding:0 1mm 1mm;
  font-family:'Inter',sans-serif; font-size:9.6pt; color:#123; outline:none; }
input.wl{ height:9mm; } input.wl.s{ height:7.5mm; } input.wl.d{ border-bottom-style:dashed; }
input.wl:focus, input.wlbl-in:focus, input.td-in:focus{ background:#FFF8E8; }
/* width:0 + min-width:0: without them an <input> keeps its intrinsic ~20ch width,
   which widens narrow grid columns (e.g. the cover's "Моя команда") past the page edge */
.wlbl{ gap:2mm; } .wlbl-in{ flex:1 1 auto; width:0; min-width:0; background:transparent; border:0; outline:none;
  font-family:'Inter',sans-serif; font-size:9.6pt; color:#123; padding-bottom:1mm; }
input.td-in{ width:100%; background:transparent; border:0; outline:none; min-height:8mm;
  font-family:'Inter',sans-serif; font-size:9.4pt; color:#123; }

/* чекбоксы */
label.ck{ cursor:pointer; }
label.ck input[type=checkbox]{ position:absolute; opacity:0; width:0; height:0; }
label.ck::before{ content:none; }
.ck-box{ flex:none; width:3.8mm; height:3.8mm; border:1.1pt solid var(--blue);
  border-radius:.6mm; margin-top:.6mm; display:inline-block; position:relative; }
label.ck input:checked + .ck-box{ background:var(--blue); }
label.ck input:checked + .ck-box::after{ content:'✓'; position:absolute; inset:0;
  color:#fff; font-size:2.8mm; line-height:3.8mm; text-align:center; }

/* один связный ответ на несколько строк -> растущий textarea */
textarea.wlta{ width:100%; display:block; background:transparent; border:0;
  border-bottom:.9pt solid var(--line-s); border-radius:0; padding:1mm 1mm 1mm 0;
  font-family:'Inter',sans-serif; font-size:9.6pt; line-height:1.55; color:#123;
  outline:none; resize:none; overflow:hidden; }
textarea.wlta.s{ font-size:9.4pt; }
textarea.wlta.d{ border-bottom-style:dashed; }
textarea.wlta:focus{ background:#FFF8E8; }

/* широкие таблицы на узком экране получают свою горизонтальную прокрутку */
.tbl-scroll{ width:100%; }

/* холст для рисования */
.canvas-wrap{ position:relative; }
.canvas-wrap canvas{ position:absolute; inset:0; width:100%; height:100%;
  cursor:crosshair; touch-action:none; z-index:1; }
.canvas-over{ position:absolute; inset:0; z-index:2; pointer-events:none; }
.canvas-tools{ position:absolute; right:3mm; bottom:3mm; z-index:3; display:flex; gap:2px;
  background:rgba(18,50,79,.85); border-radius:8px; padding:3px; }
.canvas-tools .ctool{ border:0; background:transparent; color:#fff; font-size:13px; line-height:1;
  cursor:pointer; border-radius:6px; padding:6px 8px; font-family:'Inter',sans-serif; }
.canvas-tools .ctool:hover{ background:rgba(255,255,255,.18); }
.canvas-tools .ctool.active{ background:var(--orange); }

/* печать: возвращаем ровно печатный вид */
@media print{
  .topbar, .canvas-tools{ display:none !important; }
  body{ background:#fff; }
  .stage{ padding:0; gap:0; }
  .page{ box-shadow:none; zoom:1 !important; }
  input.wl, input.wlbl-in, input.td-in{ background:transparent !important; }
}

/* ============ ТЕЛЕФОН (< 768px): снимаем A4-масштаб, одна колонка ============ */
@media (max-width:767px){
  html{ -webkit-text-size-adjust:100%; }
  body{ font-size:16px; }

  .topbar{ flex-wrap:wrap; gap:8px; padding:8px 10px; }
  .topbar button, .topbar select{ min-height:40px; font-size:14px; padding:9px 12px; }
  .topbar .brand{ font-size:14px; }
  .topbar .counter{ font-size:12px; }

  .stage{ padding:10px 8px 40px; gap:12px; }

  /* снимаем "бумажный" A4-чехол постранично: ширина/высота, тень, обрезка */
  .page{ width:100% !important; max-width:100% !important; height:auto !important;
    min-height:0 !important; box-shadow:none !important; border-radius:10px;
    overflow:visible !important; padding:14px !important; zoom:1 !important; }
  .page .hd, .page .ft{ position:static !important; margin:0 0 10px; }
  .page .ft{ margin:12px 0 0; }
  .page .body{ margin-top:10px !important; overflow:visible !important; min-height:0 !important; }
  .page.cover .body{ height:auto !important; }

  /* верстка заданий использует фиксированные mm-размеры под A4 — на телефоне
     всё, что не таблица (у таблиц своя горизонтальная прокрутка), сжимается
     в ширину контейнера вместо горизонтального выпирания за край страницы */
  .page :not(table):not(table *){ max-width:100% !important; }

  .grid2, .grid3, .grid4{ grid-template-columns:1fr !important; }
  .row{ flex-direction:column; }

  p, .lead, .tiny, .bul, .kv, .kv span, .task .tt, .task .hint, .ck span{
    font-size:16px !important; line-height:1.5 !important; }
  h1{ font-size:24px !important; }
  h2{ font-size:18px !important; }
  .label, .mono, .tstep, .chip{ font-size:11px !important; }

  input.wl, input.wl.s, input.wl.d, input.wlbl-in, input.td-in, textarea.wlta{
    font-size:16px !important; height:auto !important; min-height:40px !important;
    padding:9px 2px !important; }
  textarea.wlta{ min-height:84px !important; }

  .wbox, .canvas-wrap{ width:100% !important; height:auto !important; aspect-ratio:4/3; }

  label.ck{ min-height:40px; display:flex; align-items:center; gap:3mm; margin-bottom:6px; }
  .ck-box{ width:22px; height:22px; }
  label.ck input:checked + .ck-box::after{ font-size:15px; line-height:22px; }

  .tbl-scroll{ overflow-x:auto; -webkit-overflow-scrolling:touch; margin:0 -14px; padding:0 14px; }
  .tbl-scroll table{ min-width:560px; font-size:14px; }

  .canvas-tools .ctool{ min-width:40px; min-height:40px; font-size:15px; }
}
"""

CANVAS_CORE_JS = """
/* ============ Общий движок холста: штрихи, отмена, кисть, ластик =========
 * Используется и в автономной версии (localStorage), и в платформенной
 * (API) — отличается только тем, откуда берётся исходное изображение и
 * куда уходит результат (см. opts.loadSrc / opts.onSave).
 *
 * История штрихов живёт только в памяти вкладки: отмена штриха работает,
 * пока страницу не перезагрузили — на сервере/в localStorage по-прежнему
 * хранится один PNG-растр на холст, без вектора. Это осознанное упрощение:
 * бэкенд для векторных слоёв не заказывали, а поверх PNG "вечная" история
 * отмены не реализуема без смены формата хранения.
 */
function wbSetupCanvas(cv, opts){
  var wrap = cv.parentElement;
  var readonly = !!opts.readonly;
  var ctx = cv.getContext('2d');
  var strokes = [];
  var current = null;
  var baseImg = null;
  var tool = { size: 3.2, erase: false };

  function sizeCanvas(){
    var r = wrap.getBoundingClientRect();
    var dpr = Math.max(1, window.devicePixelRatio || 1);
    cv.width = Math.max(1, Math.round(r.width * dpr));
    cv.height = Math.max(1, Math.round(r.height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return r;
  }

  function drawStroke(s){
    if(!s.points.length) return;
    ctx.save();
    ctx.globalCompositeOperation = s.erase ? 'destination-out' : 'source-over';
    ctx.strokeStyle = '#1B3A5C';
    ctx.lineWidth = s.size;
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(s.points[0][0], s.points[0][1]);
    for(var i = 1; i < s.points.length; i++) ctx.lineTo(s.points[i][0], s.points[i][1]);
    if(s.points.length === 1) ctx.lineTo(s.points[0][0] + 0.01, s.points[0][1] + 0.01);
    ctx.stroke();
    ctx.restore();
  }

  function renderAll(){
    var r = wrap.getBoundingClientRect();
    ctx.clearRect(0, 0, r.width, r.height);
    if(baseImg){ try { ctx.drawImage(baseImg, 0, 0, r.width, r.height); } catch(e){} }
    strokes.forEach(drawStroke);
  }

  function loadBase(src){
    if(!src){ baseImg = null; renderAll(); if(opts.onLoaded) opts.onLoaded(); return; }
    var img = new Image();
    img.onload = function(){ baseImg = img; renderAll(); if(opts.onLoaded) opts.onLoaded(); };
    img.onerror = function(){ baseImg = null; renderAll(); if(opts.onLoaded) opts.onLoaded(); };
    img.src = src;
  }

  setTimeout(function(){
    sizeCanvas();
    opts.loadSrc(loadBase);
  }, 60);

  var resizeTimer = null;
  window.addEventListener('resize', function(){
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function(){ sizeCanvas(); renderAll(); }, 200);
  });
  window.addEventListener('orientationchange', function(){
    setTimeout(function(){ sizeCanvas(); renderAll(); }, 250);
  });

  function pos(e){
    var r = wrap.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }
  function persist(){ if(opts.onSave) opts.onSave(cv); }

  if(!readonly){
    cv.addEventListener('pointerdown', function(e){
      current = { erase: tool.erase, size: tool.size, points: [pos(e)] };
      strokes.push(current);
      try { cv.setPointerCapture(e.pointerId); } catch(err){}
      renderAll();
    });
    cv.addEventListener('pointermove', function(e){
      if(!current) return;
      current.points.push(pos(e));
      renderAll();
    });
    function endStroke(){
      if(!current) return;
      current = null;
      persist();
    }
    cv.addEventListener('pointerup', endStroke);
    cv.addEventListener('pointercancel', endStroke);
    cv.addEventListener('pointerleave', function(){ if(current) endStroke(); });

    var tools = wrap.querySelector('.canvas-tools');
    if(tools){
      var sizeMap = { thin: 1.6, medium: 3.2, thick: 6 };
      function markActive(act){
        tools.querySelectorAll('.ctool').forEach(function(b){
          var a = b.getAttribute('data-act');
          if(a === 'undo' || a === 'clear') return;
          var isOn = a === 'eraser' ? tool.erase : (!tool.erase && sizeMap[a] === tool.size);
          b.classList.toggle('active', isOn);
        });
      }
      tools.querySelectorAll('.ctool').forEach(function(btn){
        btn.addEventListener('click', function(){
          var act = btn.getAttribute('data-act');
          if(act === 'thin' || act === 'medium' || act === 'thick'){
            tool.size = sizeMap[act]; tool.erase = false;
          } else if(act === 'eraser'){
            tool.erase = !tool.erase;
          } else if(act === 'undo'){
            if(strokes.length){ strokes.pop(); renderAll(); persist(); }
          } else if(act === 'clear'){
            if(!confirm('Стереть весь рисунок? Это нельзя отменить.')) return;
            strokes = []; baseImg = null; renderAll(); persist();
          }
          markActive(act);
        });
      });
      markActive('medium');
    }
  } else {
    var toolsRo = wrap.querySelector('.canvas-tools');
    if(toolsRo) toolsRo.style.display = 'none';
    cv.style.pointerEvents = 'none';
  }

  return {
    setBaseSrc: function(src){ loadBase(src); }
  };
}
"""

WEB_JS = CANVAS_CORE_JS + """
/* ============ Масштаб, навигация, автосохранение ============ */
(function(){
  var KEY = 'primeteens-workbook-v4';
  var store = {};
  try { store = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e){ store = {}; }

  var savedTag = document.querySelector('.saved');
  var saveTimer = null;
  function save(){
    try { localStorage.setItem(KEY, JSON.stringify(store)); } catch(e){}
    if(savedTag){ savedTag.classList.add('on');
      clearTimeout(saveTimer);
      saveTimer = setTimeout(function(){ savedTag.classList.remove('on'); }, 1200); }
  }

  /* --- автоподгонка высоты textarea под содержимое --- */
  function autosize(el){
    el.style.height = 'auto';
    el.style.height = el.scrollHeight + 'px';
  }

  /* --- текстовые поля, textarea и чекбоксы --- */
  document.querySelectorAll('[data-f]').forEach(function(el){
    var k = el.getAttribute('data-f');
    if(el.tagName === 'INPUT' && el.type === 'checkbox'){
      if(store[k]) el.checked = true;
      el.addEventListener('change', function(){ store[k] = el.checked; save(); });
    } else if(el.tagName === 'INPUT'){
      if(store[k]) el.value = store[k];
      el.addEventListener('input', function(){ store[k] = el.value; save(); });
    } else if(el.tagName === 'TEXTAREA'){
      if(store[k]) el.value = store[k];
      autosize(el);
      el.addEventListener('input', function(){ store[k] = el.value; autosize(el); save(); });
      window.addEventListener('resize', function(){ autosize(el); });
    }
  });

  /* --- холсты для рисования --- */
  document.querySelectorAll('canvas[data-f]').forEach(function(cv){
    var k = cv.getAttribute('data-f');
    wbSetupCanvas(cv, {
      readonly: false,
      loadSrc: function(cb){ cb(store[k] || null); },
      onSave: function(canvasEl){
        try { store[k] = canvasEl.toDataURL('image/png'); save(); } catch(e){}
      }
    });
  });

  /* --- масштаб страниц под ширину экрана (zoom меняет и высоту); на
     телефоне (< 768px) масштаб снят вовсе — раскладка идёт в одну колонку
     через CSS-медиазапрос, см. WEB_CSS --- */
  var MM = 210 * 96 / 25.4; // ширина A4 в px при 96dpi
  function scale(){
    if(window.innerWidth < 768){
      document.querySelectorAll('.page').forEach(function(p){ p.style.zoom = ''; });
      return;
    }
    var avail = Math.min(document.querySelector('.stage').clientWidth - 16, 1000);
    var s = Math.min(1, avail / MM);
    document.querySelectorAll('.page').forEach(function(p){ p.style.zoom = s; });
  }
  scale();
  window.addEventListener('resize', function(){ clearTimeout(window._st);
    window._st = setTimeout(scale, 150); });

  /* --- навигация --- */
  var sel = document.getElementById('nav');
  if(sel) sel.addEventListener('change', function(){
    var t = document.getElementById('page-' + sel.value);
    if(t) t.scrollIntoView({behavior:'smooth', block:'start'});
  });
  var counter = document.querySelector('.counter');
  var pages = Array.prototype.slice.call(document.querySelectorAll('.page'));
  window.addEventListener('scroll', function(){
    var mid = window.innerHeight / 2, cur = 1;
    pages.forEach(function(p){ var r = p.getBoundingClientRect();
      if(r.top < mid) cur = +p.dataset.page; });
    if(counter) counter.textContent = cur + ' / ' + pages.length;
  });

  var btnPrint = document.getElementById('btn-print');
  if(btnPrint) btnPrint.addEventListener('click', function(){ window.print(); });

  var btnReset = document.getElementById('btn-reset');
  if(btnReset) btnReset.addEventListener('click', function(){
    if(!confirm('Стереть все записи в тетради? Это нельзя отменить.')) return;
    store = {}; save(); location.reload();
  });
})();
"""


PLATFORM_CSS = """
/* ============ ПЛАТФОРМЕННЫЙ СЛОЙ (поверх WEB_CSS) ============ */
.topbar .netstatus{ font-size:12px; color:#ffcf7a; opacity:0; transition:opacity .25s; }
.topbar .netstatus.on{ opacity:1; }
/* «Поток завершён» — спокойный статус, в отличие от оранжевого netstatus (это не ошибка) */
.topbar .archived{ font-size:12px; color:#bcd3e8; opacity:0; transition:opacity .25s; }
.topbar .archived.on{ opacity:1; }
.wb-locked canvas{ pointer-events:none; }

/* Печатный снимок (/workbook/print, см. app/workbook/print/route.ts): та же
   разметка, что и @media print ниже (WEB_CSS), но включается явным классом —
   так страница выглядит как печатная версия и в обычном браузере, не только
   под Chromium'ом page.pdf(), который сам подставляет media=print. */
.wb-print-mode .topbar, .wb-print-mode .canvas-tools{ display:none !important; }
.wb-print-mode{ background:#fff; }
.wb-print-mode .stage{ padding:0 !important; gap:0 !important; }
.wb-print-mode .page{ box-shadow:none !important; zoom:1 !important; }
.wb-print-mode input.wl, .wb-print-mode input.wlbl-in, .wb-print-mode input.td-in{ background:transparent !important; }
input.wl:disabled, input.wlbl-in:disabled, input.td-in:disabled, textarea.wlta:disabled,
label.ck input:disabled + .ck-box{ opacity:.85; cursor:default; }
@keyframes wbFlash{
  0%{ box-shadow:0 0 0 3px rgba(201,162,75,.95); }
  100%{ box-shadow:0 0 0 3px rgba(201,162,75,0); }
}
.wb-flash{ animation: wbFlash 1.4s ease-out; border-radius:3px; }

/* компактная шапка: всегда одна строка, тетрадь получает максимум экрана */
.topbar{ flex-wrap:nowrap !important; gap:10px; padding:6px 12px; min-height:44px; }
.topbar .brand{ font-size:13px; white-space:nowrap; }
.topbar select{ flex:0 1 auto; min-width:0; max-width:340px; text-overflow:ellipsis; }
.topbar .counter{ white-space:nowrap; }
/* статусы висят ярлычком под шапкой и не занимают в ней место */
.topbar .saved, .topbar .netstatus{ position:absolute; right:12px; top:100%; white-space:nowrap;
  font-size:11px; padding:2px 8px; border-radius:0 0 6px 6px; background:#12324F;
  pointer-events:none; }
.stage{ padding:14px 8px 40px; gap:14px; }

@media (max-width:767px){
  .topbar{ gap:8px; padding:6px 8px; min-height:48px; }
  .topbar .brand, .topbar .spacer{ display:none; }
  .topbar select{ flex:1 1 auto; max-width:none; min-height:36px; font-size:14px; padding:6px 10px; }
  .stage{ padding:6px 4px 32px; gap:8px; }
  .page{ padding:12px !important; border-radius:8px; }
}
"""

# Клиентский слой для платформы: вместо localStorage читает/пишет через API
# хоста (см. workbook/README раздел "платформа"). Конфиг приходит через
# window.__WB__ = {mode:"edit"|"readonly", studentId, apiBase}, который
# инжектит серверный route handler перед этим скриптом (см.
# app/workbook/frame/route.ts в основном Next.js приложении) — так cookies
# сессии остаются same-origin и для этой страницы, и для fetch-запросов к API.
PLATFORM_JS = CANVAS_CORE_JS + """
(function(){
  var WB = window.__WB__ || {};
  var API = WB.apiBase || '/api/workbook';
  var studentId = WB.studentId;
  var readonly = WB.mode !== 'edit';
  if(!studentId) return;

  if(WB.print) document.body.classList.add('wb-print-mode');

  // Read-only GET requests (entries/drawings/stream) carry the print token
  // along when we have one — see app/workbook/print/route.ts and
  // authorizeStudentRead in lib/auth/authorize.ts. Only set when this page
  // was itself opened with a token (PDF export via headless Chromium, no
  // session cookie); a live session (student/mentor/admin) doesn't need it,
  // those requests already carry the session cookie.
  function withToken(url){
    if(!WB.token) return url;
    return url + (url.indexOf('?') >= 0 ? '&' : '?') + 'token=' + encodeURIComponent(WB.token);
  }

  var savedTag = document.querySelector('.saved');
  var netTag = document.querySelector('.netstatus');
  var archivedTag = document.querySelector('.archived');
  if(WB.archived && archivedTag) archivedTag.classList.add('on');
  function flashSaved(){
    if(!savedTag) return;
    savedTag.classList.add('on');
    clearTimeout(flashSaved._t);
    flashSaved._t = setTimeout(function(){ savedTag.classList.remove('on'); }, 1200);
  }
  function setNet(ok){ if(netTag) netTag.classList.toggle('on', !ok); }
  function highlight(el){
    if(!el) return;
    el.classList.remove('wb-flash'); void el.offsetWidth;
    el.classList.add('wb-flash');
    setTimeout(function(){ el.classList.remove('wb-flash'); }, 1500);
  }

  var pending = {}, timers = {}, failed = {}, retryTimer = null;

  function scheduleSave(fieldId, value, delay){
    pending[fieldId] = value;
    clearTimeout(timers[fieldId]);
    timers[fieldId] = setTimeout(function(){ flushField(fieldId); }, delay);
  }
  function flushField(fieldId){
    if(!(fieldId in pending)) return;
    var value = pending[fieldId];
    delete pending[fieldId];
    fetch(API + '/' + studentId + '/entries/' + encodeURIComponent(fieldId), {
      method: 'PUT', credentials: 'same-origin',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({value: value})
    }).then(function(r){
      if(!r.ok) throw new Error('status ' + r.status);
      delete failed[fieldId]; setNet(true); flashSaved();
    }).catch(function(){
      failed[fieldId] = value; setNet(false); scheduleRetry();
    });
  }
  function scheduleRetry(){
    if(retryTimer) return;
    retryTimer = setTimeout(function(){
      retryTimer = null;
      var ids = Object.keys(failed);
      if(!ids.length){ setNet(true); return; }
      ids.forEach(function(id){ var v = failed[id]; delete failed[id]; pending[id] = v; flushField(id); });
    }, 3000);
  }

  function autosize(el){
    el.style.height = 'auto';
    el.style.height = el.scrollHeight + 'px';
  }

  if(!readonly){
    document.querySelectorAll('[data-f]').forEach(function(el){
      var k = el.getAttribute('data-f');
      if(el.tagName === 'INPUT' && el.type === 'checkbox'){
        el.addEventListener('change', function(){ scheduleSave(k, el.checked, 50); });
      } else if(el.tagName === 'INPUT'){
        el.addEventListener('input', function(){ scheduleSave(k, el.value, 800); });
      } else if(el.tagName === 'TEXTAREA'){
        autosize(el);
        el.addEventListener('input', function(){ scheduleSave(k, el.value, 800); autosize(el); });
        window.addEventListener('resize', function(){ autosize(el); });
      }
    });
  } else {
    document.querySelectorAll('[data-f]').forEach(function(el){
      if(el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') el.disabled = true;
    });
  }

  var canvasTimers = {};
  function scheduleCanvasSave(fieldId, cv){
    clearTimeout(canvasTimers[fieldId]);
    canvasTimers[fieldId] = setTimeout(function(){ flushCanvas(fieldId, cv); }, 1500);
  }
  function flushCanvas(fieldId, cv){
    cv.toBlob(function(blob){
      if(!blob) return;
      fetch(API + '/' + studentId + '/drawings/' + encodeURIComponent(fieldId), {
        method: 'PUT', credentials: 'same-origin',
        headers: {'Content-Type':'image/png'}, body: blob
      }).then(function(r){
        if(!r.ok) throw new Error('status ' + r.status);
        setNet(true); flashSaved();
      }).catch(function(){ setNet(false); });
    }, 'image/png');
  }

  // Readiness signal for the PDF export script (Playwright waits on
  // window.__WB_READY__ === true before printing — see
  // lib/workbook/export-pdf.ts) — true once the entries fetch has resolved
  // (or failed) AND every canvas has loaded its drawing (or failed to).
  var totalCanvases = document.querySelectorAll('canvas[data-f]').length;
  var loadedCanvases = 0;
  var entriesReady = false;
  function maybeReady(){
    if(entriesReady && loadedCanvases >= totalCanvases) window.__WB_READY__ = true;
  }

  var canvasHandles = {};
  document.querySelectorAll('canvas[data-f]').forEach(function(cv){
    var k = cv.getAttribute('data-f');
    var url = API + '/' + studentId + '/drawings/' + encodeURIComponent(k);
    canvasHandles[k] = wbSetupCanvas(cv, {
      readonly: readonly,
      loadSrc: function(cb){ cb(withToken(url + '?t=' + Date.now())); },
      onSave: function(canvasEl){ scheduleCanvasSave(k, canvasEl); },
      onLoaded: function(){ loadedCanvases++; maybeReady(); }
    });
  });

  // Readonly (mentor) view: apply one value, highlighting it only if it changed.
  function applyValue(el, v, flash){
    var before = (el.type === 'checkbox') ? el.checked : el.value;
    if(el.tagName === 'INPUT' && el.type === 'checkbox'){ el.checked = !!v; }
    else if(el.tagName === 'INPUT'){ el.value = v || ''; }
    else if(el.tagName === 'TEXTAREA'){ el.value = v || ''; autosize(el); }
    var after = (el.type === 'checkbox') ? el.checked : el.value;
    if(flash && before !== after) highlight(el.closest('.wl, .wlbl, .wlta, td, label.ck') || el);
  }

  // fieldId -> updatedAt of the drawing as last shown; a newer value from a poll
  // means the student drew something, so the canvas reloads its image.
  var drawingSeen = {};

  function reloadDrawing(fieldId, stamp, flash){
    var handle = canvasHandles[fieldId];
    if(!handle) return;
    handle.setBaseSrc(withToken(API + '/' + studentId + '/drawings/' + encodeURIComponent(fieldId) + '?t=' + encodeURIComponent(stamp || Date.now())));
    var cv = document.querySelector('canvas[data-f="' + fieldId + '"]');
    if(flash && cv) highlight(cv.parentElement);
  }

  function loadEntries(flash){
    return fetch(withToken(API + '/' + studentId + '/entries'), {credentials:'same-origin', cache:'no-store'})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(data){
        if(!data) return;
        var drawings = data.drawings || {};
        Object.keys(drawings).forEach(function(k){
          if(drawingSeen[k] === drawings[k]) return;
          var firstLoad = !(k in drawingSeen) && !flash;
          drawingSeen[k] = drawings[k];
          if(!firstLoad && readonly) reloadDrawing(k, drawings[k], flash);
        });
        var entries = data.entries || {};
        document.querySelectorAll('[data-f]').forEach(function(el){
          var k = el.getAttribute('data-f');
          if(el.tagName === 'CANVAS') return;
          if(!(k in entries)){ if(flash) applyValue(el, el.type === 'checkbox' ? false : '', true); return; }
          applyValue(el, entries[k], flash);
        });
        if(readonly) setNet(true);
      })
      .catch(function(){ setNet(false); });
  }

  loadEntries(false).then(function(){ entriesReady = true; maybeReady(); });

  if(readonly){
    // Live updates come over SSE. Some proxies (e.g. a Cloudflare quick tunnel
    // used for Telegram Mini App testing) buffer the stream so nothing arrives;
    // the server sends "hello"/"ping" events every 10 s, and if none has been
    // seen for 15 s we poll the entries every 3 s instead. Every (re)connect
    // also refetches, so events missed during a reconnect aren't lost.
    var lastLive = 0;
    var markLive = function(){ lastLive = Date.now(); };
    setInterval(function(){
      if(Date.now() - lastLive > 15000) loadEntries(true);
    }, 3000);
  }

  // "Завершить поток" can happen while this tab is open — either an admin
  // clicking the button, or the bot's automatic archive-lock job once the
  // hackathon (last course day) is over. Either way the server broadcasts
  // an "archive_changed" event to every student in the group (see
  // notifyGroupArchiveChanged in lib/realtime.ts / db.notify_workbook in the
  // bot). We listen for it even in edit mode — normally edit-mode tabs don't
  // need an SSE connection (the student's own edits are the source of
  // truth), but this is the one server-initiated change that can happen to
  // an edit-mode tab, and locking a student out live (rather than only on
  // next navigation) is the whole point of "the stream can no longer be
  // changed once it ends".
  function handleArchiveChanged(e){
    var msg = {};
    try { msg = JSON.parse(e.data); } catch(err){}
    if(msg.archived){
      if(archivedTag) archivedTag.classList.add('on');
      document.body.classList.add('wb-locked');
      document.querySelectorAll('[data-f]').forEach(function(el){
        if(el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') el.disabled = true;
      });
    }
    // A full reload re-fetches __WB__ from /workbook/frame, which recomputes
    // mode/archived from the DB — simplest way to land in a fully consistent
    // state (readonly wiring, disabled canvases, notice) after either a lock
    // or an unlock, rather than hand-rolling every transition client-side.
    setTimeout(function(){ window.location.reload(); }, msg.archived ? 1200 : 300);
  }

  if(window.EventSource){
    var es = new EventSource(withToken(API + '/' + studentId + '/stream'));
    es.addEventListener('archive_changed', handleArchiveChanged);
    if(readonly){
      es.addEventListener('hello', function(){ markLive(); loadEntries(true); });
      es.addEventListener('ping', markLive);
      es.addEventListener('entry', function(e){
        markLive();
        try {
          var msg = JSON.parse(e.data);
          var el = document.querySelector('[data-f="' + msg.fieldId + '"]');
          if(!el) return;
          applyValue(el, msg.value, true);
        } catch(err){}
      });
      es.addEventListener('drawing', function(e){
        markLive();
        try {
          var msg = JSON.parse(e.data);
          if(msg.updatedAt) drawingSeen[msg.fieldId] = msg.updatedAt;
          reloadDrawing(msg.fieldId, msg.updatedAt, true);
        } catch(err){}
      });
      es.onerror = function(){ setNet(false); };
      es.addEventListener('open', function(){ setNet(true); });
    }
  }

  var MM = 210 * 96 / 25.4;
  function scale(){
    if(window.innerWidth < 768){
      document.querySelectorAll('.page').forEach(function(p){ p.style.zoom = ''; });
      return;
    }
    var stageEl = document.querySelector('.stage');
    if(!stageEl) return;
    // Fill the available width: a laptop/desktop gets a larger A4 page with
    // proportionally larger text instead of a 794px column in empty space.
    var avail = stageEl.clientWidth - 16;
    var s = Math.min(1.6, avail / MM);
    document.querySelectorAll('.page').forEach(function(p){ p.style.zoom = s; });
  }
  scale();
  window.addEventListener('resize', function(){ clearTimeout(window._st); window._st = setTimeout(scale, 150); });

  var sel = document.getElementById('nav');
  if(sel) sel.addEventListener('change', function(){
    var t = document.getElementById('page-' + sel.value);
    if(t) t.scrollIntoView({behavior:'smooth', block:'start'});
  });
  var counter = document.querySelector('.counter');
  var pages = Array.prototype.slice.call(document.querySelectorAll('.page'));
  window.addEventListener('scroll', function(){
    var mid = window.innerHeight / 2, cur = 1;
    pages.forEach(function(p){ var r = p.getBoundingClientRect();
      if(r.top < mid) cur = +p.dataset.page; });
    if(counter) counter.textContent = cur + ' / ' + pages.length;
  });

  var btnPrint = document.getElementById('btn-print');
  if(btnPrint) btnPrint.addEventListener('click', function(){ window.print(); });
})();
"""


def write_manifest(path):
    canonical = '\n'.join(f"{f['id']}:{f['type']}" for f in MANIFEST_FIELDS)
    version = hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:12]
    manifest = {'version': version, 'fields': MANIFEST_FIELDS}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write('\n')
    return manifest


if __name__ == '__main__':
    try:
        body, n, nav = build_pages()
    except BuildError as e:
        raise SystemExit(f'ОШИБКА СБОРКИ: {e}')

    body = re.sub(r'\{\{P\s+(\w+)\}\}', lambda m: ANCHORS.get(m.group(1), '--'), body)

    options = ''.join(f'<option value="{num}">{label}</option>' for num, label in nav)
    topbar = (
        '<div class="topbar">'
        '<span class="brand">PrimeTeens · Рабочая тетрадь</span>'
        f'<select id="nav"><option value="1">В начало</option>{options}</select>'
        '<span class="spacer"></span>'
        f'<span class="counter">1 / {n}</span>'
        '<span class="saved">сохранено</span>'
        '<button id="btn-print" type="button">Печать</button>'
        '<button id="btn-reset" type="button">Очистить</button>'
        '</div>'
    )

    html = (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>PrimeTeens · Рабочая тетрадь</title>"
        f"{FONTS_LINK}"
        f"<style>{CSS}\n{WEB_CSS}</style></head><body>"
        f"{topbar}<div class='stage'>{body}</div>"
        f"<script>{WEB_JS}</script></body></html>"
    )
    out_path = '../index.html'
    open(out_path, 'w', encoding='utf-8').write(html)
    manifest = write_manifest('../dist/manifest.json')

    # ---- платформенная сборка (public/workbook/app.html + lib/workbook/manifest.json) ----
    # window.__WB__ инжектится сервером (Next.js route handler), здесь его нет —
    # PLATFORM_JS просто ничего не делает, пока __WB__ не установлен.
    topbar_platform = (
        '<div class="topbar">'
        '<span class="brand">PrimeTeens · Тетрадь</span>'
        f'<select id="nav"><option value="1">В начало</option>{options}</select>'
        '<span class="spacer"></span>'
        f'<span class="counter">1 / {n}</span>'
        '<span class="saved">сохранено</span>'
        '<span class="netstatus">нет связи, повторяем…</span>'
        '<span class="archived">Поток завершён · только чтение</span>'
        '</div>'
    )
    html_platform = (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>PrimeTeens · Рабочая тетрадь</title>"
        f"{FONTS_LINK}"
        f"<style>{CSS}\n{WEB_CSS}\n{PLATFORM_CSS}</style></head><body>"
        f"{topbar_platform}<div class='stage'>{body}</div>"
        f"<script>{PLATFORM_JS}</script></body></html>"
    )
    platform_out = '../../public/workbook/app.html'
    os.makedirs(os.path.dirname(platform_out), exist_ok=True)
    open(platform_out, 'w', encoding='utf-8').write(html_platform)
    write_manifest('../../lib/workbook/manifest.json')

    size = os.path.getsize(out_path) / 1024
    platform_size = os.path.getsize(platform_out) / 1024
    by_type = {}
    for f in MANIFEST_FIELDS:
        by_type[f['type']] = by_type.get(f['type'], 0) + 1
    print(f'страниц: {n} | размер: {size:.0f} КБ | разделов в навигации: {len(nav)}')
    print(f'полей: {by_type} | всего: {len(MANIFEST_FIELDS)} | манифест: dist/manifest.json (v{manifest["version"]})')
    print(f'платформа: {platform_out} ({platform_size:.0f} КБ) | манифест: lib/workbook/manifest.json')
