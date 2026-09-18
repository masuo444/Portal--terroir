#!/usr/bin/env python3
"""
wine / shochu / whisky の「見学できる◯◯」ガイドを生成する。

sake 側（TerriorHUB　sake/scripts/generate_visit_guides.py）と同じ考え方:
  - 公式サイトに記載のある項目だけを出す。無い項目は行ごと出さない
  - 蔵ごとに出典URLと最終確認日を必ず表示する
  - 見学を受け付けている蔵が3件未満の県は、県ページを作らない（薄いページを作らない）

sake と違い、各ジャンルは件数が少ないため「全国1枚＋件数の多い県」という構成にする。

出力:
  <各リポジトリ>/<genre>/visit/index.html        全国
  <各リポジトリ>/<genre>/visit/<県>/index.html    3件以上の県
  <各リポジトリ>/<genre>/visit/visit.css          共通スタイル（サイトの差し色に合わせる）

使い方:
  python3 scripts/generate_visit_guides_genre.py            # 全ジャンル
  python3 scripts/generate_visit_guides_genre.py wine       # 指定ジャンルのみ
"""
import os, re, sys, json, glob, html, datetime, collections, shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
TODAY = datetime.date.today().isoformat()
MIN_PER_PREF = 3
SAKE_CSS = os.path.join(ROOT, "TerriorHUB　sake", "sake", "visit", "visit.css")

GENRES = {
    "wine": dict(repo="terroirHUB wine", path="wine", domain="wine.terroirhub.com",
                 name="日本ワイン", unit="ワイナリー", maker="ワイナリー",
                 data="terroirHUB wine/data/data_*_wineries.json", suffix="_wineries.json",
                 accent="#722F37", brandsub="WINE",
                 nav=[("/wine/search/", "ワイナリー検索"), ("/wine/visit/", "見学できるワイナリー"),
                      ("/wine/guide/", "ガイド")]),
    "shochu": dict(repo="terroirHUB 焼酎", path="shochu", domain="shochu.terroirhub.com",
                   name="焼酎・泡盛", unit="蔵", maker="蔵",
                   data="terroirHUB 焼酎/data/data_*_distilleries.json", suffix="_distilleries.json",
                   accent="#8B5E3C", brandsub="SHOCHU",
                   nav=[("/shochu/visit/", "見学できる蔵"), ("/shochu/guide/", "ガイド")]),
    "whisky": dict(repo="terroirHUB whisky", path="whisky", domain="whisky.terroirhub.com",
                   name="ジャパニーズウイスキー", unit="蒸溜所", maker="蒸溜所",
                   data="terroirHUB whisky/data/data_*_distilleries.json", suffix="_distilleries.json",
                   accent="#6B4423", brandsub="WHISKY",
                   nav=[("/whisky/visit/", "見学できる蒸溜所"), ("/whisky/guide/", "ガイド")]),
}

PREF = {"hokkaido": "北海道", "aomori": "青森県", "iwate": "岩手県", "miyagi": "宮城県", "akita": "秋田県",
        "yamagata": "山形県", "fukushima": "福島県", "ibaraki": "茨城県", "tochigi": "栃木県", "gunma": "群馬県",
        "saitama": "埼玉県", "chiba": "千葉県", "tokyo": "東京都", "kanagawa": "神奈川県", "niigata": "新潟県",
        "toyama": "富山県", "ishikawa": "石川県", "fukui": "福井県", "yamanashi": "山梨県", "nagano": "長野県",
        "gifu": "岐阜県", "shizuoka": "静岡県", "aichi": "愛知県", "mie": "三重県", "shiga": "滋賀県",
        "kyoto": "京都府", "osaka": "大阪府", "hyogo": "兵庫県", "nara": "奈良県", "wakayama": "和歌山県",
        "tottori": "鳥取県", "shimane": "島根県", "okayama": "岡山県", "hiroshima": "広島県", "yamaguchi": "山口県",
        "tokushima": "徳島県", "kagawa": "香川県", "ehime": "愛媛県", "kochi": "高知県", "fukuoka": "福岡県",
        "saga": "佐賀県", "nagasaki": "長崎県", "kumamoto": "熊本県", "oita": "大分県", "miyazaki": "宮崎県",
        "kagoshima": "鹿児島県", "okinawa": "沖縄県"}

REGIONS = [("北海道・東北", ["hokkaido", "aomori", "iwate", "miyagi", "akita", "yamagata", "fukushima"]),
           ("関東", ["ibaraki", "tochigi", "gunma", "saitama", "chiba", "tokyo", "kanagawa"]),
           ("中部", ["niigata", "toyama", "ishikawa", "fukui", "yamanashi", "nagano", "gifu", "shizuoka", "aichi"]),
           ("近畿", ["mie", "shiga", "kyoto", "osaka", "hyogo", "nara", "wakayama"]),
           ("中国・四国", ["tottori", "shimane", "okayama", "hiroshima", "yamaguchi",
                        "tokushima", "kagawa", "ehime", "kochi"]),
           ("九州・沖縄", ["fukuoka", "saga", "nagasaki", "kumamoto", "oita", "miyazaki", "kagoshima", "okinawa"])]

STATUS = {"open": "見学可", "paused": "見学休止中", "closed": "見学不可", "inquire": "要問い合わせ"}
RES = {"required": "要予約", "recommended": "予約推奨", "not_required": "予約不要", "inquire": "要問い合わせ"}
TAST = {"paid": "あり（有料）", "free": "あり（無料）", "available": "あり", "none": "なし"}
ENG = {"tour": "英語ツアーあり", "materials": "英語資料あり", "none": "日本語のみ"}


def esc(s):
    return html.escape(str(s), quote=True) if s else ""


def short(s, n=20):
    s = (s or "").strip()
    return esc(s) if len(s) <= n else esc(s[:n]) + "…"


def load(g):
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, g["data"]))):
        pref = os.path.basename(f).replace("data_", "").replace(g["suffix"], "")
        if pref not in PREF:
            continue
        for b in json.load(open(f, encoding="utf-8")):
            v = b.get("visit_info") or {}
            if v.get("status") != "open" or not b.get("id"):
                continue
            b["_pref"] = pref
            out.append(b)
    return out


def badges(b):
    v = b["visit_info"]
    out = [f'<span class="badge on">{STATUS["open"]}</span>']
    if v.get("reservation") in RES:
        cls = "badge on" if v["reservation"] == "not_required" else "badge"
        out.append(f'<span class="{cls}">{RES[v["reservation"]]}</span>')
    if v.get("tasting") in ("free", "paid", "available"):
        out.append(f'<span class="badge">試飲{TAST[v["tasting"]]}</span>')
    if re.fullmatch(r"(見学)?無料", (v.get("fee") or "").strip()):
        out.append('<span class="badge free">無料</span>')
    if v.get("english") in ("tour", "materials"):
        out.append(f'<span class="badge en">{ENG[v["english"]]}</span>')
    if v.get("shop"):
        out.append('<span class="badge">直売所</span>')
    return '<div class="badges">' + "".join(out) + "</div>"


def card(b, g, show_pref=False):
    v = b["visit_info"]
    pref = b["_pref"]
    where = "・".join(x for x in [PREF[pref] if show_pref else "", b.get("area") or ""] if x)
    rows = []
    if v.get("facility"):
        rows.append(("見学施設", esc(v["facility"])))
    if v.get("fee"):
        rows.append(("料金", esc(v["fee"])))
    if v.get("duration"):
        rows.append(("所要時間", esc(v["duration"])))
    if b.get("founded"):
        era = f'（{b["founded_era"]}）' if b.get("founded_era") else ""
        rows.append(("創業", f'{esc(b["founded"])}年{esc(era)}'))
    dl = '<dl class="dl">' + "".join(f"<dt>{k}</dt><dd>{x}</dd>" for k, x in rows) + "</dl>" if rows else ""
    note = f'<div class="note">{esc(v["notes_ja"])}</div>' if v.get("notes_ja") else ""
    acts = []
    if v.get("reservation_url"):
        acts.append(f'<a class="btn" href="{esc(v["reservation_url"])}" target="_blank" '
                    f'rel="noopener">公式サイトで見学を予約する →</a>')
    acts.append(f'<a class="btn ghost" href="/{g["path"]}/{pref}/{b["id"]}.html">'
                f'{g["maker"]}の詳細を見る →</a>')
    src = ""
    if v.get("source"):
        src = (f'<div class="src">出典: <a href="{esc(v["source"])}" target="_blank" rel="noopener">'
               f'{esc(v["source"][:72])}</a>　最終確認日: {esc(v.get("last_checked", ""))}</div>')
    brand = f'<span class="brand">{esc(b["brand"])}</span>' if b.get("brand") else ""
    addr = f'　{esc(b["address"])}' if b.get("address") else ""
    return (f'<article class="card" id="{esc(b["id"])}">\n<h3>{esc(b["name"])}{brand}</h3>\n'
            f'<div class="where">{esc(where)}{addr}</div>\n{badges(b)}{dl}{note}'
            f'<div class="actions">{"".join(acts)}</div>{src}\n</article>')


def table(rows, show_pref=False):
    head = ["名称"] + (["都道府県"] if show_pref else ["所在地"]) + ["予約", "試飲", "料金", "所要時間"]
    out = ["<thead><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>"]
    for b in rows:
        v = b["visit_info"]
        cells = [f'<a href="#{esc(b["id"])}">{esc(b["name"])}</a>',
                 esc(PREF[b["_pref"]]) if show_pref else (esc(b.get("area")) or "—"),
                 RES.get(v.get("reservation"), "—"), TAST.get(v.get("tasting"), "—"),
                 short(v.get("fee")) or "—", short(v.get("duration")) or "—"]
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    out.append("</tbody>")
    return '<div class="tablewrap"><table>' + "".join(out) + "</table></div>"


def chips(rows, unit):
    v = [b["visit_info"] for b in rows]
    c = [f"見学を受け付けている{unit} <b>{len(rows)}</b>"]
    for label, test in [("予約不要", lambda k: k.get("reservation") == "not_required"),
                        ("試飲あり", lambda k: k.get("tasting") in ("free", "paid", "available")),
                        ("無料の記載", lambda k: "無料" in (k.get("fee") or "")),
                        ("英語対応", lambda k: k.get("english") in ("tour", "materials")),
                        ("直売所あり", lambda k: k.get("shop"))]:
        n = sum(1 for k in v if test(k))
        if n:
            c.append(f"{label} <b>{n}</b>")
    return '<div class="sum">' + "".join(f"<span>{x}</span>" for x in c) + "</div>"


def faq(rows, g, where):
    v = [b["visit_info"] for b in rows]
    qa = [(f"{where}で見学できる{g['unit']}は何件ありますか？",
           f"Terroir HUB では、{where}で見学を受け付けている{g['unit']}を{len(rows)}件収録しています。"
           f"いずれも各{g['maker']}の公式サイトの記載にもとづくもので、件ごとに出典と最終確認日を記載しています。")]
    nr = [b for b in rows if b["visit_info"].get("reservation") == "not_required"]
    qa.append(("予約なしで行けますか？",
               (f"公式サイトで予約不要と案内しているのが{len(nr)}件あります（"
                + "、".join(esc(b["name"]) for b in nr[:5]) + "）。" if nr else
                f"{where}では、公式サイトに「予約不要」と明記しているものを確認できていません。"
                f"各{g['maker']}の予約方法をご確認ください。")))
    en = [b for b in rows if b["visit_info"].get("english") in ("tour", "materials")]
    if en:
        qa.append(("英語で案内してもらえますか？",
                   f"英語ツアーまたは英語資料の記載があるのが{len(en)}件あります（"
                   + "、".join(esc(b["name"]) for b in en[:5]) + "）。"))
    dates = sorted(x.get("last_checked", "") for x in v if x.get("last_checked"))
    if dates:
        qa.append(("掲載情報はいつ時点のものですか？",
                   f"各公式サイトを{dates[0]}〜{dates[-1]}に確認した内容です。"
                   "受付状況は変わることがあるため、訪問前に必ず公式情報をご確認ください。"))
    return qa


def faq_html(qa):
    return "".join(f'<div class="faq"><h3>{q}</h3><p>{a}</p></div>' for q, a in qa)


def jsonld(g, url, name, desc, crumbs, rows, qa):
    items = []
    for i, b in enumerate(rows, 1):
        o = {"@type": "TouristAttraction", "name": b["name"],
             "url": f'https://{g["domain"]}/{g["path"]}/{b["_pref"]}/{b["id"]}.html'}
        if b.get("address"):
            o["address"] = {"@type": "PostalAddress", "addressRegion": PREF[b["_pref"]],
                            "streetAddress": b["address"], "addressCountry": "JP"}
        if b.get("url"):
            o["sameAs"] = b["url"]
        items.append({"@type": "ListItem", "position": i, "item": o})
    graph = [{"@type": "BreadcrumbList", "itemListElement": [
                  {"@type": "ListItem", "position": i + 1, "name": n, "item": u}
                  for i, (n, u) in enumerate(crumbs)]},
             {"@type": "ItemList", "name": name, "url": url, "description": desc,
              "numberOfItems": len(rows), "itemListElement": items},
             {"@type": "FAQPage", "mainEntity": [
                 {"@type": "Question", "name": q,
                  "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", a)}}
                 for q, a in qa]}]
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)


def page(g, url, title, desc, crumbs, body, ld):
    nav = "".join(f'<a href="{h}">{t}</a>' for h, t in g["nav"])
    crumb = " › ".join(n if i == len(crumbs) - 1 else f'<a href="{u}">{n}</a>'
                       for i, (n, u) in enumerate(crumbs))
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
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Zen+Old+Mincho:wght@400;700&family=Noto+Serif+JP:wght@200;300;400&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/{g['path']}/visit/visit.css">
<script type="application/ld+json">{ld}</script>
</head>
<body>
<nav class="nav">
  <a class="nav-brand" href="/"><span class="nav-logo">Terroir HUB</span><span class="nav-logo-sub">{g['brandsub']}</span></a>
  <div class="nav-links">{nav}<a href="https://www.terroirhub.com/business/">事業者向け</a></div>
</nav>
<main class="wrap">
<div class="crumb">{crumb}</div>
{body}
</main>
<footer>
  <div>見学情報は各{g['maker']}の公式サイトの記載にもとづきます。受付状況・料金・時間は変更されることがあるため、訪問前に必ず公式情報をご確認ください。</div>
  <div><a href="https://www.terroirhub.com/listing-update/">掲載情報の修正・写真のご提供</a>　/　<a href="/{g['path']}/visit/">見学できる{g['unit']} 全国一覧</a></div>
  <div>© 2026 合同会社FOMUS — Terroir HUB {g['brandsub']}</div>
</footer>
</body>
</html>
"""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(text)


def build(gkey):
    g = GENRES[gkey]
    rows = load(g)
    if not rows:
        print(f"{gkey}: 見学情報のある{g['unit']}がありません")
        return 0
    repo = os.path.join(ROOT, g["repo"])
    outdir = os.path.join(repo, g["path"], "visit")

    # スタイル（sake版をそのまま使い、差し色だけ差し替える）
    css = open(SAKE_CSS, encoding="utf-8").read().replace("#C85A3A", g["accent"])
    write(os.path.join(outdir, "visit.css"), css)

    by_pref = collections.defaultdict(list)
    for b in rows:
        by_pref[b["_pref"]].append(b)
    made = 0

    # 県ページ（3件以上）
    for pref, rs in sorted(by_pref.items()):
        if len(rs) < MIN_PER_PREF:
            continue
        pname = PREF[pref]
        rs = sorted(rs, key=lambda b: (-(1 if b["visit_info"].get("reservation_url") else 0), b["name"]))
        url = f'https://{g["domain"]}/{g["path"]}/visit/{pref}/'
        title = f'{pname}の見学できる{g["unit"]}{len(rs)}件 — 予約・料金・所要時間'
        desc = (f'{pname}で見学を受け付けている{g["unit"]}{len(rs)}件を、公式サイトの記載にもとづいて'
                f'一覧にしました。予約の要否・試飲・料金・所要時間で比較できます。')
        crumbs = [("ホーム", "/"), (f'見学できる{g["unit"]}', f'/{g["path"]}/visit/'), (pname, url)]
        qa = faq(rs, g, pname)
        dates = sorted(b["visit_info"].get("last_checked", "") for b in rs
                       if b["visit_info"].get("last_checked"))
        body = f"""<div class="head">
  <div class="eyebrow">Visits</div>
  <h1>{esc(pname)}の見学できる{g['unit']} {len(rs)}件</h1>
  <p class="lead">{esc(pname)}で見学を受け付けている{g['unit']}を、公式サイトの記載にもとづいて一覧にしました。
  記載を確認できなかった項目は表示していません。</p>
  {chips(rs, g['unit'])}
  <div class="asof">{f"公式サイトの確認日: {dates[0]}〜{dates[-1]}　/　" if dates else ""}ページ更新: {TODAY}</div>
</div>
<h2>一覧で比べる</h2>
{table(rs)}
<h2>{esc(pname)}の見学情報</h2>
{"".join(card(b, g) for b in rs)}
<h2>よくある質問</h2>
{faq_html(qa)}
<h2>関連ページ</h2>
<div class="links">
  <a href="/{g['path']}/visit/">全国の見学できる{g['unit']}</a>
  <a href="/{g['path']}/{pref}/">{esc(pname)}の{g['unit']}一覧</a>
  <a href="https://www.terroirhub.com/terroir/{pref}.html">{esc(pname)}のテロワール</a>
</div>
"""
        write(os.path.join(outdir, pref, "index.html"),
              page(g, url, title, desc, crumbs, body, jsonld(g, url, title, desc, crumbs, rs, qa)))
        made += 1

    # 全国ページ
    allrows = sorted(rows, key=lambda b: (REGIONS.index(next(r for r in REGIONS if b["_pref"] in r[1])),
                                          b["_pref"], b["name"]))
    url = f'https://{g["domain"]}/{g["path"]}/visit/'
    title = f'見学できる{g["name"]}の{g["unit"]} 全国{len(allrows)}件 — 予約・料金・所要時間'
    desc = (f'全国{len(allrows)}件の{g["unit"]}の見学情報を、公式サイトの記載にもとづいて掲載しています。'
            f'予約の要否・試飲・料金・所要時間で比べられます。')
    crumbs = [("ホーム", "/"), (f'見学できる{g["unit"]}', url)]
    qa = faq(allrows, g, "全国")
    prefs = [(p, len(v)) for p, v in sorted(by_pref.items(), key=lambda x: -len(x[1]))]
    plinks = "".join(
        f'<a href="/{g["path"]}/visit/{p}/">{PREF[p]}（{n}）</a>' if n >= MIN_PER_PREF
        else f'<a href="/{g["path"]}/{p}/">{PREF[p]}（{n}）</a>' for p, n in prefs)
    body = f"""<div class="head">
  <div class="eyebrow">Visits</div>
  <h1>見学できる{g['name']}の{g['unit']} 全国{len(allrows)}件</h1>
  <p class="lead">見学を受け付けている{g['unit']}を、公式サイトの記載にもとづいてまとめています。
  予約の要否・試飲・料金・所要時間で比べられ、公式の予約ページがあるものはそのまま予約に進めます。
  記載を確認できなかった項目は載せていません。</p>
  {chips(allrows, g['unit'])}
  <div class="asof">ページ更新: {TODAY}　/　掲載: {len(by_pref)}都道府県</div>
</div>
<h2>都道府県から探す</h2>
<div class="links">{plinks}</div>
<h2>一覧で比べる</h2>
{table(allrows, show_pref=True)}
<h2>{g['unit']}ごとの見学情報</h2>
{"".join(card(b, g, show_pref=True) for b in allrows)}
<h2>よくある質問</h2>
{faq_html(qa)}
<h2>ほかのジャンルの見学情報</h2>
<div class="links">
  <a href="https://sake.terroirhub.com/sake/visit/">見学できる酒蔵（日本酒）</a>
  {"".join(f'<a href="https://{GENRES[k]["domain"]}/{GENRES[k]["path"]}/visit/">見学できる{GENRES[k]["unit"]}（{GENRES[k]["name"]}）</a>' for k in GENRES if k != gkey)}
</div>
"""
    write(os.path.join(outdir, "index.html"),
          page(g, url, title, desc, crumbs, body, jsonld(g, url, title, desc, crumbs, allrows, qa)))
    made += 1
    print(f'{gkey}: {made}ページ（全国1 + 県{made-1}）　掲載{len(allrows)}件 / {len(by_pref)}県')
    return made


def main():
    keys = [a for a in sys.argv[1:] if a in GENRES] or list(GENRES)
    total = sum(build(k) for k in keys)
    print(f"\n合計 {total}ページ")


if __name__ == "__main__":
    main()
