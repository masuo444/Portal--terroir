#!/usr/bin/env python3
"""
wine / shochu / whisky の「見学の予約・料金・所要時間」記事を、収録データの集計から生成する。

sake 版（TerriorHUB　sake/scripts/generate_visit_article.py）と同じ考え方だが、
各ジャンルは母数が小さいので、**サンプルが少ない項目では代表値を出さない**。
  - 金額の中央値は、金額の記載が10件以上あるときだけ出す
  - 件数が0の項目は、その節ごと出さない
推測・ランキング・体験談は書かない（一次情報が無いため）。

出力: <各リポジトリ>/<genre>/blog/visit-guide.html
使い方: python3 scripts/generate_visit_article_genre.py [wine|shochu|whisky]
"""
import os, re, sys, json, glob, html, datetime, collections, statistics

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
TODAY = datetime.date.today().isoformat()
MIN_STAT = 10          # 代表値（中央値）を出してよい最小サンプル数

GENRES = {
    "wine": dict(repo="terroirHUB wine", path="wine", domain="wine.terroirhub.com",
                 name="日本ワイン", unit="ワイナリー", maker="ワイナリー", brandsub="WINE",
                 data="terroirHUB wine/data/data_*_wineries.json", suffix="_wineries.json",
                 total=473, kind="ワイナリー見学"),
    "shochu": dict(repo="terroirHUB 焼酎", path="shochu", domain="shochu.terroirhub.com",
                   name="焼酎・泡盛", unit="蔵", maker="蔵", brandsub="SHOCHU",
                   data="terroirHUB 焼酎/data/data_*_distilleries.json", suffix="_distilleries.json",
                   total=389, kind="蔵見学"),
    "whisky": dict(repo="terroirHUB whisky", path="whisky", domain="whisky.terroirhub.com",
                   name="ジャパニーズウイスキー", unit="蒸溜所", maker="蒸溜所", brandsub="WHISKY",
                   data="terroirHUB whisky/data/data_*_distilleries.json", suffix="_distilleries.json",
                   total=67, kind="蒸溜所見学"),
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

RES_LABEL = [("required", "要予約", "日時を決めて申し込む"),
             ("recommended", "予約推奨", "予約なしでも受け付けるが、連絡しておくと確実"),
             ("not_required", "予約不要", "営業時間内ならそのまま訪問できる"),
             ("inquire", "要問い合わせ", "受付可否を個別に確認")]


def esc(s):
    return html.escape(str(s), quote=True) if s else ""


def table(head, trs):
    return ('<div class="tablewrap"><table><thead><tr>' + "".join(f"<th>{h}</th>" for h in head)
            + "</tr></thead><tbody>" + "".join(trs) + "</tbody></table></div>")


def link(g, b):
    return f'<a href="/{g["path"]}/visit/{b["_pref"]}/#{esc(b["id"])}">{esc(b["name"])}</a>'


def load(g):
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, g["data"]))):
        pref = os.path.basename(f).replace("data_", "").replace(g["suffix"], "")
        if pref not in PREF:
            continue
        for b in json.load(open(f, encoding="utf-8")):
            if (b.get("visit_info") or {}).get("status") == "open" and b.get("id"):
                b["_pref"] = pref
                out.append(b)
    return out


def build(gkey):
    g = GENRES[gkey]
    rows = load(g)
    if len(rows) < 10:
        print(f"{gkey}: 見学情報が{len(rows)}件しかないため記事を作りません")
        return False
    V = [b["visit_info"] for b in rows]
    n = len(rows)
    res = collections.Counter(v.get("reservation", "none") for v in V)
    stated = sum(res[k] for k, _, _ in RES_LABEL)
    res_url = sum(1 for v in V if v.get("reservation_url"))
    fee_rows = [(b, b["visit_info"]["fee"]) for b in rows if b["visit_info"].get("fee")]
    free_rows = [b for b, f in fee_rows if "無料" in f]
    amt = []
    for b, f in fee_rows:
        m = re.findall(r"([0-9][0-9,]*)\s*円", f)
        if m:
            amt.append((b, min(int(x.replace(",", "")) for x in m)))
    dur_rows = [b for b in rows if b["visit_info"].get("duration")]
    tast = collections.Counter(v.get("tasting", "none") for v in V)
    shop = sum(1 for v in V if v.get("shop"))
    eng_rows = [b for b in rows if b["visit_info"].get("english") in ("tour", "materials")]
    drive = sum(1 for v in V if re.search(r"運転|ハンドル", v.get("notes_ja") or ""))
    age = sum(1 for v in V if re.search(r"20歳|未成年", v.get("notes_ja") or ""))
    dates = sorted(v.get("last_checked", "") for v in V if v.get("last_checked"))
    by_pref = collections.Counter(b["_pref"] for b in rows)
    nores = [b for b in rows if b["visit_info"].get("reservation") == "not_required"]

    url = f'https://{g["domain"]}/{g["path"]}/blog/visit-guide.html'

    # ── 予約 ──
    res_trs = [("<tr>" + "".join(f"<td>{x}</td>" for x in
                                 [lbl, f"{res[k]}件", f"{res[k]*100//stated}%", note]) + "</tr>")
               for k, lbl, note in RES_LABEL if res.get(k)]
    sec_res = f"""<h2 id="yoyaku">予約は必要か</h2>
<p>受付方法を公式サイトに明記しているのは{stated}件で、内訳は次のとおりです
（残りの{n - stated}件は受付方法の記載を確認できませんでした）。</p>
{table(["受付方法", "件数", "割合", "内容"], res_trs)}
<p>公式サイトに予約ページを用意しているのは{res_url}件です。それ以外は電話・メール・フォームでの受付になります。</p>"""
    if nores:
        sec_res += (f'<p><strong>予約不要と明記しているのは{len(nores)}件</strong>です：'
                    + "、".join(f'{link(g, b)}（{PREF[b["_pref"]]}）' for b in nores) + "。</p>")
    sec_res += f'<p><a class="inline-cta" href="/{g["path"]}/visit/">見学できる{g["unit"]}の一覧を見る →</a></p>'

    # ── 料金 ──
    sec_fee = ""
    if fee_rows:
        sec_fee = f"""<h2 id="ryokin">料金</h2>
<p>料金を明記しているのは{len(fee_rows)}件で、そのうち{len(free_rows)}件が「無料」を含む記載でした。</p>"""
        if len(amt) >= MIN_STAT:
            vals = sorted(a for _, a in amt)
            band = collections.Counter("500円以下" if a <= 500 else "501〜1,000円" if a <= 1000
                                       else "1,001〜2,000円" if a <= 2000 else "2,001円以上" for a in vals)
            trs = [("<tr>" + "".join(f"<td>{x}</td>" for x in
                                     [k, f"{band[k]}件", f"{band[k]*100//len(vals)}%"]) + "</tr>")
                   for k in ["500円以下", "501〜1,000円", "1,001〜2,000円", "2,001円以上"] if band.get(k)]
            sec_fee += (f"<p>金額が書かれている{len(vals)}件の分布です"
                        "（複数コースがある場合は最も安いコースで数えています）。</p>"
                        + table(["料金帯", "件数", "割合"], trs)
                        + f"<p>中央値は{statistics.median(vals):,.0f}円、"
                          f"{min(vals):,}円から{max(vals):,}円まで幅があります。</p>")
        elif amt:
            ex = "、".join(f'{link(g, b)} {a:,}円' for b, a in sorted(amt, key=lambda x: x[1])[:6])
            sec_fee += (f"<p>金額まで書かれているのは{len(amt)}件で、代表値を出せるほどの件数がありません。"
                        f"実際の記載は{ex}などです。</p>")
        if free_rows:
            sec_fee += ('<p>無料と書かれているのは：'
                        + "、".join(link(g, b) for b in free_rows[:10]) + "。</p>")
        sec_fee += ("<p>「見学は無料だが試飲は有料」という書き方もあるため、"
                    f"条件は各{g['maker']}の記載をご確認ください。</p>")

    # ── 所要時間 ──
    sec_dur = ""
    if dur_rows:
        ex = "、".join(f'{link(g, b)}「{esc(b["visit_info"]["duration"])}」' for b in dur_rows[:5])
        sec_dur = f"""<h2 id="jikan">所要時間</h2>
<p>所要時間を明記しているのは{len(dur_rows)}件です。表記は統一されておらず、{ex}のように書かれています。
売店や試飲の時間は別に見ておくと安全です。</p>"""

    # ── 試飲・直売所 ──
    tast_n = tast.get("free", 0) + tast.get("paid", 0) + tast.get("available", 0)
    sec_tast = f"""<h2 id="shiin">試飲と直売所</h2>
<p>試飲について記載があるのは{tast_n}件で、内訳は無料{tast.get('free',0)}件・有料{tast.get('paid',0)}件・
記載あり（料金不明）{tast.get('available',0)}件です。直売所や売店があると書かれているのは{shop}件でした。</p>"""
    if drive or age:
        sec_tast += (f"<p>車で行く場合、{drive}件が「運転される方は試飲できない」旨を、"
                     f"{age}件が20歳未満の試飲不可を公式サイトに明記しています。"
                     "書いていない場合でも、飲酒運転が禁じられていることに変わりはありません。</p>")

    # ── 英語 ──
    sec_eng = ""
    if eng_rows:
        sec_eng = f"""<h2 id="eigo">英語対応</h2>
<p>英語ツアーまたは英語資料の記載があるのは{len(eng_rows)}件です：
{"、".join(f'{link(g, b)}（{PREF[b["_pref"]]}）' for b in eng_rows)}。
記載が無いだけで対応できる場合もあるため、必要なときは直接お問い合わせください。</p>"""

    # ── 地域 ──
    pref_trs = []
    for p, c in by_pref.most_common():
        rs = [b for b in rows if b["_pref"] == p]
        nr = sum(1 for b in rs if b["visit_info"].get("reservation") == "not_required")
        fr = sum(1 for b in rs if "無料" in (b["visit_info"].get("fee") or ""))
        has_page = os.path.exists(os.path.join(ROOT, g["repo"], g["path"], "visit", p, "index.html"))
        name = (f'<a href="/{g["path"]}/visit/{p}/">{PREF[p]}</a>' if has_page
                else f'<a href="/{g["path"]}/{p}/">{PREF[p]}</a>')
        pref_trs.append("<tr>" + "".join(f"<td>{x}</td>" for x in
                                         [name, f"{c}件", nr or "—", fr or "—"]) + "</tr>")
    sec_area = f"""<h2 id="chiiki">都道府県別</h2>
<p>見学を受け付けている{g['unit']}は{len(by_pref)}都道府県にあります。</p>
{table(["都道府県", "見学できる" + g["unit"], "予約不要", "無料の記載"], pref_trs)}"""

    qa = [(f"{g['kind']}に予約は必要ですか？",
           f"受付方法を明記している{stated}件のうち、{res.get('required',0)}件が要予約、"
           f"{res.get('recommended',0)}件が予約推奨、{res.get('not_required',0)}件が予約不要でした。"
           f"予約が前提の{g['maker']}が多いため、公式サイトの案内を先に確認するのが確実です。"),
          (f"料金はどれくらいですか？",
           f"料金を明記しているのは{len(fee_rows)}件で、うち{len(free_rows)}件が「無料」を含む記載です。"
           + (f"金額が書かれている{len(amt)}件の中央値は{statistics.median([a for _, a in amt]):,.0f}円でした。"
              if len(amt) >= MIN_STAT else "金額まで書かれている件数が少ないため、代表値は出していません。")),
          ("掲載情報はいつ時点のものですか？",
           f"各{g['maker']}の公式サイトを{dates[0] if dates else ''}〜{dates[-1] if dates else ''}に確認した内容です。"
           "受付状況は変わることがあるため、訪問前に必ず公式情報をご確認ください。"),
          ("どうやって調べたのですか？",
           f"Terroir HUB が収録する{g['total']}件の{g['unit']}について、公式サイトを1件ずつ確認し、"
           f"見学・試飲の受付が明記されている{n}件を対象に数えました。"
           "書かれていない項目は「記載なし」として扱い、推測では埋めていません。")]

    title = f"{g['kind']}の予約・料金・所要時間 — {n}件の公式サイトを調べた結果 | Terroir HUB {g['brandsub']}"
    desc = (f"{g['name']}の{g['unit']}{n}件の公式サイトを確認し、予約の要否（要予約{res.get('required',0)}件・"
            f"予約不要{res.get('not_required',0)}件）、料金、所要時間、試飲、英語対応を集計しました。出典と確認日つき。")

    body = f"""
<p class="lede">{g['kind']}は予約が要るのか、いくらかかるのか、どれくらい時間がかかるのか。
{g['maker']}ごとに書き方が違うため、まとまった答えが見つかりません。
そこで、公式サイトを1件ずつ確認し、見学を受け付けている<strong>{n}件</strong>を集計しました。
以下の数字はすべてその集計にもとづきます。</p>

<p class="note-box">調べた範囲：Terroir HUB が収録する{g['total']}件の{g['unit']}のうち、
公式サイトで見学・試飲の受付を確認できた{n}件。確認日は{dates[0] if dates else ''}〜{dates[-1] if dates else ''}です。
件ごとの出典URLと確認日は<a href="/{g['path']}/visit/">見学できる{g['unit']}の一覧</a>に掲載しています。</p>

{sec_res}
{sec_fee}
{sec_dur}
{sec_tast}
{sec_eng}
{sec_area}

<h2 id="shirabekata">この記事の調べ方</h2>
<ul>
  <li>対象は、Terroir HUB が収録する{g['total']}件の{g['unit']}のうち、
      <strong>公式サイトで見学・試飲の受付を確認できた{n}件</strong>です。</li>
  <li>予約方法・料金・所要時間・試飲・英語対応は、<strong>公式サイトに書かれている内容だけ</strong>を記録しています。
      記載が無い項目は数えていません。</li>
  <li>件ごとに<strong>出典URLと確認日</strong>を保存し、ページ上にも表示しています。</li>
  <li>受付状況は変わります。訪問前に、必ず公式情報をご確認ください。</li>
</ul>

<h2 id="faq">よくある質問</h2>
{"".join(f'<div class="faq"><h3>{q}</h3><p>{a}</p></div>' for q, a in qa)}

<h2>関連ページ</h2>
<div class="links">
  <a href="/{g['path']}/visit/">見学できる{g['unit']} 全国{n}件</a>
  <a href="https://sake.terroirhub.com/sake/visit/">見学できる酒蔵（日本酒）253蔵</a>
  {"".join(f'<a href="https://{GENRES[k]["domain"]}/{GENRES[k]["path"]}/visit/">見学できる{GENRES[k]["unit"]}（{GENRES[k]["name"]}）</a>' for k in GENRES if k != gkey)}
</div>
"""

    ld = json.dumps({"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "ホーム", "item": f'https://{g["domain"]}/'},
            {"@type": "ListItem", "position": 2, "name": f'見学できる{g["unit"]}',
             "item": f'https://{g["domain"]}/{g["path"]}/visit/'},
            {"@type": "ListItem", "position": 3, "name": f'{g["kind"]}の予約・料金・所要時間', "item": url}]},
        {"@type": "Article",
         "headline": f"{g['kind']}の予約・料金・所要時間 — {n}件の公式サイトを調べた結果",
         "description": desc, "datePublished": TODAY, "dateModified": TODAY,
         "inLanguage": "ja", "url": url,
         "author": {"@type": "Organization", "name": "Terroir HUB", "url": f'https://{g["domain"]}/'},
         "publisher": {"@type": "Organization", "name": "合同会社FOMUS"},
         "isBasedOn": f'https://{g["domain"]}/{g["path"]}/visit/'},
        {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", a)}} for q, a in qa]}
    ]}, ensure_ascii=False)

    html_out = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Zen+Old+Mincho:wght@400;700&family=Noto+Serif+JP:wght@200;300;400&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/{g['path']}/visit/visit.css">
<style>
.lede{{font-size:16px;line-height:2.1;margin-bottom:20px}}
.note-box{{background:var(--surface-warm);border:1px solid var(--border);border-radius:10px;
  padding:14px 18px;font-size:13px;line-height:1.95;margin-bottom:8px}}
article p{{margin:14px 0;font-size:15px;line-height:2.05}}
article ul{{margin:14px 0 14px 1.2em;font-size:14.5px;line-height:2.05}}
article li{{margin-bottom:8px}}
.inline-cta{{display:inline-block;margin-top:4px;font-size:13.5px;color:var(--accent);
  text-decoration:none;border-bottom:1px solid var(--accent)}}
</style>
<script type="application/ld+json">{ld}</script>
</head>
<body>
<nav class="nav">
  <a class="nav-brand" href="/"><span class="nav-logo">Terroir HUB</span><span class="nav-logo-sub">{g['brandsub']}</span></a>
  <div class="nav-links"><a href="/{g['path']}/visit/">見学できる{g['unit']}</a><a href="/{g['path']}/guide/">ガイド</a>
  <a href="https://www.terroirhub.com/business/">事業者向け</a></div>
</nav>
<main class="wrap">
<div class="crumb"><a href="/">ホーム</a> › <a href="/{g['path']}/visit/">見学できる{g['unit']}</a> › {g['kind']}の予約・料金</div>
<div class="head">
  <div class="eyebrow">Visits</div>
  <h1>{esc(g['kind'])}の予約・料金・所要時間<br>— {n}件の公式サイトを調べた結果</h1>
  <div class="asof">最終更新: {TODAY}　/　調査対象: {n}件（{len(by_pref)}都道府県）</div>
</div>
<article>
{body}
</article>
</main>
<footer>
  <div>本記事の数値は Terroir HUB が収録する{g['unit']}データの集計です。見学情報は各{g['maker']}の公式サイトの記載にもとづき、
  件ごとに出典URLと確認日を表示しています。受付状況は変わるため、訪問前に必ず公式情報をご確認ください。</div>
  <div><a href="https://www.terroirhub.com/listing-update/">掲載情報の修正・写真のご提供</a></div>
  <div>© 2026 合同会社FOMUS — Terroir HUB {g['brandsub']}</div>
</footer>
</body>
</html>
"""
    out = os.path.join(ROOT, g["repo"], g["path"], "blog", "visit-guide.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(html_out)
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html_out, flags=re.S))
    print(f'{gkey}: {out.replace(ROOT + "/", "")}  {len(html_out):,}バイト / '
          f'本文{len(re.sub(r"\\s+", " ", text).strip()):,}字 / 対象{n}件')
    return True


def main():
    keys = [a for a in sys.argv[1:] if a in GENRES] or list(GENRES)
    for k in keys:
        build(k)


if __name__ == "__main__":
    main()
