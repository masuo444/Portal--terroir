#!/usr/bin/env python3
"""
自治体別ふるさと納税ページを生成する。
  /furusato/<県slug>/<自治体slug>/index.html

目的は2つ:
  1) 「都城市 ふるさと納税 焼酎」のような自治体×お酒の検索需要を取る（アフィリ収益）
  2) 自治体・観光協会への提案時に「御市のページはこれです」と現物を示せる営業資産にする

データ源:
  - 返礼品: 各ジャンルの rakuten_items.json（【ふるさと納税】を含む商品のみ）
    楽天の店舗コード f<JISコード6桁>-<ローマ字> から自治体を同定
  - 自治体名: data/furusato_municipalities.json（楽天店舗ページのtitle由来・出典あり）
  - 生産者: 各ジャンルのデータJSONの住所が「県名＋自治体名」で始まるもの

情報がないものは推測で埋めない（RULES.md準拠）。
使い方: python3 scripts/generate_furusato_municipality.py [--limit N]
"""
import json, glob, os, re, sys, html, datetime, urllib.parse

TODAY = datetime.date.today().isoformat()
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
DOMAIN = "www.terroirhub.com"
MUNI_JSON = os.path.join(BASE, "data", "furusato_municipalities.json")
OUTROOT = os.path.join(BASE, "furusato")

GENRES = [
    dict(key="sake", name="日本酒", unit="酒蔵", color="#B8452A", site="https://sake.terroirhub.com",
         path="sake", items="TerriorHUB　sake/sake/rakuten_items.json",
         data="TerriorHUB　sake/data_*_breweries.json", suffix="_breweries.json"),
    dict(key="wine", name="日本ワイン", unit="ワイナリー", color="#722F37", site="https://wine.terroirhub.com",
         path="wine", items="terroirHUB wine/wine/rakuten_items.json",
         data="terroirHUB wine/data/data_*_wineries.json", suffix="_wineries.json"),
    dict(key="shochu", name="焼酎・泡盛", unit="蔵", color="#8B5E3C", site="https://shochu.terroirhub.com",
         path="shochu", items="terroirHUB 焼酎/shochu/rakuten_items.json",
         data="terroirHUB 焼酎/data/data_*_distilleries.json", suffix="_distilleries.json"),
    dict(key="whisky", name="ウイスキー", unit="蒸溜所", color="#2D5F3F", site="https://whisky.terroirhub.com",
         path="whisky", items="terroirHUB whisky/whisky/rakuten_items.json",
         data="terroirHUB whisky/data/data_*_distilleries.json", suffix="_distilleries.json"),
    dict(key="liqueur", name="梅酒・リキュール", unit="メーカー", color="#4A8BAE", site="https://liqueur.terroirhub.com",
         path="liqueur", items="terroirHUB liqueur/liqueur/rakuten_items.json",
         data="terroirHUB liqueur/data/data_*_liqueurs.json", suffix="_liqueurs.json"),
]

SHOP_RE = re.compile(r'item\.rakuten\.co\.jp/(f\d{6}-[a-z0-9_\-]+)/')
# 区切りは寄付者の控除上限の実態に合わせる（1万円台に固まりやすいのを解きほぐす）
BUDGET_BANDS = [('1万円以下', 0, 10000), ('1万〜2.5万円', 10000, 25000),
                ('2.5万〜5万円', 25000, 50000), ('5万円以上', 50000, 10 ** 9)]


def esc(s):
    return html.escape(str(s or ""), quote=True)


def clean_name(nm):
    s = re.sub(r'^[【\[]?\s*ふるさと納税\s*[】\]]?\s*', '', nm or '')
    s = re.sub(r'\s*(送料無料|人気|数量限定|期間限定|訳あり)\s*', ' ', s)
    return s.strip() or nm


BAND_KEYS = [('u10', 0, 10000), ('10-25', 10000, 25000), ('25-50', 25000, 50000),
             ('o50', 50000, 10 ** 9)]


def band_key_of(price):
    if not price:
        return 'unknown'
    for key, lo, hi in BAND_KEYS:
        if (lo == 0 and price <= hi) or (lo < price <= hi):
            return key
    return 'unknown'


def band_of(price):
    if not price:
        return ''
    for label, lo, hi in BUDGET_BANDS:
        if (lo == 0 and price <= hi) or (lo < price <= hi):
            return label
    return ''


def load_items():
    """{shop_code: [item, ...]} — itemにgenre情報を付ける"""
    by_shop = {}
    for g in GENRES:
        p = os.path.join(ROOT, g["items"])
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        for bid, grp in d.items():
            for it in grp.get("items", []):
                if "ふるさと納税" not in it.get("name", ""):
                    continue
                u = urllib.parse.unquote(it.get("url", "") or "")
                m = SHOP_RE.search(u)
                if not m:
                    continue
                by_shop.setdefault(m.group(1), []).append({**it, "genre": g["key"], "bid": bid})
    return by_shop


def load_producers():
    """{(県名, 市区町村名): [producer]} 住所の先頭一致で自治体に割り当てる"""
    out = {}
    for g in GENRES:
        for jf in glob.glob(os.path.join(ROOT, g["data"])):
            pref_slug = os.path.basename(jf).replace("data_", "").replace(g["suffix"], "")
            try:
                rows = json.load(open(jf, encoding="utf-8"))
            except Exception:
                continue
            for b in rows:
                addr = (b.get("address") or "").strip()
                if not addr or not b.get("id"):
                    continue
                out.setdefault(addr, []).append({
                    "name": b.get("name", ""), "id": b["id"], "pref_slug": pref_slug,
                    "genre": g["key"], "addr": addr,
                    "url": f'{g["site"]}/{g["path"]}/{pref_slug}/{b["id"]}.html',
                })
    return out


def producers_in(all_producers, pref, city):
    """住所が『県名＋市区町村名』で始まる生産者（推測しない・完全な前方一致のみ）"""
    key = pref + city
    hits = []
    for addr, rows in all_producers.items():
        norm = addr.replace(" ", "").replace("　", "")
        if norm.startswith(key):
            hits.extend(rows)
    hits.sort(key=lambda r: (r["genre"], r["name"]))
    return hits


NAV = """<nav class="nav">
  <a href="/" class="nav-logo">Terroir HUB</a>
  <div class="nav-links">
    <a class="nav-link" href="/furusato/">ふるさと納税</a>
    <a class="nav-link" href="/terroir/">テロワール</a>
    <a class="nav-link" href="https://sake.terroirhub.com/">SAKE</a>
    <a class="nav-link" href="https://wine.terroirhub.com/">WINE</a>
    <a class="nav-link" href="https://shochu.terroirhub.com/">SHOCHU</a>
  </div>
</nav>"""

CSS = """*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#FAFAF7;--surface:#F3F0EA;--border:rgba(0,0,0,0.08);--text:#1a1816;--muted:rgba(26,24,22,0.62);--gold:#996E1A;--fd:'Shippori Mincho',serif;--fb:'Noto Sans JP',sans-serif;--fn:'Inter',sans-serif}
html{scroll-behavior:smooth;-webkit-font-smoothing:antialiased}
body{background:var(--bg);color:var(--text);font-family:var(--fb);line-height:1.8;overflow-x:hidden}
a{color:inherit;text-decoration:none}
img{display:block;max-width:100%}
.nav{position:fixed;top:0;left:0;right:0;z-index:100;height:64px;display:flex;align-items:center;justify-content:space-between;padding:0 clamp(1.2rem,5vw,4rem);background:rgba(250,250,247,0.92);backdrop-filter:blur(20px);border-bottom:1px solid var(--border)}
.nav-logo{font-family:var(--fd);font-size:1.2rem;font-weight:700;letter-spacing:0.08em}
.nav-links{display:none;gap:1.6rem;align-items:center}
@media(min-width:980px){.nav-links{display:flex}}
.nav-link{font-size:0.72rem;font-weight:500;letter-spacing:0.16em;text-transform:uppercase;color:var(--muted)}
.crumb{margin-top:64px;padding:0.9rem clamp(1.4rem,5vw,5rem);font-size:0.76rem;color:var(--muted);background:#fff;border-bottom:1px solid var(--border)}
.crumb a:hover{color:var(--gold)}
.hero{padding:clamp(2.6rem,6vw,4.4rem) clamp(1.4rem,5vw,5rem) clamp(2rem,4vw,2.8rem);background:#fff;border-bottom:1px solid var(--border)}
.hero-inner{max-width:1080px;margin:0 auto}
.eyebrow{font-family:var(--fn);font-size:0.62rem;font-weight:600;letter-spacing:0.32em;text-transform:uppercase;color:var(--gold);margin-bottom:1rem}
.hero h1{font-family:var(--fd);font-size:clamp(1.7rem,4.2vw,2.7rem);font-weight:700;line-height:1.38;margin-bottom:1.1rem}
.hero p{font-size:clamp(0.94rem,1.3vw,1.04rem);max-width:720px;line-height:2;color:var(--text)}
.hstats{display:flex;gap:2.2rem;margin-top:1.8rem;flex-wrap:wrap;padding-top:1.3rem;border-top:1px solid var(--border)}
.hstat-n{font-family:var(--fn);font-size:clamp(1.4rem,2.2vw,1.8rem);font-weight:600;line-height:1}
.hstat-l{font-size:0.8rem;color:var(--muted);margin-top:4px}
.wrap{max-width:1180px;margin:0 auto;padding:clamp(2.2rem,4vw,3.2rem) clamp(1.4rem,5vw,5rem) 0}
.sec-head{font-family:var(--fd);font-size:clamp(1.2rem,2.2vw,1.55rem);font-weight:700;margin-bottom:0.5rem}
.sec-lead{font-size:0.88rem;color:var(--muted);line-height:1.85;margin-bottom:1.4rem;max-width:760px}
.pgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem}
@media(max-width:900px){.pgrid{grid-template-columns:repeat(2,1fr)}}
.pcard{background:#fff;border:1px solid var(--border);display:flex;flex-direction:column;transition:box-shadow .25s,transform .25s}
.pcard:hover{box-shadow:0 12px 30px rgba(40,30,20,.12);transform:translateY(-3px)}
.pcard-img{aspect-ratio:1/1;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden}
.pcard-img img{width:100%;height:100%;object-fit:contain;padding:12px}
.pcard-g{font-family:var(--fn);font-size:0.6rem;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;padding:9px 13px 0}
.pcard-name{font-size:0.82rem;line-height:1.55;padding:5px 13px 0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;flex:1}
.pcard-price{font-family:var(--fd);font-size:0.8rem;color:#7a2a18;padding:8px 13px 0}
.pcard-price b{font-family:var(--fn);font-size:1.02rem;font-weight:600}
.pcard-buy{font-family:var(--fn);font-size:0.66rem;font-weight:600;letter-spacing:0.06em;color:#fff;background:#BF0000;text-align:center;padding:8px 0;margin:11px 13px 13px;border-radius:3px}
.prod-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:0.8rem}
@media(max-width:860px){.prod-grid{grid-template-columns:1fr}}
.prod{background:#fff;border:1px solid var(--border);padding:1rem 1.1rem;display:block}
.prod:hover{box-shadow:0 8px 22px rgba(40,30,20,.10)}
.prod-g{font-family:var(--fn);font-size:0.6rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase}
.prod-n{font-family:var(--fd);font-size:1rem;font-weight:600;margin:4px 0 3px}
.prod-a{font-size:0.76rem;color:var(--muted);line-height:1.6}
#thub-deadline{position:sticky;top:64px;z-index:90;background:#5E410C;color:#fff}
.dl-in{max-width:1180px;margin:0 auto;padding:.7rem clamp(1.4rem,5vw,5rem);display:flex;align-items:center;gap:1rem;flex-wrap:wrap}
.dl-t{flex:1;min-width:220px;font-size:.84rem;line-height:1.6}
.dl-t b{font-family:var(--fd);font-size:.95rem;margin-right:.6rem}
.dl-t span{opacity:.8;font-size:.78rem}
.dl-a{font-family:var(--fn);font-size:.75rem;font-weight:600;letter-spacing:.06em;background:#fff;color:#5E410C;padding:.5rem 1.1rem;white-space:nowrap}
.dl-x{background:none;border:none;color:#fff;font-size:1.1rem;cursor:pointer;opacity:.7;padding:0 .2rem}
.dl-x:hover{opacity:1}
.bandrow{display:flex;gap:0.6rem;flex-wrap:wrap;align-items:center;margin-bottom:1.2rem}
.bandlbl{font-family:var(--fn);font-size:0.68rem;letter-spacing:0.14em;color:var(--muted);text-transform:uppercase;margin-right:0.2rem}
.bandpill{font-family:var(--fn);font-size:0.76rem;border:1px solid var(--border);background:#fff;padding:7px 15px;color:var(--muted);cursor:pointer;transition:border-color .2s,color .2s}
.bandpill:hover{border-color:var(--gold);color:var(--text)}
.bandpill.on{border-color:var(--gold);color:var(--text);background:#fff;box-shadow:inset 0 -2px 0 var(--gold)}
.bandpill b{font-family:var(--fn);color:var(--text);font-weight:600}
.pcard[hidden]{display:none}
.note{max-width:1180px;margin:clamp(2.4rem,4vw,3.4rem) auto 0;padding:0 clamp(1.4rem,5vw,5rem)}
.note-in{background:var(--surface);border:1px solid var(--border);padding:1.3rem 1.5rem;font-size:0.82rem;color:var(--muted);line-height:1.9}
.linkrow{display:flex;gap:0.7rem;flex-wrap:wrap;margin-top:1rem}
.linkrow a{font-family:var(--fn);font-size:0.76rem;border:1px solid var(--border);background:#fff;padding:7px 15px}
.linkrow a:hover{border-color:var(--gold);color:var(--gold)}
.foot{margin-top:clamp(3rem,6vw,4.5rem);padding:2.4rem clamp(1.4rem,5vw,5rem);border-top:1px solid var(--border);background:#fff;font-size:0.78rem;color:var(--muted)}
.foot-logo{font-family:var(--fd);font-size:1.05rem;color:var(--text);margin-bottom:0.5rem}"""


def card(it, gmap, muni_slug="", jis=""):
    g = gmap[it["genre"]]
    price = it.get("price")
    ph = f'<div class="pcard-price">寄付 <b>{price:,}</b>円</div>' if price else ''
    band_key = band_key_of(it.get("price"))
    return (f'<a class="pcard" data-band="{band_key}" href="{esc(it["url"])}" target="_blank" rel="nofollow sponsored noopener" '
            f'onclick="if(window.gtag)gtag(\'event\',\'furusato_click\','
            f'{{genre:\'{g["key"]}\',muni:\'{muni_slug}\',jis:\'{jis}\'}});">'
            f'<div class="pcard-img"><img src="{esc(it.get("image",""))}" alt="{esc(clean_name(it["name"]))}" loading="lazy"></div>'
            f'<div class="pcard-g" style="color:{g["color"]}">{esc(g["name"])}</div>'
            f'<div class="pcard-name">{esc(clean_name(it["name"]))}</div>{ph}'
            f'<div class="pcard-buy">楽天ふるさと納税で寄付 →</div></a>')


def build_page(m, items, producers, gmap):
    pref, city = m["pref"], m["city"]
    full = f"{pref}{city}"
    url = f'https://{DOMAIN}/furusato/{m["pref_slug"]}/{m["slug"]}/'
    genres_here = []
    for g in GENRES:
        n = sum(1 for it in items if it["genre"] == g["key"])
        if n:
            genres_here.append((g, n))
    gnames = "・".join(g["name"] for g, _ in genres_here)
    title = f"{full}のふるさと納税で選ぶお酒 — {gnames}の返礼品{len(items)}件 | Terroir HUB"
    desc = (f"{full}のふるさと納税返礼品から、{gnames}を{len(items)}件まとめました。"
            f"寄付金額から選べます。{full}の造り手の情報もあわせて掲載しています。")

    bands = {}
    for it in items:
        k = band_key_of(it.get("price"))
        if k != 'unknown':
            bands[k] = bands.get(k, 0) + 1
    pills = ''.join(
        f'<button class="bandpill" data-filter="{k}">{esc(lb)} <b>{bands[k]}</b>件</button>'
        for (lb, _lo, _hi), (k, _a, _b) in zip(BUDGET_BANDS, BAND_KEYS) if bands.get(k))
    bandrow = (f'<div class="bandrow"><span class="bandlbl">寄付金額で絞る</span>'
               f'<button class="bandpill on" data-filter="all">すべて <b>{len(items)}</b>件</button>'
               f'{pills}</div>') if pills else ''

    items_sorted = sorted(items, key=lambda x: (x.get("price") or 10 ** 9, x["name"]))
    cards = "".join(card(it, gmap, m["slug"], m["jis"]) for it in items_sorted)

    prod_html = ""
    if producers:
        rows = "".join(
            f'<a class="prod" href="{esc(p["url"])}">'
            f'<div class="prod-g" style="color:{gmap[p["genre"]]["color"]}">{esc(gmap[p["genre"]]["name"])}</div>'
            f'<div class="prod-n">{esc(p["name"])}</div>'
            f'<div class="prod-a">{esc(p["addr"])}</div></a>' for p in producers)
        prod_html = f"""<section class="wrap">
  <h2 class="sec-head">{esc(full)}の造り手</h2>
  <p class="sec-lead">Terroir HUBに収録している{esc(full)}の造り手です。各ページに所在地・公式サイト・代表銘柄を掲載しています。</p>
  <div class="prod-grid">{rows}</div>
</section>"""

    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Terroir HUB", "item": f"https://{DOMAIN}/"},
                {"@type": "ListItem", "position": 2, "name": "ふるさと納税", "item": f"https://{DOMAIN}/furusato/"},
                {"@type": "ListItem", "position": 3, "name": pref, "item": f'https://{DOMAIN}/furusato/{m["pref_slug"]}/'},
                {"@type": "ListItem", "position": 4, "name": city, "item": url}]},
            {"@type": "CollectionPage", "name": title, "description": desc, "url": url,
             "about": {"@type": "AdministrativeArea", "name": full}},
            {"@type": "ItemList", "name": f"{full}のふるさと納税返礼品（お酒）",
             "itemListElement": [
                 {"@type": "ListItem", "position": i + 1, "name": clean_name(it["name"]),
                  "image": it.get("image", ""), "url": it["url"],
                  **({"offers": {"@type": "Offer", "price": it["price"], "priceCurrency": "JPY"}} if it.get("price") else {})}
                 for i, it in enumerate(items_sorted[:30])]},
        ]}

    gl = "".join(
        f'<a href="{g["site"]}/{g["path"]}/furusato/{m["pref_slug"]}.html">{esc(pref)}の{esc(g["name"])}の返礼品</a>'
        for g, _n in genres_here)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="https://sake.terroirhub.com/img/hero-top.png">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@500;600;700&family=Noto+Sans+JP:wght@300;400;500;700&family=Inter:wght@500;600&display=swap" rel="stylesheet">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>{CSS}</style>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-NG35V7K1JH"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-NG35V7K1JH');</script>
</head>
<body>
{NAV}
<div id="thub-deadline" hidden></div>
<script>
(function(){{
  // 12月1日〜翌1月10日だけ、年末の案内を出す。閉じたら同じシーズン中は出さない。
  var n=new Date(), m=n.getMonth()+1, d=n.getDate(), y=n.getFullYear();
  var inDec = (m===12), inJan = (m===1 && d<=10);
  if(!inDec && !inJan) return;
  var season = inDec ? y : y-1;
  try{{ if(localStorage.getItem('thub-dl-'+season)==='1') return; }}catch(e){{}}
  var msg, sub;
  if(inDec){{
    var left = 31-d+1;
    msg = '年内の寄付は12月31日まで';
    sub = (left<=7? 'あと'+left+'日。' : '') + '締切はサイトと決済方法で異なります';
  }} else {{
    msg = 'ワンストップ特例の申請はお早めに';
    sub = '期限は自治体ごとに定められています';
  }}
  var el=document.getElementById('thub-deadline');
  el.hidden=false;
  el.innerHTML='<div class="dl-in"><div class="dl-t"><b>'+msg+'</b><span>'+sub+'</span></div>'
    +'<a class="dl-a" href="/furusato/deadline/">期限と手続きを確認する →</a>'
    +'<button class="dl-x" aria-label="閉じる">×</button></div>';
  el.querySelector('.dl-x').addEventListener('click',function(){{
    el.hidden=true;
    try{{ localStorage.setItem('thub-dl-'+season,'1'); }}catch(e){{}}
  }});
  if(window.gtag)gtag('event','deadline_banner_shown',{{month:m}});
}})();
</script>
<div class="crumb"><a href="/">ホーム</a> › <a href="/furusato/">ふるさと納税</a> › <a href="/furusato/{m["pref_slug"]}/">{esc(pref)}</a> › {esc(city)}</div>
<header class="hero"><div class="hero-inner">
  <div class="eyebrow">Furusato Tax · {esc(pref)}</div>
  <h1>{esc(full)}のふるさと納税で選ぶお酒</h1>
  <p>{esc(full)}が提供するふるさと納税返礼品のうち、{esc(gnames)}を{len(items)}件掲載しています。寄付金額から選べます。掲載は楽天ふるさと納税の返礼品情報にもとづきます。</p>
  <div class="hstats">
    <div><div class="hstat-n">{len(items)}</div><div class="hstat-l">掲載返礼品</div></div>
    <div><div class="hstat-n">{len(genres_here)}</div><div class="hstat-l">ジャンル</div></div>
    <div><div class="hstat-n">{len(producers)}</div><div class="hstat-l">収録している造り手</div></div>
  </div>
</div></header>
<section class="wrap">
  <h2 class="sec-head">返礼品一覧</h2>
  <p class="sec-lead">ふるさと納税は、自己負担2,000円を除いた分が所得税・住民税から控除されます。
  控除される上限額は年収と家族構成で変わるため、<b>ご自身の上限を確かめてから、その範囲で選ぶ</b>のが無駄がありません。
  <a href="https://www.soumu.go.jp/main_sosiki/jichi_zeisei/czaisei/czaisei_seido/furusato/mechanism/deduction.html" target="_blank" rel="noopener">総務省の説明ページ</a>に
  <a href="https://www.soumu.go.jp/main_content/000408218.xlsx" target="_blank" rel="noopener">控除額の計算シミュレーション（Excel）</a>があります。</p>
  {bandrow}
  <div class="pgrid">{cards}</div>
</section>
{prod_html}
<div class="note"><div class="note-in">
  <p>掲載している返礼品は楽天ふるさと納税の情報にもとづきます（最終更新 {TODAY}）。寄付金額・在庫・提供事業者は変更されることがあるため、寄付前に各返礼品ページで最新の情報をご確認ください。</p>
  <p>控除の上限額は年収や家族構成によって異なります。各ふるさと納税サイトのシミュレーターでご確認のうえ寄付してください。</p>
  <p>当ページには楽天アフィリエイトのリンクを含みます。</p>
  <div class="linkrow">{gl}<a href="/furusato/">お酒のふるさと納税トップ</a><a href="/terroir/{m["pref_slug"]}.html">{esc(pref)}のテロワール</a></div>
</div></div>
<footer class="foot"><div class="foot-logo">Terroir HUB</div>
  <p>日本の酒と土地を、正確な一次情報で。</p></footer>
<script>
(function(){{
  var pills=document.querySelectorAll('.bandpill');
  var cards=document.querySelectorAll('.pcard');
  Array.prototype.forEach.call(pills,function(p){{
    p.addEventListener('click',function(){{
      var f=p.getAttribute('data-filter');
      Array.prototype.forEach.call(pills,function(q){{q.classList.toggle('on',q===p);}});
      Array.prototype.forEach.call(cards,function(c){{
        c.hidden = (f!=='all' && c.getAttribute('data-band')!==f);
      }});
      if(window.gtag)gtag('event','furusato_filter',{{band:f}});
    }});
  }});
}})();
</script>
</body>
</html>"""


def render_pref_index(pref, pref_slug, rows, gmap):
    """/furusato/<県>/ — その県の自治体一覧（自治体ページの孤立を防ぐ）"""
    url = f'https://{DOMAIN}/furusato/{pref_slug}/'
    total = sum(r["items"] for r in rows)
    title = f'{pref}のふるさと納税で選ぶお酒 — {len(rows)}自治体・返礼品{total}件 | Terroir HUB'
    desc = (f'{pref}の{len(rows)}自治体が提供するふるさと納税返礼品から、日本酒・ワイン・焼酎・'
            f'ウイスキー・リキュールを{total}件まとめました。自治体ごとに寄付金額から選べます。')
    cards = "".join(
        f'<a class="prod" href="/furusato/{pref_slug}/{esc(r["slug"])}/">'
        f'<div class="prod-g" style="color:var(--gold)">{esc(r["city"])}</div>'
        f'<div class="prod-n">返礼品 {r["items"]}件</div>'
        f'<div class="prod-a">' + (f'収録している造り手 {r["producers"]}件' if r["producers"] else '&nbsp;') +
        f'</div></a>' for r in rows)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Terroir HUB", "item": f"https://{DOMAIN}/"},
            {"@type": "ListItem", "position": 2, "name": "ふるさと納税", "item": f"https://{DOMAIN}/furusato/"},
            {"@type": "ListItem", "position": 3, "name": pref, "item": url}]},
        {"@type": "CollectionPage", "name": title, "description": desc, "url": url,
         "about": {"@type": "AdministrativeArea", "name": pref}}]}
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="https://sake.terroirhub.com/img/hero-top.png">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@500;600;700&family=Noto+Sans+JP:wght@300;400;500;700&family=Inter:wght@500;600&display=swap" rel="stylesheet">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>{CSS}</style>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-NG35V7K1JH"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-NG35V7K1JH');</script>
</head>
<body>
{NAV}
<div id="thub-deadline" hidden></div>
<script>
(function(){{
  // 12月1日〜翌1月10日だけ、年末の案内を出す。閉じたら同じシーズン中は出さない。
  var n=new Date(), m=n.getMonth()+1, d=n.getDate(), y=n.getFullYear();
  var inDec = (m===12), inJan = (m===1 && d<=10);
  if(!inDec && !inJan) return;
  var season = inDec ? y : y-1;
  try{{ if(localStorage.getItem('thub-dl-'+season)==='1') return; }}catch(e){{}}
  var msg, sub;
  if(inDec){{
    var left = 31-d+1;
    msg = '年内の寄付は12月31日まで';
    sub = (left<=7? 'あと'+left+'日。' : '') + '締切はサイトと決済方法で異なります';
  }} else {{
    msg = 'ワンストップ特例の申請はお早めに';
    sub = '期限は自治体ごとに定められています';
  }}
  var el=document.getElementById('thub-deadline');
  el.hidden=false;
  el.innerHTML='<div class="dl-in"><div class="dl-t"><b>'+msg+'</b><span>'+sub+'</span></div>'
    +'<a class="dl-a" href="/furusato/deadline/">期限と手続きを確認する →</a>'
    +'<button class="dl-x" aria-label="閉じる">×</button></div>';
  el.querySelector('.dl-x').addEventListener('click',function(){{
    el.hidden=true;
    try{{ localStorage.setItem('thub-dl-'+season,'1'); }}catch(e){{}}
  }});
  if(window.gtag)gtag('event','deadline_banner_shown',{{month:m}});
}})();
</script>
<div class="crumb"><a href="/">ホーム</a> › <a href="/furusato/">ふるさと納税</a> › {esc(pref)}</div>
<header class="hero"><div class="hero-inner">
  <div class="eyebrow">Furusato Tax</div>
  <h1>{esc(pref)}のふるさと納税で選ぶお酒</h1>
  <p>{esc(pref)}の{len(rows)}自治体が提供する返礼品から、Terroir HUBに収録しているお酒を{total}件掲載しています。自治体ごとに寄付金額から選べます。</p>
  <div class="hstats">
    <div><div class="hstat-n">{len(rows)}</div><div class="hstat-l">自治体</div></div>
    <div><div class="hstat-n">{total}</div><div class="hstat-l">掲載返礼品</div></div>
  </div>
</div></header>
<section class="wrap">
  <h2 class="sec-head">自治体から選ぶ</h2>
  <p class="sec-lead">返礼品の掲載数が多い順です。</p>
  <div class="prod-grid">{cards}</div>
</section>
<div class="note"><div class="note-in">
  <p>掲載は楽天ふるさと納税の返礼品情報にもとづきます（最終更新 {TODAY}）。寄付前に各返礼品ページで最新の情報をご確認ください。</p>
  <div class="linkrow"><a href="/furusato/">お酒のふるさと納税トップ</a><a href="/terroir/{pref_slug}.html">{esc(pref)}のテロワール</a></div>
</div></div>
<footer class="foot"><div class="foot-logo">Terroir HUB</div>
  <p>日本の酒と土地を、正確な一次情報で。</p></footer>
</body>
</html>"""


# 各ジャンルのリポジトリに「生産者→自治体ページ」の対応表を書き出す。
# 蔵ページからふるさと納税ページへ内部リンクを張るために使う（リポジトリは独立してデプロイされるため、
# ポータルのファイルを直接読ませず、各リポジトリに実体を配る）。
LINK_OUT = {
    "sake": "TerriorHUB　sake/sake/furusato_links.json",
    "wine": "terroirHUB wine/wine/furusato_links.json",
    "shochu": "terroirHUB 焼酎/shochu/furusato_links.json",
    "whisky": "terroirHUB whisky/whisky/furusato_links.json",
    "liqueur": "terroirHUB liqueur/liqueur/furusato_links.json",
}


def write_producer_links(munis, by_shop):
    """{genre: {rakuten_items.jsonのキー: {city, pref, url, count}}} を各リポジトリへ"""
    out = {g["key"]: {} for g in GENRES}
    by_code = {m["code"]: m for m in munis.values() if m.get("city")}
    for code, items in by_shop.items():
        m = by_code.get(code)
        if not m:
            continue
        url = f'https://{DOMAIN}/furusato/{m["pref_slug"]}/{m["slug"]}/'
        for it in items:
            g = it["genre"]
            rec = out[g].setdefault(it["bid"], {
                "city": m["city"], "pref": m["pref"], "url": url, "count": 0})
            # 同じ蔵が複数自治体に返礼品を出している場合は、件数の多い自治体を代表にする
            if rec["url"] == url:
                rec["count"] += 1
            else:
                rec.setdefault("_others", {})
                rec["_others"][url] = rec["_others"].get(url, 0) + 1
    written = 0
    for g in GENRES:
        rel = LINK_OUT.get(g["key"])
        if not rel:
            continue
        path = os.path.join(ROOT, rel)
        if not os.path.isdir(os.path.dirname(path)):
            continue
        data = {}
        for bid, rec in out[g["key"]].items():
            best = (rec["url"], rec["count"])
            for u, n in (rec.get("_others") or {}).items():
                if n > best[1]:
                    best = (u, n)
            data[bid] = {"city": rec["city"], "pref": rec["pref"],
                         "url": best[0], "count": rec["count"] + sum((rec.get("_others") or {}).values())}
        json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        written += len(data)
        print(f'  {g["key"]}: {len(data)}生産者 → {rel}')
    return written


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    munis = json.load(open(MUNI_JSON, encoding="utf-8"))
    by_shop = load_items()
    producers_all = load_producers()
    gmap = {g["key"]: g for g in GENRES}

    targets = [m for m in munis.values() if m.get("city") and by_shop.get(m["code"])]
    targets.sort(key=lambda m: -len(by_shop[m["code"]]))
    if limit:
        targets = targets[:limit]

    index_rows = []
    made = 0
    for m in targets:
        items = by_shop[m["code"]]
        prods = producers_in(producers_all, m["pref"], m["city"])
        d = os.path.join(OUTROOT, m["pref_slug"], m["slug"])
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(
            build_page(m, items, prods, gmap))
        index_rows.append({"pref": m["pref"], "pref_slug": m["pref_slug"], "city": m["city"],
                           "slug": m["slug"], "items": len(items), "producers": len(prods),
                           "url": f'/furusato/{m["pref_slug"]}/{m["slug"]}/'})
        made += 1

    json.dump(index_rows, open(os.path.join(BASE, "data", "furusato_municipality_index.json"), "w",
                               encoding="utf-8"), ensure_ascii=False, indent=1)

    # 県インデックス（自治体ページの孤立とパンくずの404を防ぐ）
    by_pref = {}
    for r in index_rows:
        by_pref.setdefault((r["pref"], r["pref_slug"]), []).append(r)
    for (pref, pslug), rows in by_pref.items():
        rows.sort(key=lambda r: -r["items"])
        d = os.path.join(OUTROOT, pslug)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(
            render_pref_index(pref, pslug, rows, gmap))
    print(f"生成: {made}自治体ページ / {len(by_pref)}県インデックス")
    print("生産者→自治体ページの対応表:")
    n = write_producer_links(munis, by_shop)
    print(f"  計 {n}生産者にふるさと納税ページを紐づけ")
    tot = sum(r["items"] for r in index_rows)
    withp = sum(1 for r in index_rows if r["producers"])
    print(f"掲載返礼品 合計{tot}件 / 造り手を紐づけできた自治体 {withp}/{made}")
    for r in index_rows[:10]:
        print(f'  {r["pref"]}{r["city"]}: 返礼品{r["items"]} 造り手{r["producers"]} → {r["url"]}')


if __name__ == "__main__":
    main()
