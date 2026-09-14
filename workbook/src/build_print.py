import re, json, glob, sys, asyncio, os
from playwright.async_api import async_playwright

B = json.load(open('assets/b64.json'))
CSS = open('theme.css').read()
ANCHORS = {}

FONTS = f"""
@font-face{{font-family:'Unbounded';src:url(data:font/ttf;base64,{B['unb']}) format('truetype');font-weight:100 900;}}
@font-face{{font-family:'Inter';src:url(data:font/ttf;base64,{B['inter']}) format('truetype');font-weight:100 900;}}
@font-face{{font-family:'Source Serif 4';src:url(data:font/ttf;base64,{B['serif']}) format('truetype');font-weight:200 900;font-style:normal;}}
@font-face{{font-family:'Source Serif 4';src:url(data:font/ttf;base64,{B['serifit']}) format('truetype');font-weight:200 900;font-style:italic;}}
@font-face{{font-family:'JetBrains Mono';src:url(data:font/ttf;base64,{B['mono']}) format('truetype');font-weight:100 800;}}
"""
LOGO = f"data:image/png;base64,{B['logo']}"


def macros(s):
    # Начиная с версии со стабильными id полей (см. build_web.py), в
    # исходниках parts/*.html у {{L n}}/{{LS n}}/{{LD n}} и {{K подпись}}
    # появился необязательный суффикс "|id=..." — устойчивый id поля для
    # веб-версии и манифеста. Печатной версии он не нужен (тут нет полей
    # ввода), поэтому просто отбрасываем его при разборе макроса.
    # "|ta" — ещё один необязательный суффикс (см. build_web.py): в вебе
    # такая группа строк становится одним растущим textarea вместо
    # отдельных полей на каждую строку. В печати разницы нет — как и
    # раньше, рисуем n разлинованных строк.
    def rep(m):
        kind, n = m.group(1), int(m.group(2))
        cls = {'L': 'wl', 'LS': 'wl s', 'LD': 'wl d'}[kind]
        return ''.join(f'<div class="{cls}"></div>' for _ in range(n))
    s = re.sub(r'\{\{(L|LS|LD)\s+(\d+)(?:\|id=[^|}]*)?(?:\|ta)?\}\}', rep, s)
    s = re.sub(r'\{\{K\s+(.*?)(?:\|id=[^}]*)?\}\}',
               lambda m: f'<div class="wlbl"><span class="k">{m.group(1)}</span></div>', s)
    return s.replace('{{LOGO}}', LOGO)


def build_pages():
    files = sorted(glob.glob('parts/*.html'))
    raw = '\n'.join(open(f, encoding='utf-8').read() for f in files)
    chunks = re.split(r'<!--PAGE(.*?)-->', raw)[1:]
    pages, n = [], 0
    total = len(chunks) // 2
    for i in range(0, len(chunks), 2):
        attrs, content = chunks[i], chunks[i + 1]
        get = lambda k: (re.search(k + r'="(.*?)"', attrs).group(1)
                         if re.search(k + r'="(.*?)"', attrs) else '')
        cls, hl, hr, fl = get('class'), get('hl'), get('hr'), get('fl')
        n += 1
        if get('anchor'):
            ANCHORS[get('anchor')] = f'{n:02d}'
        head = f'<div class="hd"><span>{hl}</span><span class="r">{hr}</span></div>' if hl or hr else ''
        foot = (f'<div class="ft"><span>{fl or "PRIMETEENS · РАБОЧАЯ ТЕТРАДЬ"}</span>'
                f'<span>{n:02d} / {total:02d}</span></div>') if 'nofoot' not in cls else ''
        pages.append(f'<section class="page {cls}">{head}<div class="body">{macros(content)}</div>{foot}</section>')
    return '\n'.join(pages), n


async def render(html_path, pdf_path):
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        await pg.goto('file://' + os.path.abspath(html_path))
        await pg.wait_for_timeout(1200)
        over = await pg.evaluate("""() => {
          const bad=[];
          document.querySelectorAll('.page').forEach((el,i)=>{
            const b=el.querySelector('.body');
            if(b && b.scrollHeight > b.clientHeight+2) bad.push([i+1, b.scrollHeight-b.clientHeight]);
          });
          return bad;
        }""")
        print('!! ПЕРЕПОЛНЕНИЕ:', over) if over else print('переполнений нет')
        await pg.pdf(path=pdf_path, format='A4', print_background=True,
                     margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'})
        await b.close()


if __name__ == '__main__':
    body, n = build_pages()
    body = re.sub(r'\{\{P\s+(\w+)\}\}', lambda m: ANCHORS.get(m.group(1), '--'), body)
    html = (f"<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
            f"<style>{FONTS}\n{CSS}</style></head><body>{body}</body></html>")
    open('out.html', 'w', encoding='utf-8').write(html)
    print('страниц:', n)
    asyncio.run(render('out.html', 'PrimeTeens_Workbook.pdf'))