#!/usr/bin/env python3
"""
地域の「風土のもの」を1ページにまとめた見本ページを生成する。

  /area/<県slug>/<自治体slug>/   自治体ごとの見本
  /area/                         見本の一覧

目的は営業で見せること。中身は楽天ふるさと納税の返礼品（機械的に分類）と、
Terroir HUB が収録している造り手なので、検索に出す品質には達していない。
したがって **noindex**（検索エンジンに載せない）で公開する。
本格導入が決まった地域だけ、確認済みの情報で作り直して索引に載せる。

使い方: python3 scripts/generate_area_pages.py
"""
import json, os, glob, html, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
DOMAIN = "www.terroirhub.com"
TODAY = datetime.date.today().isoformat()
AREA_DIR = os.path.join(BASE, "data", "area")
OUT = os.path.join(BASE, "area")

CATS = [("sake", "酒"), ("fruit", "果物"), ("meat", "肉"), ("seafood", "魚介"),
        ("farm", "米・野菜"), ("food", "加工品・調味料"), ("sweets", "菓子"),
        ("craft", "工芸・ものづくり"), ("stay", "体験・宿泊")]

GENRES = [
    dict(key="sake", name="日本酒", color="#B8452A", site="https://sake.terroirhub.com", path="sake",
         data="TerriorHUB　sake/data_*_breweries.json", suffix="_breweries.json"),
    dict(key="wine", name="日本ワイン", color="#722F37", site="https://wine.terroirhub.com", path="wine",
         data="terroirHUB wine/data/data_*_wineries.json", suffix="_wineries.json"),
    dict(key="shochu", name="焼酎・泡盛", color="#8B5E3C", site="https://shochu.terroirhub.com", path="shochu",
         data="terroirHUB 焼酎/data/data_*_distilleries.json", suffix="_distilleries.json"),
    dict(key="whisky", name="ウイスキー", color="#2D5F3F", site="https://whisky.terroirhub.com", path="whisky",
         data="terroirHUB whisky/data/data_*_distilleries.json", suffix="_distilleries.json"),
    dict(key="liqueur", name="梅酒・リキュール", color="#4A8BAE", site="https://liqueur.terroirhub.com", path="liqueur",
         data="terroirHUB liqueur/data/data_*_liqueurs.json", suffix="_liqueurs.json"),
]


def esc(s):
    return html.escape(str(s or ""), quote=True)


def clean(nm):
    import re
    s = re.sub(r'^[【\[]?\s*ふるさと納税\s*[】\]]?\s*', '', nm or '')
    s = re.sub(r'\s*(送料無料|数量限定|期間限定|訳あり|先行予約)\s*', ' ', s)
    return s.strip() or nm


def load_producers():
    out = {}
    for g in GENRES:
        for jf in glob.glob(os.path.join(ROOT, g["data"])):
            pref_slug = os.path.basename(jf).replace("data_", "").replace(g["suffix"], "")
            try:
                rows = json.load(open(jf, encoding="utf-8"))
            except Exception:
                continue
            for b in rows:
                if not b.get("id") or not b.get("address"):
                    continue
                out.setdefault(b["address"].replace(" ", "").replace("　", ""), []).append({
                    "name": b.get("name", ""), "genre": g["name"], "color": g["color"],
                    "url": f'{g["site"]}/{g["path"]}/{pref_slug}/{b["id"]}.html',
                })
    return out


CSS = """*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#FAFAF7;--surface:#F3F0EA;--border:rgba(0,0,0,.09);--text:#1a1816;--muted:rgba(26,24,22,.62);--gold:#996E1A;--fd:'Shippori Mincho',serif;--fb:'Noto Sans JP',sans-serif;--fn:'Inter',sans-serif}
html{scroll-behavior:smooth;-webkit-font-smoothing:antialiased}
body{background:var(--bg);color:var(--text);font-family:var(--fb);line-height:1.85;overflow-x:hidden}
a{color:inherit;text-decoration:none}
img{display:block;max-width:100%}
.nav{position:fixed;top:0;left:0;right:0;z-index:100;height:60px;display:flex;align-items:center;justify-content:space-between;padding:0 clamp(1.2rem,5vw,4rem);background:rgba(250,250,247,.94);backdrop-filter:blur(20px);border-bottom:1px solid var(--border)}
.nav-logo{font-family:var(--fd);font-size:1.12rem;font-weight:700;letter-spacing:.08em}
.nav-cta{font-family:var(--fn);font-size:.7rem;font-weight:600;letter-spacing:.1em;color:#fff;background:var(--gold);padding:.55rem 1.2rem}
.demo{margin-top:60px;background:#5E410C;color:#fff;padding:.6rem clamp(1.4rem,5vw,5rem);font-size:.78rem;line-height:1.6}
.demo b{font-family:var(--fn);background:#fff;color:#5E410C;padding:.05rem .45rem;margin-right:.5rem;font-size:.7rem;letter-spacing:.08em}
.crumb{padding:.85rem clamp(1.4rem,5vw,5rem);font-size:.74rem;color:var(--muted);background:#fff;border-bottom:1px solid var(--border)}
.hero{padding:clamp(2.4rem,6vw,4rem) clamp(1.4rem,5vw,5rem) clamp(1.8rem,3vw,2.4rem);background:#fff;border-bottom:1px solid var(--border)}
.inner{max-width:1120px;margin:0 auto}
.eyebrow{font-family:var(--fn);font-size:.6rem;font-weight:600;letter-spacing:.3em;text-transform:uppercase;color:var(--gold);margin-bottom:.9rem}
h1{font-family:var(--fd);font-size:clamp(1.7rem,4.2vw,2.7rem);font-weight:700;line-height:1.4;margin-bottom:1rem}
.lead{font-size:clamp(.92rem,1.3vw,1.02rem);max-width:760px;line-height:2}
.chips{display:flex;gap:.45rem;flex-wrap:wrap;margin-top:1.4rem}
.chip{font-family:var(--fn);font-size:.74rem;border:1px solid var(--border);background:var(--bg);padding:.35rem .8rem;color:var(--muted)}
.chip b{color:var(--text);font-weight:600;margin-left:.25rem}
section{padding:clamp(2rem,4vw,3rem) clamp(1.4rem,5vw,5rem) 0}
h2{font-family:var(--fd);font-size:clamp(1.15rem,2.2vw,1.5rem);font-weight:700;margin-bottom:.3rem;display:flex;align-items:baseline;gap:.6rem;flex-wrap:wrap}
h2 span{font-family:var(--fn);font-size:.74rem;font-weight:500;color:var(--muted)}
.sec-lead{font-size:.86rem;color:var(--muted);margin-bottom:1.1rem}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.9rem}
@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}}
.card{background:#fff;border:1px solid var(--border);display:flex;flex-direction:column;transition:box-shadow .25s,transform .25s}
.card:hover{box-shadow:0 10px 26px rgba(40,30,20,.12);transform:translateY(-2px)}
.card-img{aspect-ratio:1/1;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden}
.card-img img{width:100%;height:100%;object-fit:contain;padding:10px}
.card-name{font-size:.8rem;line-height:1.5;padding:9px 12px 0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;flex:1}
.card-price{font-family:var(--fd);font-size:.78rem;color:#7a2a18;padding:7px 12px 0}
.card-price b{font-family:var(--fn);font-size:1rem;font-weight:600}
.card-buy{font-family:var(--fn);font-size:.64rem;font-weight:600;letter-spacing:.05em;color:#fff;background:#BF0000;text-align:center;padding:7px 0;margin:9px 12px 12px;border-radius:3px}
.prods{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem}
@media(max-width:860px){.prods{grid-template-columns:1fr}}
.prod{background:#fff;border:1px solid var(--border);padding:.9rem 1rem;display:block}
.prod:hover{box-shadow:0 8px 20px rgba(40,30,20,.1)}
.prod-g{font-family:var(--fn);font-size:.6rem;font-weight:600;letter-spacing:.1em}
.prod-n{font-family:var(--fd);font-size:1rem;font-weight:600;margin-top:3px}
.cta{max-width:1120px;margin:clamp(2.4rem,5vw,3.4rem) auto 0;padding:0 clamp(1.4rem,5vw,5rem)}
.cta-in{background:var(--surface);border:1px solid var(--border);padding:1.6rem 1.8rem}
.cta-in h3{font-family:var(--fd);font-size:1.15rem;margin-bottom:.5rem}
.cta-in p{font-size:.88rem;color:var(--muted);line-height:1.9;margin-bottom:1rem;max-width:720px}
.btnrow{display:flex;gap:.6rem;flex-wrap:wrap}
.btnrow a{font-family:var(--fn);font-size:.76rem;font-weight:600;letter-spacing:.08em;background:#fff;border:1px solid var(--border);padding:.7rem 1.4rem}
.btnrow a:first-child{background:var(--gold);color:#fff;border-color:var(--gold)}
.note{max-width:1120px;margin:1.6rem auto 0;padding:0 clamp(1.4rem,5vw,5rem)}
.note-in{background:#fff;border:1px solid var(--border);padding:1rem 1.2rem;font-size:.78rem;color:var(--muted);line-height:1.85}
.foot{margin-top:clamp(2.6rem,5vw,4rem);padding:2.2rem clamp(1.4rem,5vw,5rem);border-top:1px solid var(--border);background:#fff;font-size:.76rem;color:var(--muted)}
.foot-logo{font-family:var(--fd);font-size:1rem;color:var(--text);margin-bottom:.4rem}
.alist{display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem}
@media(max-width:860px){.alist{grid-template-columns:1fr}}
.acard{background:#fff;border:1px solid var(--border);padding:1.2rem 1.3rem;display:block}
.acard:hover{box-shadow:0 10px 24px rgba(40,30,20,.12)}
.acard h3{font-family:var(--fd);font-size:1.15rem;margin-bottom:.2rem}
.acard .pr{font-size:.76rem;color:var(--muted)}
.acard .ct{font-family:var(--fn);font-size:.74rem;color:var(--gold);margin-top:.5rem}"""

NAV = """<nav class="nav">
  <a href="/" class="nav-logo">Terroir HUB</a>
  <a href="/business/municipality/" class="nav-cta">導入のご相談</a>
</nav>
<div class="demo"><b>見本</b>この地域ページは、公開情報から自動で構成した見本です。本格導入では、事業者に確認した情報と写真で作り直します。</div>"""


def head(title, desc, url):
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="noindex, follow">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@500;600;700&family=Noto+Sans+JP:wght@300;400;500;700&family=Inter:wght@500;600&display=swap" rel="stylesheet">
<style>{CSS}</style>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-NG35V7K1JH"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-NG35V7K1JH');</script>
</head>
<body>
{NAV}"""


def card(it, city):
    return (f'<a class="card" href="{esc(it["url"])}" target="_blank" rel="nofollow sponsored noopener" '
            f'onclick="if(window.gtag)gtag(\'event\',\'area_item_click\',{{city:\'{esc(city)}\'}});">'
            f'<div class="card-img"><img src="{esc(it["image"])}" alt="{esc(clean(it["name"]))}" loading="lazy"></div>'
            f'<div class="card-name">{esc(clean(it["name"]))}</div>'
            + (f'<div class="card-price">寄付 <b>{it["price"]:,}</b>円</div>' if it.get("price") else '')
            + '<div class="card-buy">楽天ふるさと納税で見る →</div></a>')


def render_city(d, producers):
    full = d["pref"] + d["city"]
    url = f'https://{DOMAIN}/area/{d["pref_slug"]}/{d["slug"]}/'
    present = [(k, n) for k, n in CATS if d["counts"].get(k)]
    chips = "".join(f'<span class="chip">{esc(n)}<b>{d["counts"][k]}</b></span>' for k, n in present)
    title = f'{full}の風土 — 酒・食・工芸・体験 {d["total"]}件 | Terroir HUB（見本）'
    desc = f'{full}のふるさと納税返礼品を、酒・果物・肉・魚介・米野菜・加工品・菓子・工芸・体験に分けて一覧にした見本ページです。'

    secs = ""
    for k, n in present:
        items = [i for i in d["items"] if i["cat"] == k]
        items.sort(key=lambda x: (-x.get("review_count", 0), x.get("price") or 10**9))
        # 同一商品の重複を除く（同じ返礼品が別IDで複数登録されていることがある）
        seen_i, uniq_i = set(), []
        for i in items:
            key_i = (clean(i["name"])[:40], i.get("price"))
            if key_i in seen_i:
                continue
            seen_i.add(key_i); uniq_i.append(i)
        items = uniq_i
        cards = "".join(card(i, d["city"]) for i in items[:8])
        secs += (f'<section><div class="inner"><h2>{esc(n)}<span>{len(items)}件</span></h2>'
                 f'<div class="grid">{cards}</div></div></section>')

    key = (d["pref"] + d["city"]).replace(" ", "")
    plist = []
    for addr, rows in producers.items():
        if addr.startswith(key):
            plist.extend(rows)
    prod_html = ""
    if plist:
        seen, uniq = set(), []
        for p in plist:
            if p["name"] not in seen:
                seen.add(p["name"]); uniq.append(p)
        rows = "".join(f'<a class="prod" href="{esc(p["url"])}"><div class="prod-g" style="color:{p["color"]}">'
                       f'{esc(p["genre"])}</div><div class="prod-n">{esc(p["name"])}</div></a>' for p in uniq)
        prod_html = (f'<section><div class="inner"><h2>{esc(d["city"])}の造り手<span>{len(uniq)}者</span></h2>'
                     f'<p class="sec-lead">Terroir HUB が収録している酒の造り手です。各ページに所在地・公式サイト・代表銘柄を出典つきで掲載しています。</p>'
                     f'<div class="prods">{rows}</div></div></section>')

    return head(title, desc, url) + f"""
<div class="crumb"><a href="/">ホーム</a> › <a href="/area/">地域</a> › {esc(full)}</div>
<header class="hero"><div class="inner">
  <div class="eyebrow">Terroir of {esc(d["city"])}</div>
  <h1>{esc(full)}の風土</h1>
  <p class="lead">{esc(d["city"])}の返礼品 {d["total"]}件を、酒・食・工芸・体験に分けて並べました。
  本格導入では、ここに事業者の物語・写真・英語ページ・見学や体験の案内が加わります。</p>
  <div class="chips">{chips}</div>
</div></header>
{secs}
{prod_html}
<div class="cta"><div class="cta-in">
  <h3>この地域のページを、本格的に作りませんか</h3>
  <p>自治体・観光協会・DMO・地域商社・事業者のいずれからでもご相談いただけます。
  事業者への確認、写真の掲載、英語への対応、毎月の閲覧レポートまで一式でお引き受けします。</p>
  <div class="btnrow">
    <a href="/business/area/">申し込む・料金を見る</a>
    <a href="/business/municipality/#contact">自治体の方はこちら</a>
    <a href="/area/">ほかの地域の見本を見る</a>
  </div>
</div></div>
<div class="note"><div class="note-in">
  <p>掲載内容は楽天ふるさと納税の返礼品情報にもとづき、分類は楽天のジャンル情報を用いて機械的に行っています（最終更新 {d["collected_at"]}）。
  寄付金額・在庫・提供事業者は変動しますので、寄付前に各返礼品ページでご確認ください。</p>
  <p>本ページは楽天アフィリエイトのリンクを含みます。Terroir HUB は寄付の受付・決済を行っていません。</p>
</div></div>
<footer class="foot"><div class="foot-logo">Terroir HUB</div>
  <p>日本の風土と造り手を、正確な一次情報で。｜運営：合同会社FOMUS</p></footer>
</body></html>"""


def render_index(areas):
    url = f"https://{DOMAIN}/area/"
    cards = ""
    for d in sorted(areas, key=lambda x: -x["total"]):
        top = "・".join(n for k, n in CATS if d["counts"].get(k, 0) >= 20)[:40]
        cards += (f'<a class="acard" href="/area/{d["pref_slug"]}/{d["slug"]}/">'
                  f'<h3>{esc(d["city"])}</h3><div class="pr">{esc(d["pref"])}</div>'
                  f'<div class="ct">{d["total"]}件 ／ {esc(top)}</div></a>')
    return head("地域の風土ページ 見本一覧 | Terroir HUB",
                "自治体・観光協会・事業者向けに、地域の風土のものを1ページにまとめた見本です。", url) + f"""
<div class="crumb"><a href="/">ホーム</a> › 地域</div>
<header class="hero"><div class="inner">
  <div class="eyebrow">Area Pages</div>
  <h1>地域の風土を、1ページに。</h1>
  <p class="lead">その土地の酒・果物・肉・魚介・米や野菜・加工品・菓子・工芸・体験を、ひとつのページにまとめます。
  下は{len(areas)}地域の見本です。実際の導入では、事業者に確認した情報と写真で作り直し、英語にも対応します。</p>
</div></header>
<section><div class="inner"><h2>見本のある地域<span>{len(areas)}地域</span></h2>
<div class="alist">{cards}</div></div></section>
<div class="cta"><div class="cta-in">
  <h3>御地域のページをご覧になりたい方へ</h3>
  <p>ご希望の市区町村があれば、見本をお作りしてお送りします。自治体・観光協会・DMO・地域商社・事業者のいずれからでも承ります。</p>
  <div class="btnrow"><a href="/business/area/">料金とお申し込み</a><a href="/business/municipality/#contact">見本を依頼する</a></div>
</div></div>
<footer class="foot"><div class="foot-logo">Terroir HUB</div>
  <p>日本の風土と造り手を、正確な一次情報で。｜運営：合同会社FOMUS</p></footer>
</body></html>"""


def main():
    producers = load_producers()
    areas = []
    for f in sorted(glob.glob(os.path.join(AREA_DIR, "*", "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        outdir = os.path.join(OUT, d["pref_slug"], d["slug"])
        os.makedirs(outdir, exist_ok=True)
        open(os.path.join(outdir, "index.html"), "w", encoding="utf-8").write(render_city(d, producers))
        areas.append(d)
        print(f'  {d["pref"]}{d["city"]}: {d["total"]}件 → /area/{d["pref_slug"]}/{d["slug"]}/')
    if areas:
        os.makedirs(OUT, exist_ok=True)
        open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(render_index(areas))
        print(f'一覧: /area/（{len(areas)}地域）')


if __name__ == "__main__":
    main()
