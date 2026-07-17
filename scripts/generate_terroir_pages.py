#!/usr/bin/env python3
"""地域×全ジャンル横断「テロワールページ」生成。

/terroir/{pref}.html（47県）+ /terroir/index.html を生成する。
データは各ジャンルリポジトリのJSONを直接読む（このリポジトリの兄弟ディレクトリ）。
"""
import json
import glob
import os
import html

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)  # テロワールハブ　総合/
OUT = os.path.join(BASE, 'terroir')
TODAY = __import__('datetime').date.today().isoformat()

PREFS = [
    ('hokkaido','北海道'),('aomori','青森県'),('iwate','岩手県'),('miyagi','宮城県'),
    ('akita','秋田県'),('yamagata','山形県'),('fukushima','福島県'),('ibaraki','茨城県'),
    ('tochigi','栃木県'),('gunma','群馬県'),('saitama','埼玉県'),('chiba','千葉県'),
    ('tokyo','東京都'),('kanagawa','神奈川県'),('niigata','新潟県'),('toyama','富山県'),
    ('ishikawa','石川県'),('fukui','福井県'),('yamanashi','山梨県'),('nagano','長野県'),
    ('gifu','岐阜県'),('shizuoka','静岡県'),('aichi','愛知県'),('mie','三重県'),
    ('shiga','滋賀県'),('kyoto','京都府'),('osaka','大阪府'),('hyogo','兵庫県'),
    ('nara','奈良県'),('wakayama','和歌山県'),('tottori','鳥取県'),('shimane','島根県'),
    ('okayama','岡山県'),('hiroshima','広島県'),('yamaguchi','山口県'),('tokushima','徳島県'),
    ('kagawa','香川県'),('ehime','愛媛県'),('kochi','高知県'),('fukuoka','福岡県'),
    ('saga','佐賀県'),('nagasaki','長崎県'),('kumamoto','熊本県'),('oita','大分県'),
    ('miyazaki','宮崎県'),('kagoshima','鹿児島県'),('okinawa','沖縄県'),
]

GENRES = [
    # key, 表示名, 生産者呼称, 色, ドメイン, データパスパターン
    ('sake',    '日本酒',   '酒蔵',       '#B8452A', 'https://sake.terroirhub.com',
     os.path.join(ROOT, 'TerriorHUB　sake', 'data_{pref}_breweries.json')),
    ('wine',    'ワイン',   'ワイナリー', '#722F37', 'https://wine.terroirhub.com',
     os.path.join(ROOT, 'terroirHUB wine', 'data', 'data_{pref}_wineries.json')),
    ('shochu',  '焼酎・泡盛', '蒸留所',   '#8B5E3C', 'https://shochu.terroirhub.com',
     os.path.join(ROOT, 'terroirHUB 焼酎', 'data', 'data_{pref}_distilleries.json')),
    ('whisky',  'ウイスキー', '蒸留所',   '#2D5F3F', 'https://whisky.terroirhub.com',
     os.path.join(ROOT, 'terroirHUB whisky', 'data', 'data_{pref}_distilleries.json')),
    ('liqueur', 'リキュール・果実酒', '製造者', '#3A7A9E', 'https://liqueur.terroirhub.com',
     os.path.join(ROOT, 'terroirHUB liqueur', 'data', 'data_{pref}_liqueurs.json')),
]

esc = html.escape


def load(path_tmpl, pref):
    path = path_tmpl.format(pref=pref)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def producer_li(domain, gkey, pref, p):
    name = p.get('name', '')
    pid = p.get('id', '')
    area = p.get('area', '') or ''
    founded = p.get('founded', '') or ''
    meta = ' / '.join(x for x in (area, f'{founded}年創業' if founded else '') if x)
    url = f"{domain}/{gkey}/{pref}/{pid}.html"
    meta_html = f'<span class="p-meta">{esc(meta)}</span>' if meta else ''
    return f'<li><a href="{url}">{esc(name)}</a>{meta_html}</li>'


def page_html(pref, pref_name, sections, total, gi_list):
    genre_secs = []
    itemlist = []
    pos = 1
    for gkey, gname, unit, color, domain, items in sections:
        if not items:
            continue
        pref_url = f'{domain}/{gkey}/{pref}/'
        lis = '\n        '.join(producer_li(domain, gkey, pref, p) for p in items[:12])
        more = ''
        if len(items) > 12:
            more = f'<a class="more" href="{pref_url}">残り{len(items)-12}件を含むすべての{unit}を見る →</a>'
        else:
            more = f'<a class="more" href="{pref_url}">{gname}サイトで詳しく見る →</a>'
        genre_secs.append(f'''
  <section class="genre" style="--gc:{color}">
    <div class="g-head">
      <h2>{esc(gname)}</h2>
      <span class="g-count">{len(items)}<small>{esc(unit)}</small></span>
    </div>
    <ul class="p-list">
        {lis}
    </ul>
    {more}
  </section>''')
        itemlist.append({
            "@type": "ListItem", "position": pos,
            "name": f"{pref_name}の{gname}",
            "url": pref_url,
        })
        pos += 1

    gi_html = ''
    if gi_list:
        badges = ''.join(f'<span class="gi">{esc(g)}</span>' for g in sorted(gi_list))
        gi_html = f'<div class="gi-row">{badges}</div>'

    stats = ' ・ '.join(
        f'{gname}{len(items)}' for gkey, gname, unit, color, domain, items in sections if items
    )

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "CollectionPage",
                "name": f"{pref_name}のテロワール — 日本酒・ワイン・焼酎・ウイスキー・リキュール",
                "url": f"https://www.terroirhub.com/terroir/{pref}.html",
                "description": f"{pref_name}の酒の造り手{total}件を全ジャンル横断で紹介。",
                "dateModified": TODAY,
                "isPartOf": {"@type": "WebSite", "name": "Terroir HUB", "url": "https://www.terroirhub.com/"},
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Terroir HUB", "item": "https://www.terroirhub.com/"},
                    {"@type": "ListItem", "position": 2, "name": "テロワール", "item": "https://www.terroirhub.com/terroir/"},
                    {"@type": "ListItem", "position": 3, "name": pref_name, "item": f"https://www.terroirhub.com/terroir/{pref}.html"},
                ],
            },
            {"@type": "ItemList", "itemListElement": itemlist},
        ],
    }, ensure_ascii=False)

    return f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(pref_name)}のテロワール — 酒蔵・ワイナリー・蒸留所{total}件 | Terroir HUB</title>
<meta name="description" content="{esc(pref_name)}の日本酒・ワイン・焼酎・ウイスキー・リキュールの造り手{total}件を1ページで。{esc(stats)}。地域の風土と酒を全ジャンル横断で紹介する日本で唯一のテロワールページ。">
<link rel="canonical" href="https://www.terroirhub.com/terroir/{pref}.html">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Zen+Old+Mincho:wght@400;600&family=Noto+Serif+JP:wght@400;500&display=swap" rel="stylesheet">
<script type="application/ld+json">{jsonld}</script>
<style>
:root{{--bg:#FAFAF7;--surface:#F3F0EA;--text:#1a1816;--muted:#7A7268;--gold:#996E1A;--border:#E5E0D5;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:'Noto Serif JP','Hiragino Mincho ProN',serif;background:var(--bg);color:var(--text);line-height:1.85;}}
.wrap{{max-width:960px;margin:0 auto;padding:0 22px;}}
header{{border-bottom:1px solid var(--border);}}
.hd{{display:flex;align-items:center;justify-content:space-between;padding:14px 0;}}
.hd a.logo{{font-family:'Zen Old Mincho',serif;font-size:17px;color:var(--text);text-decoration:none;letter-spacing:.1em;}}
.hd a.logo em{{color:var(--gold);font-style:normal;}}
.hd nav a{{font-size:13px;color:var(--muted);text-decoration:none;margin-left:16px;}}
.hero{{padding:52px 0 36px;text-align:center;}}
.hero .crumb{{font-size:12px;color:var(--muted);letter-spacing:.15em;margin-bottom:14px;}}
.hero .crumb a{{color:var(--muted);text-decoration:none;}}
.hero h1{{font-family:'Zen Old Mincho',serif;font-size:30px;font-weight:600;letter-spacing:.12em;}}
.hero .total{{margin-top:12px;font-size:14px;color:var(--muted);}}
.hero .total b{{color:var(--gold);font-size:20px;font-family:'Zen Old Mincho',serif;}}
.gi-row{{margin-top:16px;}}
.gi{{display:inline-block;font-size:11.5px;letter-spacing:.08em;border:1px solid var(--gold);color:var(--gold);border-radius:3px;padding:3px 10px;margin:3px;}}
.genre{{background:#fff;border:1px solid var(--border);border-left:4px solid var(--gc);border-radius:8px;padding:26px 28px;margin:22px 0;}}
.g-head{{display:flex;align-items:baseline;justify-content:space-between;border-bottom:1px solid var(--border);padding-bottom:12px;margin-bottom:16px;}}
.g-head h2{{font-family:'Zen Old Mincho',serif;font-size:19px;letter-spacing:.1em;color:var(--gc);font-weight:600;}}
.g-count{{font-family:'Zen Old Mincho',serif;font-size:24px;color:var(--text);}}
.g-count small{{font-size:12px;color:var(--muted);margin-left:3px;}}
.p-list{{list-style:none;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px 22px;}}
.p-list li{{font-size:14px;border-bottom:1px dashed var(--border);padding:7px 2px;display:flex;justify-content:space-between;gap:10px;align-items:baseline;}}
.p-list a{{color:var(--text);text-decoration:none;}}
.p-list a:hover{{color:var(--gc);}}
.p-meta{{font-size:11px;color:var(--muted);white-space:nowrap;}}
.more{{display:inline-block;margin-top:16px;font-size:13px;color:var(--gc);text-decoration:none;letter-spacing:.05em;}}
.cross{{background:var(--surface);border-radius:8px;padding:22px 26px;margin:34px 0;font-size:13.5px;color:var(--muted);}}
footer{{border-top:1px solid var(--border);margin-top:52px;padding:26px 0;text-align:center;font-size:12px;color:var(--muted);}}
footer a{{color:var(--muted);}}
@media(max-width:600px){{.hero h1{{font-size:23px;}}.genre{{padding:20px 18px;}}}}
</style>
</head>
<body>
<header><div class="wrap hd">
  <a class="logo" href="/">Terroir <em>HUB</em></a>
  <nav><a href="/terroir/">全国のテロワール</a><a href="/">総合トップ</a></nav>
</div></header>

<div class="wrap">
  <div class="hero">
    <div class="crumb"><a href="/">Terroir HUB</a> ／ <a href="/terroir/">テロワール</a> ／ {esc(pref_name)}</div>
    <h1>{esc(pref_name)}のテロワール</h1>
    <p class="total">日本酒・ワイン・焼酎・ウイスキー・リキュールの造り手 <b>{total}</b> 件</p>
    {gi_html}
  </div>
{''.join(genre_secs)}
  <div class="cross">
    Terroir HUB は日本全国の酒蔵・ワイナリー・蒸留所を5ジャンル横断で収録する総合データベースです。
    各造り手の詳細ページでは銘柄・見学情報・購入リンクを掲載しています。データは公式情報に基づき、最終更新は {TODAY} です。
  </div>
</div>

<footer><div class="wrap">
  <a href="https://www.terroirhub.com/">Terroir HUB</a> — 日本の酒テロワール総合データベース
</div></footer>
</body>
</html>
'''


def index_html(rows, grand_total):
    cards = ''
    for pref, pref_name, total, per in rows:
        if total == 0:
            continue
        chips = ' '.join(f'<span>{gname}{n}</span>' for gname, n in per if n)
        cards += f'''
    <a class="card" href="/terroir/{pref}.html">
      <span class="c-name">{esc(pref_name)}</span>
      <span class="c-total">{total}<small>件</small></span>
      <span class="c-chips">{chips}</span>
    </a>'''

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "全国のテロワール — 都道府県別・全ジャンル横断",
        "url": "https://www.terroirhub.com/terroir/",
        "description": f"日本全国{grand_total}件の酒蔵・ワイナリー・蒸留所を47都道府県×5ジャンルで横断検索。",
        "dateModified": TODAY,
    }, ensure_ascii=False)

    return f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>全国のテロワール — 都道府県別に日本酒・ワイン・焼酎・ウイスキーを横断 | Terroir HUB</title>
<meta name="description" content="日本全国{grand_total}件の酒蔵・ワイナリー・蒸留所・リキュール製造者を、47都道府県×5ジャンルで横断できる日本で唯一のテロワール一覧。">
<link rel="canonical" href="https://www.terroirhub.com/terroir/">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Zen+Old+Mincho:wght@400;600&family=Noto+Serif+JP:wght@400;500&display=swap" rel="stylesheet">
<script type="application/ld+json">{jsonld}</script>
<style>
:root{{--bg:#FAFAF7;--surface:#F3F0EA;--text:#1a1816;--muted:#7A7268;--gold:#996E1A;--border:#E5E0D5;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:'Noto Serif JP','Hiragino Mincho ProN',serif;background:var(--bg);color:var(--text);line-height:1.8;}}
.wrap{{max-width:1040px;margin:0 auto;padding:0 22px;}}
header{{border-bottom:1px solid var(--border);}}
.hd{{display:flex;align-items:center;justify-content:space-between;padding:14px 0;}}
.hd a.logo{{font-family:'Zen Old Mincho',serif;font-size:17px;color:var(--text);text-decoration:none;letter-spacing:.1em;}}
.hd a.logo em{{color:var(--gold);font-style:normal;}}
.hd nav a{{font-size:13px;color:var(--muted);text-decoration:none;margin-left:16px;}}
.hero{{padding:52px 0 30px;text-align:center;}}
.hero h1{{font-family:'Zen Old Mincho',serif;font-size:28px;font-weight:600;letter-spacing:.12em;}}
.hero p{{margin-top:12px;font-size:14px;color:var(--muted);}}
.hero b{{color:var(--gold);}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:14px;padding:26px 0 10px;}}
.card{{background:#fff;border:1px solid var(--border);border-radius:8px;padding:18px 20px;text-decoration:none;color:var(--text);display:flex;flex-direction:column;gap:6px;transition:border-color .2s,transform .15s;}}
.card:hover{{border-color:var(--gold);transform:translateY(-2px);}}
.c-name{{font-family:'Zen Old Mincho',serif;font-size:16px;letter-spacing:.1em;}}
.c-total{{font-family:'Zen Old Mincho',serif;font-size:22px;color:var(--gold);}}
.c-total small{{font-size:11px;color:var(--muted);margin-left:2px;}}
.c-chips{{font-size:10.5px;color:var(--muted);line-height:1.7;}}
.c-chips span{{margin-right:7px;white-space:nowrap;}}
footer{{border-top:1px solid var(--border);margin-top:48px;padding:26px 0;text-align:center;font-size:12px;color:var(--muted);}}
footer a{{color:var(--muted);}}
</style>
</head>
<body>
<header><div class="wrap hd">
  <a class="logo" href="/">Terroir <em>HUB</em></a>
  <nav><a href="/">総合トップ</a></nav>
</div></header>

<div class="wrap">
  <div class="hero">
    <h1>全国のテロワール</h1>
    <p>日本全国 <b>{grand_total}</b> 件の造り手を、都道府県 × 5ジャンルで横断。<br>その土地の酒がぜんぶ分かる、日本で唯一の一覧です。</p>
  </div>
  <div class="grid">{cards}
  </div>
</div>

<footer><div class="wrap">
  <a href="https://www.terroirhub.com/">Terroir HUB</a> — 日本の酒テロワール総合データベース
</div></footer>
</body>
</html>
'''


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    grand_total = 0
    for pref, pref_name in PREFS:
        sections = []
        gi_list = set()
        total = 0
        for gkey, gname, unit, color, domain, tmpl in GENRES:
            items = load(tmpl, pref)
            items = [p for p in items if p.get('id') and p.get('name')]
            sections.append((gkey, gname, unit, color, domain, items))
            total += len(items)
            for p in items:
                if p.get('gi'):
                    gi_list.add(p['gi'])
        grand_total += total
        if total:
            with open(os.path.join(OUT, f'{pref}.html'), 'w', encoding='utf-8') as f:
                f.write(page_html(pref, pref_name, sections, total, gi_list))
        rows.append((pref, pref_name, total, [(g[1], len(g[5])) for g in sections]))

    with open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_html(rows, grand_total))

    print(f'terroir pages: {sum(1 for r in rows if r[2])}県 + index / 総計{grand_total}件')
    for pref, name, total, per in rows:
        if total == 0:
            print(f'  !! {name}: 0件')


if __name__ == '__main__':
    main()
