#!/usr/bin/env python3
"""
ポータル統合ふるさと納税ハブを生成（terroirhub.com/furusato/index.html）。
5ジャンル（日本酒・ワイン・焼酎・ウイスキー・リキュール）を横断する最上位ページ。
各ジャンルの返礼品(楽天ふるさと納税)を抜粋表示し、ジャンル別ハブ→県別→蔵へ送客するSEOトピッククラスタの頂点。
ASP(ふるなび/さとふる)は scripts/asp_config.json にアフィリURLが入っていればボタンを点灯。
"""
import json, glob, os, html

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # Portal-terroir/
ROOT = os.path.dirname(BASE)                                          # テロワールハブ　総合/
OUT = os.path.join(BASE, "furusato", "index.html")
DOMAIN = "www.terroirhub.com"

# ジャンル定義: dir=データ元ディレクトリ, sub=サイト内サブパス, furusato=ジャンル別ハブURL(無=準備中)
GENRES = [
    {"key": "sake",    "name": "日本酒",     "color": "#B8452A",
     "dir": "TerriorHUB　sake", "items_sub": "sake",
     "site": "https://sake.terroirhub.com", "furusato": "https://sake.terroirhub.com/sake/furusato/"},
    {"key": "wine",    "name": "ワイン",     "color": "#7A1F2B",
     "dir": "terroirHUB wine", "items_sub": "wine",
     "site": "https://wine.terroirhub.com", "furusato": "https://wine.terroirhub.com/wine/furusato/"},
    {"key": "shochu",  "name": "焼酎・泡盛", "color": "#8B5E3C",
     "dir": "terroirHUB 焼酎", "items_sub": "shochu",
     "site": "https://shochu.terroirhub.com", "furusato": None},
    {"key": "whisky",  "name": "ウイスキー", "color": "#2D5F3F",
     "dir": "terroirHUB whisky", "items_sub": "whisky",
     "site": "https://whisky.terroirhub.com", "furusato": "https://whisky.terroirhub.com/whisky/furusato/"},
    {"key": "liqueur", "name": "リキュール", "color": "#3A7A9E",
     "dir": "terroirHUB liqueur", "items_sub": "liqueur",
     "site": "https://liqueur.terroirhub.com", "furusato": None},
]


def esc(s):
    return html.escape(str(s or ""), quote=True)


def load_asp():
    p = os.path.join(BASE, "scripts", "asp_config.json")
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}


def featured_items(g, limit=8):
    """ジャンルの rakuten_items.json から【ふるさと納税】返礼品を抜粋"""
    path = os.path.join(ROOT, g["dir"], g["items_sub"], "rakuten_items.json")
    if not os.path.exists(path):
        return [], 0
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        return [], 0
    items, seen = [], set()
    total = 0
    for wid, grp in d.items():
        for it in grp.get("items", []):
            nm = it.get("name", "")
            if not it.get("image") or "ふるさと納税" not in nm:
                continue
            total += 1
            key = it.get("url") or nm
            if key in seen:
                continue
            seen.add(key)
            if len(items) < limit:
                items.append(it)
    return items, total


def clean_name(nm):
    import re
    s = re.sub(r'^[【\[]?\s*ふるさと納税\s*[】\]]?\s*', '', nm)
    s = re.sub(r'\s*(御祝|御礼|母の日|父の日|敬老の日|御中元|御歳暮|御年賀|内祝|出産内祝|ギフト|プレゼント|贈り物|人気|寿|送料無料).*$', '', s)
    return s.strip() or nm


def asp_buttons(asp, genre_key):
    btns = ""
    for site in ("furunavi", "satofuru"):
        cfg = asp.get(site, {})
        if not cfg.get("enabled"):
            continue
        url = (cfg.get("search_url_by_genre", {}) or {}).get(genre_key, "")
        if not url:
            continue
        cls = "asp-furunavi" if site == "furunavi" else "asp-satofuru"
        btns += f'<a class="asp-btn {cls}" href="{esc(url)}" target="_blank" rel="nofollow sponsored noopener">{esc(cfg.get("label", site))}で探す</a>'
    return btns


def build():
    asp = load_asp()
    grand_total = 0
    genre_html = ""
    jsonld_items = []
    pos = 0

    for g in GENRES:
        items, total = featured_items(g)
        grand_total += total
        cards = ""
        for it in items:
            nm = clean_name(it["name"])
            cards += f'''
          <a class="pcard" href="{esc(it['url'])}" target="_blank" rel="nofollow sponsored noopener">
            <span class="pcard-img"><img src="{esc(it['image'])}" alt="{esc(nm)}" loading="lazy"></span>
            <span class="pcard-name">{esc(nm)}</span>
            <span class="pcard-buy">楽天ふるさと納税</span>
          </a>'''
            if pos < 24:
                pos += 1
                jsonld_items.append({"@type": "ListItem", "position": pos,
                                     "name": nm, "image": it["image"], "url": it["url"]})
        aspb = asp_buttons(asp, g["key"])
        if g["furusato"] and items:
            cta = f'<a class="genre-cta" href="{esc(g["furusato"])}">{esc(g["name"])}のふるさと納税を見る（{total}件）→</a>'
            status = f'<span class="genre-count">{total}件</span>'
            body = f'<div class="pgrid">{cards}</div><div class="genre-actions">{cta}{aspb}</div>'
        elif items:  # データはあるがジャンル別ハブ未公開
            cta = f'<a class="genre-cta" href="{esc(g["site"])}">{esc(g["name"])}のサイトへ →</a>'
            status = f'<span class="genre-count">{total}件・特集ページ準備中</span>'
            body = f'<div class="pgrid">{cards}</div><div class="genre-actions">{cta}{aspb}</div>'
        else:  # データなし
            status = '<span class="genre-soon">近日公開</span>'
            body = (f'<p class="genre-empty">{esc(g["name"])}のふるさと納税特集は準備中です。'
                    f'<a href="{esc(g["site"])}">{esc(g["name"])}のサイトを見る →</a></p>{("<div class=\"genre-actions\">"+aspb+"</div>") if aspb else ""}')

        genre_html += f'''
      <section class="genre-block" id="g-{g['key']}" style="--gc:{g['color']}">
        <div class="genre-head">
          <h2 class="genre-title">{esc(g['name'])}のふるさと納税 {status}</h2>
        </div>
        {body}
      </section>'''

    n_live = sum(1 for g in GENRES if featured_items(g)[1] > 0)

    faqs = [
        ("お酒のふるさと納税はどこで選べますか？",
         "Terroir HUBでは日本酒・ワイン・焼酎・ウイスキー・リキュールのふるさと納税返礼品を横断的にまとめています。ジャンル別ページからさらに都道府県・蔵元単位で選べます。"),
        ("ふるさと納税でアフィリエイトの返礼品は使えますか？",
         "本ページの返礼品リンクは楽天ふるさと納税に対応しています。ふるなび・さとふる等の他サイトも順次併記し、最もお得な寄付先を選べるようにしています。"),
        ("控除を受けるには何が必要ですか？",
         "確定申告、またはワンストップ特例制度（確定申告不要な給与所得者で寄付先が年間5自治体以内）の申請が必要です。控除上限額は年収・家族構成で変わるため、各サイトのシミュレーターでご確認ください。"),
        ("返礼品や寄付額は変わりますか？",
         "返礼品・寄付額・在庫・取扱自治体は時期により変動します。最新情報は各返礼品ページでご確認ください。"),
    ]
    faq_html = "".join(f'<div class="faq-item"><dt>{esc(q)}</dt><dd>{esc(a)}</dd></div>' for q, a in faqs)

    desc = (f"日本酒・ワイン・焼酎・ウイスキー・リキュールのふるさと納税返礼品を横断検索。"
            f"全国の蔵元・ワイナリーの返礼品を産地別にまとめ、寄付で地域の造り手を応援できます。楽天ふるさと納税対応。")
    url = f"https://{DOMAIN}/furusato/"
    jsonld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Terroir HUB", "item": f"https://{DOMAIN}/"},
            {"@type": "ListItem", "position": 2, "name": "ふるさと納税", "item": url}]},
        {"@type": "CollectionPage", "name": "お酒のふるさと納税 | Terroir HUB", "description": desc, "url": url},
        {"@type": "ItemList", "name": "お酒のふるさと納税返礼品", "itemListElement": jsonld_items},
        {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]},
    ]}

    page = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>お酒のふるさと納税 — 日本酒・ワイン・焼酎・ウイスキー | Terroir HUB</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:title" content="お酒のふるさと納税｜日本酒・ワイン・焼酎・ウイスキー — Terroir HUB">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@500;600;700&family=Noto+Sans+JP:wght@300;400;500;700&family=Inter:wght@500;600&display=swap" rel="stylesheet">
<script type="application/ld+json">
{json.dumps(jsonld, ensure_ascii=False, indent=1)}
</script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#FAFAF7;--surface:#F3F0EA;--border:rgba(0,0,0,0.08);--text:#1a1816;--muted:rgba(26,24,22,0.62);--gold:#996E1A;--fd:'Shippori Mincho',serif;--fb:'Noto Sans JP',sans-serif;--fn:'Inter',sans-serif}}
html{{scroll-behavior:smooth;-webkit-font-smoothing:antialiased}}
body{{background:var(--bg);color:var(--text);font-family:var(--fb);line-height:1.8;overflow-x:hidden}}
a{{color:inherit;text-decoration:none}}
img{{display:block;max-width:100%}}
.nav{{position:fixed;top:0;left:0;right:0;z-index:100;height:64px;display:flex;align-items:center;justify-content:space-between;padding:0 clamp(1.2rem,5vw,4rem);background:rgba(250,250,247,0.92);backdrop-filter:blur(20px);border-bottom:1px solid var(--border)}}
.nav-logo{{font-family:var(--fd);font-size:1.2rem;font-weight:700;letter-spacing:0.08em}}
.nav-links{{display:none;gap:1.8rem;align-items:center}}
@media(min-width:980px){{.nav-links{{display:flex}}}}
.nav-link{{font-size:0.72rem;font-weight:500;letter-spacing:0.16em;text-transform:uppercase;color:var(--muted)}}
.nav-link:hover{{color:var(--text)}}
.nav-link.cur{{color:var(--gold)}}
.hero{{margin-top:64px;padding:clamp(3.5rem,8vw,6rem) clamp(1.4rem,5vw,5rem) clamp(2.5rem,5vw,4rem);background:#fff;border-bottom:1px solid var(--border)}}
.hero-inner{{max-width:1080px;margin:0 auto}}
.eyebrow{{font-family:var(--fn);font-size:0.62rem;font-weight:600;letter-spacing:0.32em;text-transform:uppercase;color:var(--gold);margin-bottom:1.1rem}}
.hero h1{{font-family:var(--fd);font-size:clamp(1.9rem,4.6vw,3.1rem);font-weight:700;letter-spacing:0.02em;line-height:1.35;margin-bottom:1.3rem}}
.hero p{{font-size:clamp(0.96rem,1.4vw,1.1rem);color:var(--text);max-width:680px;line-height:2}}
.hstats{{display:flex;gap:2.2rem;margin-top:2rem;flex-wrap:wrap;padding-top:1.4rem;border-top:1px solid var(--border)}}
.hstat-n{{font-family:var(--fn);font-size:clamp(1.5rem,2.4vw,1.9rem);font-weight:600;line-height:1}}
.hstat-l{{font-size:0.82rem;color:var(--muted);margin-top:4px}}
.steps{{max-width:1080px;margin:0 auto;padding:clamp(2.2rem,4vw,3rem) clamp(1.4rem,5vw,5rem) 0;display:grid;grid-template-columns:repeat(3,1fr);gap:1rem}}
@media(max-width:760px){{.steps{{grid-template-columns:1fr}}}}
.step{{background:#fff;border:1px solid var(--border);padding:1.4rem 1.5rem}}
.step b{{font-family:var(--fn);color:var(--gold);font-size:0.8rem;letter-spacing:0.1em}}
.step h3{{font-family:var(--fd);font-size:1.05rem;margin:0.5rem 0 0.4rem}}
.step p{{font-size:0.86rem;color:var(--muted);line-height:1.75}}
.sim{{max-width:1080px;margin:1.4rem auto 0;padding:0 clamp(1.4rem,5vw,5rem)}}
.sim-in{{background:#fff;border:1px solid var(--border);padding:1.3rem 1.6rem;display:flex;align-items:center;gap:1.2rem;flex-wrap:wrap}}
.sim-in p{{flex:1;min-width:240px;font-size:0.9rem;color:var(--text)}}
.sim-in a{{font-family:var(--fn);font-size:0.78rem;font-weight:600;letter-spacing:0.08em;color:#fff;background:var(--gold);padding:0.7rem 1.5rem;white-space:nowrap}}
.wrap{{max-width:1180px;margin:0 auto;padding:clamp(2.5rem,5vw,4rem) clamp(1.4rem,5vw,5rem) 0}}
.genre-block{{margin-bottom:clamp(2.6rem,5vw,3.6rem);padding-left:18px;border-left:3px solid var(--gc)}}
.genre-head{{margin-bottom:1.2rem}}
.genre-title{{font-family:var(--fd);font-size:clamp(1.3rem,2.4vw,1.7rem);font-weight:700;display:flex;align-items:baseline;gap:0.7rem;flex-wrap:wrap}}
.genre-count{{font-family:var(--fn);font-size:0.8rem;font-weight:500;color:var(--gc)}}
.genre-soon{{font-family:var(--fn);font-size:0.74rem;letter-spacing:0.1em;color:var(--muted);border:1px solid var(--border);padding:3px 10px}}
.pgrid{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem}}
@media(max-width:900px){{.pgrid{{grid-template-columns:repeat(2,1fr)}}}}
.pcard{{background:#fff;border:1px solid var(--border);display:flex;flex-direction:column;transition:box-shadow .25s,transform .25s}}
.pcard:hover{{box-shadow:0 12px 30px rgba(40,30,20,.12);transform:translateY(-3px)}}
.pcard-img{{aspect-ratio:1/1;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden}}
.pcard-img img{{width:100%;height:100%;object-fit:contain;padding:12px}}
.pcard-name{{font-size:0.82rem;line-height:1.55;color:var(--text);padding:11px 13px 0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;flex:1}}
.pcard-buy{{font-family:var(--fn);font-size:0.66rem;font-weight:600;letter-spacing:0.06em;color:#fff;background:#BF0000;text-align:center;padding:8px 0;margin:11px 13px 13px;border-radius:3px}}
.genre-actions{{display:flex;gap:0.7rem;flex-wrap:wrap;align-items:center;margin-top:1.2rem}}
.genre-cta{{font-family:var(--fn);font-size:0.82rem;font-weight:600;letter-spacing:0.04em;color:#fff;background:var(--gc);padding:0.7rem 1.4rem}}
.genre-cta:hover{{opacity:0.9}}
.asp-btn{{font-family:var(--fn);font-size:0.78rem;font-weight:600;padding:0.65rem 1.2rem;border:1px solid var(--border)}}
.asp-furunavi{{background:#fff;color:#e8520e;border-color:#e8520e}}
.asp-satofuru{{background:#fff;color:#0aa;border-color:#0aa}}
.genre-empty{{font-size:0.9rem;color:var(--muted)}}
.genre-empty a{{color:var(--gold);font-weight:500}}
.faqsec{{max-width:900px;margin:clamp(2rem,4vw,3rem) auto 0;padding:0 clamp(1.4rem,5vw,5rem)}}
.faqsec h2{{font-family:var(--fd);font-size:1.5rem;margin-bottom:1.2rem}}
.faq{{background:#fff;border:1px solid var(--border);padding:1.8rem}}
.faq-item{{padding-bottom:1.2rem;margin-bottom:1.2rem;border-bottom:1px solid var(--border)}}
.faq-item:last-child{{padding-bottom:0;margin-bottom:0;border-bottom:none}}
.faq-item dt{{font-weight:600;margin-bottom:0.4rem}}
.faq-item dd{{font-size:0.9rem;color:var(--muted);line-height:1.85}}
.note{{max-width:900px;margin:1.6rem auto 0;padding:0 clamp(1.4rem,5vw,5rem);font-size:0.72rem;color:var(--muted);line-height:1.8}}
.footer{{background:#1a1816;color:rgba(255,255,255,0.45);margin-top:clamp(3rem,6vw,5rem);padding:3rem clamp(1.4rem,5vw,5rem) 2rem;text-align:center}}
.footer-logo{{font-family:var(--fd);font-size:1.4rem;color:#fff;font-weight:700;margin-bottom:1rem}}
.footer-nav{{display:flex;justify-content:center;flex-wrap:wrap;gap:1.2rem;margin-bottom:1.4rem;font-size:0.8rem}}
.footer-nav a{{color:rgba(255,255,255,0.6)}}.footer-nav a:hover{{color:#fff}}
.footer-c{{font-size:0.7rem;color:rgba(255,255,255,0.3)}}
</style>
</head>
<body>
<nav class="nav">
  <a href="/" class="nav-logo">Terroir HUB</a>
  <div class="nav-links">
    <a href="https://sake.terroirhub.com" class="nav-link">日本酒</a>
    <a href="https://wine.terroirhub.com" class="nav-link">ワイン</a>
    <a href="https://shochu.terroirhub.com" class="nav-link">焼酎</a>
    <a href="https://whisky.terroirhub.com" class="nav-link">ウイスキー</a>
    <a href="https://liqueur.terroirhub.com" class="nav-link">リキュール</a>
    <a href="/furusato/" class="nav-link cur">ふるさと納税</a>
  </div>
</nav>

<header class="hero"><div class="hero-inner">
  <div class="eyebrow">FURUSATO TAX — お酒のふるさと納税</div>
  <h1>寄付して、日本の造り手を応援しよう。</h1>
  <p>日本酒・ワイン・焼酎・ウイスキー・リキュール。Terroir HUBが全国の蔵元・ワイナリーのふるさと納税返礼品を横断的にまとめました。実質自己負担2,000円で、好きなお酒を受け取りながら産地と造り手を直接応援できます。</p>
  <div class="hstats">
    <div><div class="hstat-n">{grand_total:,}</div><div class="hstat-l">返礼品（楽天ふるさと納税）</div></div>
    <div><div class="hstat-n">{n_live}</div><div class="hstat-l">対応ジャンル</div></div>
  </div>
</div></header>

<section class="steps">
  <div class="step"><b>STEP 1</b><h3>控除上限を確認</h3><p>年収・家族構成で寄付できる上限額が決まります。各サイトのシミュレーターで確認。</p></div>
  <div class="step"><b>STEP 2</b><h3>好きなお酒を選ぶ</h3><p>ジャンル・産地・蔵元から選んで寄付。返礼品としてお酒が届きます。</p></div>
  <div class="step"><b>STEP 3</b><h3>控除を申請</h3><p>ワンストップ特例（5自治体以内）または確定申告で実質自己負担2,000円に。</p></div>
</section>
<div class="sim"><div class="sim-in">
  <p>💡 まずは控除上限額をチェック。年収と家族構成を入れるだけで、いくらまで寄付できるか分かります。</p>
  <a href="https://event.rakuten.co.jp/furusato/simulation/" target="_blank" rel="noopener">控除シミュレーター ›</a>
</div></div>

<main class="wrap">
  {genre_html}
</main>

<section class="faqsec"><h2>お酒のふるさと納税 よくある質問</h2><dl class="faq">{faq_html}</dl></section>
<p class="note">※ 返礼品・寄付額・在庫・取扱自治体は時期により変動します。本ページは楽天ふるさと納税の情報をもとに構成しており、最新の内容・正確な控除上限は各返礼品ページおよび各自治体・ふるさと納税サイトでご確認ください。控除には確定申告またはワンストップ特例申請が必要です。20歳未満の飲酒・お酒の購入は法律で禁止されています。Terroir HUBはお酒の販売を行っていません。</p>

<footer class="footer">
  <div class="footer-logo">Terroir HUB</div>
  <nav class="footer-nav">
    <a href="/">ホーム</a>
    <a href="https://sake.terroirhub.com">日本酒</a>
    <a href="https://wine.terroirhub.com">ワイン</a>
    <a href="/furusato/">ふるさと納税</a>
    <a href="/community.html">コミュニティ</a>
  </nav>
  <p class="footer-c">&copy; 2026 合同会社FOMUS — Terroir HUB</p>
</footer>
</body>
</html>
'''
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"生成: {OUT}")
    print(f"横断返礼品 {grand_total}件 / 対応ジャンル {n_live}")


if __name__ == "__main__":
    build()
