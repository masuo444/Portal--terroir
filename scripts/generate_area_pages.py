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

EN_QUEUE = []
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
    """住所 → 造り手の詳細（説明・見学・最寄駅・公式・出典つき）"""
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
                vi = b.get("visit_info") or {}
                station = b.get("nearest_station")
                if not station and isinstance(b.get("nearest_station_calc"), dict):
                    c = b["nearest_station_calc"]
                    if c.get("station"):
                        station = f'{c.get("line","")} {c["station"]}駅'.strip() + "（座標からの算出）"
                brands = [(x.get("name") if isinstance(x, dict) else str(x)) for x in (b.get("brands") or [])]
                out.setdefault(b["address"], []).append({
                    "name": b.get("name", ""), "genre": g["name"], "color": g["color"],
                    "url": f'{g["site"]}/{g["path"]}/{pref_slug}/{b["id"]}.html',
                    "desc": (b.get("desc") or "").strip(),
                    "visit": (b.get("visit") or vi.get("notes_ja") or "").strip(),
                    "reservation": vi.get("reservation", ""), "station": station or "",
                    "official": b.get("url", ""), "source": b.get("source", ""),
                    "brands": [x for x in brands if x][:3],
                    "founded": b.get("founded", ""),
                    "founded_era": b.get("founded_era", ""),
                    "name_en": b.get("name_en", ""), "address": b.get("address", ""),
                    "tel": b.get("tel", ""), "vi": vi, "genre_key": g["key"],
                })
    return out


# ── 見学情報の表記（公式記載のある項目だけを出す）──
V_STATUS = {"open": "見学を受け付けています", "paused": "見学を休止中", "closed": "一般見学は行っていません",
            "inquire": "見学は要問い合わせ"}
V_RESV = {"required": "予約が必要", "recommended": "予約をおすすめします", "not_required": "予約不要"}
V_TASTE = {"paid": "有料試飲あり", "free": "無料試飲あり", "available": "試飲あり", "none": "試飲なし"}
V_EN = {"tour": "英語での案内あり", "materials": "英語の資料あり"}
V_STATUS_EN = {"open": "Open to visitors", "paused": "Visits suspended", "closed": "Not open to visitors",
               "inquire": "Enquire in advance"}
V_RESV_EN = {"required": "Reservation required", "recommended": "Reservation recommended",
             "not_required": "No reservation needed"}
V_TASTE_EN = {"paid": "Paid tasting", "free": "Free tasting", "available": "Tasting available", "none": "No tasting"}
V_EN_EN = {"tour": "English-guided tour", "materials": "English materials"}


def visit_facts(p, en=False):
    """公式に記載のある見学情報だけを並べる。無い項目は出さない。"""
    vi = p.get("vi") or {}
    out = []
    S, R, T, E = (V_STATUS_EN, V_RESV_EN, V_TASTE_EN, V_EN_EN) if en else (V_STATUS, V_RESV, V_TASTE, V_EN)
    if vi.get("status") and S.get(vi["status"]):
        out.append(S[vi["status"]])
    if vi.get("reservation") and R.get(vi["reservation"]):
        out.append(R[vi["reservation"]])
    if vi.get("tasting") and T.get(vi["tasting"]):
        out.append(T[vi["tasting"]])
    if vi.get("english") and E.get(vi["english"]):
        out.append(E[vi["english"]])
    if vi.get("fee"):
        out.append(("Fee: " if en else "料金：") + str(vi["fee"])[:40])
    if vi.get("duration"):
        out.append(("Duration: " if en else "所要：") + str(vi["duration"])[:30])
    if vi.get("shop"):
        out.append("Shop on site" if en else "売店あり")
    if vi.get("facility"):
        out.append(("Facility: " if en else "施設：") + str(vi["facility"])[:36])
    return out


def has_visit(p):
    vi = p.get("vi") or {}
    return bool(vi.get("status") or vi.get("notes_ja") or p.get("visit"))


def norm_addr(a):
    """住所の表記ゆれを吸収する。郵便番号・空白を落とす。"""
    import re as _re
    a = (a or "").replace(" ", "").replace("　", "")
    a = _re.sub(r'〒?\d{3}-?\d{4}', '', a)
    return a.strip()


def addr_matches(addr, pref, city):
    """住所が「県＋市区町村」に一致するか。
    郵便番号つき・県名なし・郡つき町村（〇〇郡△△町）のいずれにも対応する。"""
    import re as _re
    a = norm_addr(addr)
    if not a:
        return False
    if pref in a:
        rest = a[a.find(pref) + len(pref):]
    else:
        rest = a  # 県名が書かれていない場合（データは県別ファイルなので県は確定している）
    return rest.startswith(city) or bool(_re.match(r'[^\s]{1,6}郡' + _re.escape(city), rest))


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
.lead.en{font-size:.86rem;color:var(--muted);margin-top:.7rem;font-family:var(--fn);line-height:1.85}
.lead.sub{font-size:.84rem;color:var(--muted);margin-top:.9rem;padding-top:.8rem;border-top:1px dashed var(--border)}
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
/* 本格版 */
.enlink{margin-top:1rem;font-family:var(--fn);font-size:.8rem}
.enlink a{color:var(--gold);font-weight:600}
.vgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:.8rem}
@media(max-width:860px){.vgrid{grid-template-columns:1fr}}
.vcard{background:#fff;border:1px solid var(--border);border-left:3px solid var(--gold);padding:1.2rem 1.3rem}
.vcard h3{font-family:var(--fd);font-size:1.08rem;margin:.25rem 0 .55rem}
.vcard h3 a{color:inherit}
.vcard h3 a:hover{color:var(--gold)}
.vchips{display:flex;gap:.35rem;flex-wrap:wrap;margin-bottom:.6rem}
.vchip{font-family:var(--fn);font-size:.72rem;background:var(--surface);border:1px solid var(--border);padding:.18rem .6rem}
.vnote{font-size:.86rem;line-height:1.8;color:var(--text)}
.vaccess{font-size:.8rem;color:var(--muted);margin-top:.4rem}
.vbtn{display:inline-block;margin-top:.7rem;font-family:var(--fn);font-size:.74rem;font-weight:600;color:#fff;background:var(--gold);padding:.5rem 1.1rem}
.atable{width:100%;border-collapse:collapse;font-size:.88rem;background:#fff;border:1px solid var(--border)}
.atable th{text-align:left;padding:.6rem .9rem;border-bottom:1px solid var(--border);width:14em;font-weight:500;color:var(--muted);vertical-align:top}
.atable td{padding:.6rem .9rem;border-bottom:1px solid var(--border)}
.qa{background:#fff;border:1px solid var(--border);padding:1.1rem 1.3rem;margin-bottom:.6rem}
.qa h3{font-family:var(--fd);font-size:1rem;margin-bottom:.3rem}
.qa p{font-size:.88rem;color:var(--muted);line-height:1.85}
.srclist{list-style:none;font-size:.78rem;line-height:1.9;color:var(--muted);background:#fff;border:1px solid var(--border);padding:1rem 1.2rem}
.srclist a{color:var(--gold);word-break:break-all}
.upd{font-size:.78rem;color:var(--muted);margin-top:.8rem;line-height:1.8}
.upd a{color:var(--gold)}
.pgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:.8rem}
@media(max-width:860px){.pgrid{grid-template-columns:1fr}}
.pitem{background:#fff;border:1px solid var(--border);padding:1.2rem 1.3rem}
.pgenre{font-family:var(--fn);font-size:.62rem;font-weight:600;letter-spacing:.1em}
.pitem h3{font-family:var(--fd);font-size:1.08rem;margin:.25rem 0 .45rem}
.pdesc{font-size:.86rem;color:var(--text);line-height:1.8}
.ptable{width:100%;border-collapse:collapse;font-size:.82rem;margin-top:.6rem}
.ptable th{text-align:left;width:5.6em;color:var(--muted);font-weight:500;padding:.25rem 0;vertical-align:top}
.ptable td{padding:.25rem 0}
.plinks{margin-top:.6rem;font-size:.84rem}
.plinks a{color:var(--gold);margin-right:.8rem;font-weight:500}
.psrc{font-size:.72rem;color:var(--muted);margin-top:.3rem}
.psrc a{color:var(--muted);text-decoration:underline}
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

NAV_FULL = """<nav class="nav">
  <a href="/" class="nav-logo">Terroir HUB</a>
  <a href="/business/area/" class="nav-cta">地域ページについて</a>
</nav>"""

NAV = """<nav class="nav">
  <a href="/" class="nav-logo">Terroir HUB</a>
  <a href="/business/municipality/" class="nav-cta">導入のご相談</a>
</nav>
<div class="demo"><b>見本</b>この地域ページは、公開情報から自動で構成した見本です。本格導入では、事業者に確認した情報と写真で作り直します。</div>"""


def head(title, desc, url, robots='<meta name="robots" content="noindex, follow">', extra="", nav=None):
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
{robots}
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@500;600;700&family=Noto+Sans+JP:wght@300;400;500;700&family=Inter:wght@500;600&display=swap" rel="stylesheet">
{extra}
<style>{CSS}</style>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-NG35V7K1JH"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-NG35V7K1JH');</script>
</head>
<body>
{nav if nav else NAV}"""


def card(it, city):
    return (f'<a class="card" href="{esc(it["url"])}" target="_blank" rel="nofollow sponsored noopener" '
            f'onclick="if(window.gtag)gtag(\'event\',\'area_item_click\',{{city:\'{esc(city)}\'}});">'
            f'<div class="card-img"><img src="{esc(it["image"])}" alt="{esc(clean(it["name"]))}" loading="lazy"></div>'
            f'<div class="card-name">{esc(clean(it["name"]))}</div>'
            + (f'<div class="card-price">寄付 <b>{it["price"]:,}</b>円</div>' if it.get("price") else '')
            + '<div class="card-buy">楽天ふるさと納税で見る →</div></a>')


def load_text(d):
    p = os.path.join(BASE, "data", "area_text", d["pref_slug"], f'{d["slug"]}.json')
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def sec_visit(d, uniq):
    """見学できる造り手（一次情報の中心。出典と最終確認日を必ず添える）"""
    vs = [p for p in uniq if has_visit(p)]
    if not vs:
        return "", 0
    cards = ""
    for p in vs:
        vi = p.get("vi") or {}
        facts = visit_facts(p)
        chips = "".join(f'<span class="vchip">{esc(f)}</span>' for f in facts)
        note = esc((vi.get("notes_ja") or p.get("visit") or "")[:150])
        src = vi.get("source") or p.get("source") or ""
        lc = vi.get("last_checked") or ""
        meta = []
        if src:
            meta.append(f'<a href="{esc(src)}" target="_blank" rel="noopener">出典</a>')
        if lc:
            meta.append(f'最終確認 {esc(lc)}')
        btn = (f'<a class="vbtn" href="{esc(vi["reservation_url"])}" target="_blank" rel="noopener">公式で予約する →</a>'
               if vi.get("reservation_url") else "")
        cards += (f'<article class="vcard"><div class="pgenre" style="color:{p["color"]}">{esc(p["genre"])}</div>'
                  f'<h3><a href="{esc(p["url"])}">{esc(p["name"])}</a></h3>'
                  + (f'<div class="vchips">{chips}</div>' if chips else "")
                  + (f'<p class="vnote">{note}</p>' if note else "")
                  + (f'<p class="vaccess">{esc(p["station"])}</p>' if p.get("station") else "")
                  + btn
                  + (f'<p class="psrc">{" ／ ".join(meta)}</p>' if meta else "")
                  + '</article>')
    html_ = (f'<section id="visit"><div class="inner"><h2>見学・直売のある造り手<span>{len(vs)}者</span></h2>'
             f'<p class="sec-lead">各社の公式情報から、見学の受付状況・予約の要否・試飲や売店の有無をまとめています。'
             f'出典と最終確認日を添えていますが、受付状況は変わることがあるため、訪問前に公式サイトでご確認ください。</p>'
             f'<div class="vgrid">{cards}</div></div></section>')
    return html_, len(vs)


def sec_access(d, uniq):
    """最寄駅ごとの造り手（旅の計画に直接使える形）"""
    by = {}
    for p in uniq:
        st = (p.get("station") or "").replace("（座標からの算出）", "").strip()
        if st:
            by.setdefault(st, []).append(p["name"])
    if len(by) < 2:
        return ""
    rows = "".join(f'<tr><th>{esc(k)}</th><td>{esc("、".join(v))}</td></tr>'
                   for k, v in sorted(by.items(), key=lambda x: -len(x[1]))[:10])
    return (f'<section><div class="inner"><h2>最寄駅から探す</h2>'
            f'<p class="sec-lead">公式に記載のある最寄駅、記載がない場合は所在地の座標から算出した最寄駅です（算出したものはその旨を明記しています）。</p>'
            f'<table class="atable">{rows}</table></div></section>')


def sec_faq(d, uniq, nvisit, en=False):
    city = d["city"]
    names = "、".join(p["name"] for p in uniq[:8])
    qa = [(f'{city}にはどのような酒の造り手がありますか？',
           f'Terroir HUB では{city}の造り手を{len(uniq)}者収録しています。' + (f'（{names} ほか）' if names else '')
           + '各ページに所在地・公式サイト・代表銘柄を、出典を明記して掲載しています。')]
    if nvisit:
        qa.append((f'{city}で見学できる造り手はありますか？',
                   f'公式情報で見学や直売に関する案内が確認できるのは{nvisit}者です。予約の要否や試飲の有無も'
                   f'あわせて掲載しています。受付状況は変わることがあるため、訪問前に各公式サイトでご確認ください。'))
    if d["total"]:
        qa.append((f'{city}の返礼品にはどんなものがありますか？',
                   '掲載している' + str(d["total"]) + '件の内訳は、'
                   + "、".join(f'{n}{d["counts"][k]}件' for k, n in CATS if d["counts"].get(k)) + 'です。'))
    faq = "".join(f'<div class="qa"><h3>{esc(q)}</h3><p>{esc(a)}</p></div>' for q, a in qa)
    ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
                     "mainEntity": [{"@type": "Question", "name": q,
                                     "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qa]},
                    ensure_ascii=False)
    return f'<section><div class="inner"><h2>よくある質問</h2>{faq}</div></section>', ld


def sec_sources(d, uniq):
    srcs = []
    for p in uniq:
        vi = p.get("vi") or {}
        u = vi.get("source") or p.get("source")
        if u and u not in [x[1] for x in srcs]:
            srcs.append((p["name"], u))
    rows = "".join(f'<li>{esc(n)}：<a href="{esc(u)}" target="_blank" rel="noopener">{esc(u[:68])}</a></li>'
                   for n, u in srcs[:30])
    return (f'<section><div class="inner"><h2>出典</h2>'
            f'<p class="sec-lead">造り手の情報は、各社の公式サイトおよび業界団体の公表情報にもとづいています。'
            f'確認できない項目は掲載していません。</p><ul class="srclist">{rows}</ul>'
            f'<p class="upd">最終更新：{d["collected_at"]}　／　運営：合同会社FOMUS（<a href="https://www.terroirhub.com/">Terroir HUB</a>）　'
            f'／　掲載内容の修正は<a href="https://www.terroirhub.com/listing-update/">こちら</a>から承ります。</p></div></section>')


def render_city(d, producers):
    tx = load_text(d)
    full_name = d["pref"] + d["city"]
    full = False  # 本格版かどうか（造り手の情報量で決まる。下で判定）
    url = f'https://{DOMAIN}/area/{d["pref_slug"]}/{d["slug"]}/'
    present = [(k, n) for k, n in CATS if d["counts"].get(k)]
    chips = "".join(f'<span class="chip">{esc(n)}<b>{d["counts"][k]}</b></span>' for k, n in present)

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

    plist = []
    for addr, rows in producers.items():
        if addr_matches(addr, d["pref"], d["city"]):
            plist.extend(rows)
    prod_html = ""
    if plist:
        seen, uniq = set(), []
        for p in plist:
            if p["name"] not in seen:
                seen.add(p["name"]); uniq.append(p)
        uniq.sort(key=lambda x: (0 if x.get("desc") else 1, x["name"]))
        rich = [p for p in uniq if p.get("desc") and p.get("source")]
        full = len(rich) >= 3 and bool(tx.get("intro_ja"))
        rows = ""
        for p in uniq:
            meta = []
            if p.get("founded"):
                meta.append(("創業", esc(str(p["founded"])) + "年"))
            if p.get("brands"):
                meta.append(("代表銘柄", "、".join(esc(b) for b in p["brands"])))
            if p.get("visit"):
                meta.append(("見学", esc(p["visit"][:70])))
            if p.get("station"):
                meta.append(("最寄駅", esc(p["station"])))
            mt = "".join(f'<tr><th>{k}</th><td>{v}</td></tr>' for k, v in meta)
            links = f'<a href="{esc(p["url"])}">詳しく見る →</a>'
            if p.get("official"):
                links += f' <a href="{esc(p["official"])}" target="_blank" rel="noopener">公式サイト</a>'
            src = (f'<p class="psrc">出典：<a href="{esc(p["source"])}" target="_blank" rel="noopener">公式情報</a></p>'
                   if p.get("source") else "")
            rows += (f'<article class="pitem"><div class="pgenre" style="color:{p["color"]}">{esc(p["genre"])}</div>'
                     f'<h3>{esc(p["name"])}</h3>'
                     + (f'<p class="pdesc">{esc(p["desc"][:140])}</p>' if p.get("desc") else "")
                     + (f'<table class="ptable">{mt}</table>' if mt else "")
                     + f'<p class="plinks">{links}</p>{src}</article>')
        prod_html = (f'<section><div class="inner"><h2>{esc(d["city"])}の造り手<span>{len(uniq)}者</span></h2>'
                     f'<p class="sec-lead">公式情報にもとづいて収録しています。確認できない項目は掲載していません。</p>'
                     f'<div class="pgrid">{rows}</div></div></section>')

    title = (f'{full_name}の風土 — 酒・食・工芸・体験 {d["total"]}件 | Terroir HUB'
             if full else f'{full_name}の風土 — 酒・食・工芸・体験 {d["total"]}件 | Terroir HUB（見本）')
    desc = (f'{full_name}の酒・果物・肉・魚介・米や野菜・加工品・菓子・工芸・体験を一覧にしました。市内の造り手も公式情報にもとづいて掲載しています。'
            if full else
            f'{full_name}のふるさと納税返礼品を、酒・果物・肉・魚介・米野菜・加工品・菓子・工芸・体験に分けて一覧にした見本ページです。')
    ld = json.dumps({"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Terroir HUB", "item": f"https://{DOMAIN}/"},
            {"@type": "ListItem", "position": 2, "name": "地域", "item": f"https://{DOMAIN}/area/"},
            {"@type": "ListItem", "position": 3, "name": full_name, "item": url}]},
        {"@type": "CollectionPage", "name": title, "description": desc, "url": url,
         "about": {"@type": "AdministrativeArea", "name": full_name}}]}, ensure_ascii=False)
    robots = ('<meta name="robots" content="index,follow,max-image-preview:large">' if full
              else '<meta name="robots" content="noindex, follow">')
    extra = f'<script type="application/ld+json">{ld}</script>' if full else ""
    if full:
        visit_html, nvisit = sec_visit(d, uniq)
        faq_html, faq_ld = sec_faq(d, uniq, nvisit)
        access_html = sec_access(d, uniq)
        src_html = sec_sources(d, uniq)
        en_url = f'https://{DOMAIN}/area/en/{d["pref_slug"]}/{d["slug"]}/'
        extra += (f'<script type="application/ld+json">{faq_ld}</script>'
                  f'<link rel="alternate" hreflang="ja" href="{url}">'
                  f'<link rel="alternate" hreflang="en" href="{en_url}">'
                  f'<link rel="alternate" hreflang="x-default" href="{url}">')
        chips2 = (f'<span class="chip">収録している造り手<b>{len(uniq)}</b></span>'
                  + (f'<span class="chip">見学・直売あり<b>{nvisit}</b></span>' if nvisit else "")
                  + f'<span class="chip">ふるさと納税返礼品<b>{d["total"]}</b></span>')
        EN_QUEUE.append((d, tx, uniq, nvisit))
        return head(title, desc, url, robots, extra, NAV_FULL) + f"""
<div class="crumb"><a href="/">ホーム</a> › <a href="/area/">地域</a> › {esc(full_name)}</div>
<header class="hero"><div class="inner">
  <div class="eyebrow">Terroir of {esc(d["city"])}</div>
  <h1>{esc(full_name)}の風土</h1>
  <p class="lead">{esc(tx.get("intro_ja",""))}</p>
  <div class="chips">{chips2}</div>
  <p class="enlink"><a href="{en_url}">English page →</a></p>
</div></header>
{visit_html}
{prod_html}
{access_html}
<section><div class="inner"><h2>ふるさと納税の返礼品<span>{d["total"]}件</span></h2>
  <p class="sec-lead">{esc(full_name)}が提供する返礼品です。寄付金額・在庫・提供事業者は変動しますので、
  寄付前に各返礼品ページでご確認ください。以下のリンクは楽天アフィリエイトのリンクを含みます（PR）。</p>
  {secs}
</div></section>
{faq_html}
{src_html}
<div class="cta"><div class="cta-in">
  <h3>この地域の発信を、一緒に。</h3>
  <p>掲載内容の追加・修正は無料で承ります。地域全体のページとして運用する場合のご案内もございます。</p>
  <div class="btnrow">
    <a href="/business/area/">地域ページについて</a>
    <a href="/business/municipality/#contact">自治体の方はこちら</a>
  </div>
</div></div>
<footer class="foot"><div class="foot-logo">Terroir HUB</div>
  <p>日本の風土と造り手を、正確な一次情報で。｜運営：合同会社FOMUS</p></footer>
</body></html>"""

    return head(title, desc, url, robots, extra, NAV) + f"""
<div class="crumb"><a href="/">ホーム</a> › <a href="/area/">地域</a> › {esc(full_name)}</div>
<header class="hero"><div class="inner">
  <div class="eyebrow">Terroir of {esc(d["city"])}</div>
  <h1>{esc(full_name)}の風土</h1>
  <p class="lead">{esc(tx.get("intro_ja")) or (esc(d["city"]) + "の返礼品 " + str(d["total"]) + "件を、酒・食・工芸・体験に分けて並べました。")}</p>
  {'<p class="lead en">' + esc(tx["intro_en"]) + '</p>' if tx.get("intro_en") else ''}
  <p class="lead sub">本格導入では、ここに事業者の物語・写真・英語ページ・見学や体験の案内が加わります。</p>
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


def render_city_en(d, tx, uniq, nvisit):
    """英語ページ。翻訳が確かなもの（名称・見学の事実）だけを英語にし、日本語の説明文は訳さない。"""
    full_name = d["pref"] + d["city"]
    city_en = d["slug"].replace("-", " ").title()
    pref_en = d["pref_slug"].replace("-", " ").title()
    url = f'https://{DOMAIN}/area/en/{d["pref_slug"]}/{d["slug"]}/'
    ja_url = f'https://{DOMAIN}/area/{d["pref_slug"]}/{d["slug"]}/'
    title = f'{city_en}, {pref_en} — Sake, Wine and Local Makers | Terroir HUB'
    desc = (f'Producers in {city_en} ({d["city"]}): {len(uniq)} listed from official sources'
            + (f', {nvisit} open to visitors' if nvisit else '') + '. Visiting details with sources and last-checked dates.')
    cards = ""
    for p in uniq:
        facts = visit_facts(p, en=True)
        chips = "".join(f'<span class="vchip">{esc(f)}</span>' for f in facts)
        vi = p.get("vi") or {}
        src, lc = vi.get("source") or p.get("source") or "", vi.get("last_checked") or ""
        meta = []
        if src:
            meta.append(f'<a href="{esc(src)}" target="_blank" rel="noopener">Source</a>')
        if lc:
            meta.append(f'Last checked {esc(lc)}')
        nm = p.get("name_en") or p["name"]
        official = (f' <a href="{esc(p["official"])}" target="_blank" rel="noopener">Official site</a>'
                    if p.get("official") else "")
        cards += (f'<article class="vcard"><div class="pgenre" style="color:{p["color"]}">{esc(p["genre_key"].upper())}</div>'
                  f'<h3><a href="{esc(p["url"])}">{esc(nm)}</a></h3>'
                  + (f'<p class="vnote">{esc(p["name"])}</p>' if p.get("name_en") else "")
                  + (f'<div class="vchips">{chips}</div>' if chips else "")
                  + (f'<p class="vaccess">{esc(p["station"].replace("（座標からの算出）", " (estimated from coordinates)"))}</p>'
                     if p.get("station") else "")
                  + f'<p class="plinks">{official}</p>'
                  + (f'<p class="psrc">{" / ".join(meta)}</p>' if meta else "") + '</article>')
    ld = json.dumps({"@context": "https://schema.org", "@type": "CollectionPage", "name": title,
                     "description": desc, "url": url,
                     "about": {"@type": "AdministrativeArea", "name": full_name}}, ensure_ascii=False)
    extra = (f'<script type="application/ld+json">{ld}</script>'
             f'<link rel="alternate" hreflang="ja" href="{ja_url}">'
             f'<link rel="alternate" hreflang="en" href="{url}">'
             f'<link rel="alternate" hreflang="x-default" href="{ja_url}">')
    nav = """<nav class="nav">
  <a href="/" class="nav-logo">Terroir HUB</a>
  <a href="/business/area/" class="nav-cta">For regions</a>
</nav>"""
    return head(title, desc, url, '<meta name="robots" content="index,follow,max-image-preview:large">',
                extra, nav) + f"""
<div class="crumb"><a href="/">Home</a> › <a href="/area/">Areas</a> › {esc(city_en)}</div>
<header class="hero"><div class="inner">
  <div class="eyebrow">Terroir of {esc(city_en)}</div>
  <h1>{esc(city_en)}, {esc(pref_en)}</h1>
  <p class="lead sub">{esc(full_name)}</p>
  <p class="lead">{esc(tx.get("intro_en",""))}</p>
  <p class="enlink"><a href="{ja_url}">日本語ページ →</a></p>
</div></header>
<section><div class="inner"><h2>Local makers<span>{len(uniq)} listed</span></h2>
  <p class="sec-lead">Compiled from each producer's official information. Fields we could not verify are left out.
  Visiting conditions change, so please check the official site before you go.</p>
  <div class="vgrid">{cards}</div></div></section>
<div class="note"><div class="note-in">
  <p>Listings are based on official sources, with the source and last-checked date shown for each producer.
  Terroir HUB does not sell alcohol and does not accept furusato tax donations.</p>
  <p>Corrections are welcome at <a href="https://www.terroirhub.com/listing-update/">this form</a>.</p>
</div></div>
<footer class="foot"><div class="foot-logo">Terroir HUB</div>
  <p>Japanese terroir and its makers, from verified primary sources. Operated by FOMUS LLC.</p></footer>
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
        for (ed, etx, euniq, envisit) in EN_QUEUE:
            ed_dir = os.path.join(OUT, "en", ed["pref_slug"], ed["slug"])
            os.makedirs(ed_dir, exist_ok=True)
            open(os.path.join(ed_dir, "index.html"), "w", encoding="utf-8").write(
                render_city_en(ed, etx, euniq, envisit))
        EN_QUEUE.clear()
        print(f'  {d["pref"]}{d["city"]}: {d["total"]}件 → /area/{d["pref_slug"]}/{d["slug"]}/')
    if areas:
        os.makedirs(OUT, exist_ok=True)
        open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(render_index(areas))
        print(f'一覧: /area/（{len(areas)}地域）')


if __name__ == "__main__":
    main()
