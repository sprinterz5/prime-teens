"""
Сборка ВЕБ-версии рабочей тетради из тех же parts/*.html + theme.css.
Отличия от build.py (печатной версии):
  - шрифты подключаются с Google Fonts, а не вшиваются base64 (файл ~200 КБ вместо 6 МБ)
  - поля для письма превращаются в <input>/<textarea>
  - чекбоксы становятся настоящими
  - области для рисования получают <canvas>
  - добавлена навигация, масштабирование под экран и автосохранение
"""
import re, json, glob, os

CSS = open('theme.css', encoding='utf-8').read()
B = json.load(open('assets/b64.json'))
LOGO = f"data:image/png;base64,{B['logo_web']}"
ANCHORS = {}

FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Unbounded:wght@400;700;800&'
    'family=Inter:wght@400;500;600;700&'
    'family=Source+Serif+4:ital,wght@0,400;0,600;1,400&'
    'family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">'
)

# ─────────────────────────────────────────── макросы (как в печатной версии)
def macros(s):
    def rep(m):
        kind, n = m.group(1), int(m.group(2))
        cls = {'L': 'wl', 'LS': 'wl s', 'LD': 'wl d'}[kind]
        return ''.join(f'<div class="{cls}"></div>' for _ in range(n))
    s = re.sub(r'\{\{(L|LS|LD)\s+(\d+)\}\}', rep, s)
    s = re.sub(r'\{\{K\s+(.*?)\}\}',
               lambda m: f'<div class="wlbl"><span class="k">{m.group(1)}</span></div>', s)
    return s.replace('{{LOGO}}', LOGO)


# ─────────────────────────────────────────── превращение в интерактив
def interactive(html, page_no):
    """Заменяет статичные поля на рабочие элементы формы."""
    counter = {'i': 0}

    def fid():
        counter['i'] += 1
        return f"p{page_no}f{counter['i']}"

    # линейки для письма -> текстовые поля
    def wl_rep(m):
        cls = m.group(1)
        return f'<input class="{cls}" type="text" data-f="{fid()}" autocomplete="off">'
    html = re.sub(r'<div class="(wl(?:\s+[sd])?)"></div>', wl_rep, html)

    # поле с моноширинной подписью слева
    def wlbl_rep(m):
        label = m.group(1)
        return (f'<div class="wlbl"><span class="k">{label}</span>'
                f'<input class="wlbl-in" type="text" data-f="{fid()}" autocomplete="off"></div>')
    html = re.sub(r'<div class="wlbl"><span class="k">(.*?)</span></div>', wlbl_rep, html)

    # чекбоксы
    def ck_rep(m):
        attrs, inner = m.group(1), m.group(2)
        return (f'<label class="ck"{attrs}><input type="checkbox" data-f="{fid()}">'
                f'<span class="ck-box"></span>{inner}</label>')
    html = re.sub(r'<div class="ck"(.*?)>(.*?)</div>', ck_rep, html, flags=re.S)

    # пустые ячейки таблиц -> поля ввода
    def td_rep(m):
        attrs = m.group(1) or ''
        return f'<td{attrs}><input class="td-in" type="text" data-f="{fid()}" autocomplete="off"></td>'
    html = re.sub(r'<td([^>]*)>\s*</td>', td_rep, html)

    # области для рисования -> холст (любые классы, с содержимым и без)
    def canvas_rep(m):
        cls, attrs, inner = m.group(1), m.group(2), m.group(3)
        return (f'<div class="{cls} canvas-wrap"{attrs}>'
                f'<canvas data-f="{fid()}"></canvas>'
                f'<div class="canvas-over">{inner}</div>'
                f'<button class="canvas-clear" type="button">Стереть</button></div>')
    html = re.sub(r'<div class="(wbox dot[^"]*)"([^>]*)>(.*?)</div>\s*(?=<|$)',
                  canvas_rep, html, flags=re.S)

    return html


# ─────────────────────────────────────────── сборка страниц
def build_pages():
    files = sorted(glob.glob('parts/*.html'))
    raw = '\n'.join(open(f, encoding='utf-8').read() for f in files)
    chunks = re.split(r'<!--PAGE(.*?)-->', raw)[1:]
    pages, nav, n = [], [], 0
    total = len(chunks) // 2
    for i in range(0, len(chunks), 2):
        attrs, content = chunks[i], chunks[i + 1]
        get = lambda k: (re.search(k + r'="(.*?)"', attrs).group(1)
                         if re.search(k + r'="(.*?)"', attrs) else '')
        cls, hl, hr, fl, anchor = get('class'), get('hl'), get('hr'), get('fl'), get('anchor')
        n += 1
        if anchor:
            ANCHORS[anchor] = f'{n:02d}'
            nav.append((n, hr or hl or anchor))
        head = f'<div class="hd"><span>{hl}</span><span class="r">{hr}</span></div>' if hl or hr else ''
        foot = (f'<div class="ft"><span>{fl or "PRIMETEENS · РАБОЧАЯ ТЕТРАДЬ"}</span>'
                f'<span>{n:02d} / {total:02d}</span></div>') if 'nofoot' not in cls else ''
        body = interactive(macros(content), n)
        pages.append(
            f'<section class="page {cls}" id="page-{n}" data-page="{n}">'
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
.wlbl{ gap:2mm; } .wlbl-in{ flex:1 1 auto; background:transparent; border:0; outline:none;
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

/* холст для рисования */
.canvas-wrap{ position:relative; }
.canvas-wrap canvas{ position:absolute; inset:0; width:100%; height:100%;
  cursor:crosshair; touch-action:none; z-index:1; }
.canvas-over{ position:absolute; inset:0; z-index:2; pointer-events:none; }
.canvas-clear{ position:absolute; right:3mm; bottom:3mm; z-index:3; font-size:11px;
  border:0; background:rgba(18,50,79,.8); color:#fff; border-radius:6px;
  padding:4px 9px; cursor:pointer; font-family:'Inter',sans-serif; }
.canvas-clear:hover{ background:#12324F; }

/* печать: возвращаем ровно печатный вид */
@media print{
  .topbar, .canvas-clear{ display:none !important; }
  body{ background:#fff; }
  .stage{ padding:0; gap:0; }
  .page{ box-shadow:none; zoom:1 !important; }
  input.wl, input.wlbl-in, input.td-in{ background:transparent !important; }
}
"""

WEB_JS = """
/* ============ Масштаб, навигация, автосохранение ============ */
(function(){
  var KEY = 'primeteens-workbook-v3';
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

  /* --- текстовые поля и чекбоксы --- */
  document.querySelectorAll('[data-f]').forEach(function(el){
    var k = el.getAttribute('data-f');
    if(el.tagName === 'INPUT' && el.type === 'checkbox'){
      if(store[k]) el.checked = true;
      el.addEventListener('change', function(){ store[k] = el.checked; save(); });
    } else if(el.tagName === 'INPUT'){
      if(store[k]) el.value = store[k];
      el.addEventListener('input', function(){ store[k] = el.value; save(); });
    }
  });

  /* --- холсты для рисования --- */
  document.querySelectorAll('canvas[data-f]').forEach(function(cv){
    var k = cv.getAttribute('data-f');
    var wrap = cv.parentElement;
    function fit(){
      var r = wrap.getBoundingClientRect();
      var data = cv.toDataURL && cv.width ? cv.toDataURL() : null;
      cv.width = Math.max(1, Math.round(r.width * 2));
      cv.height = Math.max(1, Math.round(r.height * 2));
      var ctx = cv.getContext('2d');
      ctx.scale(2,2); ctx.lineWidth = 1.6; ctx.lineCap='round'; ctx.lineJoin='round';
      ctx.strokeStyle = '#1B3A5C';
      var src = store[k] || data;
      if(src){ var img = new Image(); img.onload = function(){
        ctx.drawImage(img, 0, 0, r.width, r.height); }; img.src = src; }
    }
    setTimeout(fit, 60);
    window.addEventListener('resize', function(){ clearTimeout(cv._t); cv._t = setTimeout(fit, 250); });

    var drawing = false, ctx = cv.getContext('2d');
    function pos(e){ var r = cv.getBoundingClientRect();
      return { x:(e.clientX - r.left), y:(e.clientY - r.top) }; }
    cv.addEventListener('pointerdown', function(e){
      drawing = true; cv.setPointerCapture(e.pointerId);
      var p = pos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); });
    cv.addEventListener('pointermove', function(e){
      if(!drawing) return; var p = pos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); });
    function stop(){ if(!drawing) return; drawing = false;
      try { store[k] = cv.toDataURL('image/png'); save(); } catch(e){} }
    cv.addEventListener('pointerup', stop);
    cv.addEventListener('pointerleave', stop);

    var btn = wrap.querySelector('.canvas-clear');
    if(btn) btn.addEventListener('click', function(){
      ctx.clearRect(0,0,cv.width,cv.height); delete store[k]; save(); });
  });

  /* --- масштаб страниц под ширину экрана (zoom меняет и высоту) --- */
  var MM = 210 * 96 / 25.4; // ширина A4 в px при 96dpi
  function scale(){
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


if __name__ == '__main__':
    body, n, nav = build_pages()
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
    open('workbook_web.html', 'w', encoding='utf-8').write(html)
    size = os.path.getsize('workbook_web.html') / 1024
    print(f'страниц: {n} | размер: {size:.0f} КБ | разделов в навигации: {len(nav)}')
