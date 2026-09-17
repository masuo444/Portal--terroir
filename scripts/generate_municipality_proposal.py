#!/usr/bin/env python3
"""
自治体向けの個別提案書を自動生成する（1自治体＝1枚）。

「御市の返礼品をこう紹介しています」という現物を先に見せ、そのうえで
有料パッケージを提案する構成。433自治体ぶんを同じ形で作れるので、
2件目以降の作成コストはゼロになる。

出力（公開ディレクトリの外。営業資料であってWebに置くものではない）:
  ../proposals/<県slug>/<自治体slug>.html   個別提案書
  ../proposals/_priority.csv                 営業の優先順リスト
  ../proposals/_index.html                   一覧（社内用）

使い方:
  python3 scripts/generate_municipality_proposal.py              # 全件
  python3 scripts/generate_municipality_proposal.py --top 30     # 優先上位だけ
  python3 scripts/generate_municipality_proposal.py --pref yamanashi
"""
import json, os, sys, csv, html, datetime

TODAY = datetime.date.today()
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
OUTROOT = os.path.join(ROOT, "proposals")
INDEX = os.path.join(BASE, "data", "furusato_municipality_index.json")
DOMAIN = "www.terroirhub.com"

# ── 価格（2026-09-17 決定。ここだけ直せば全提案書に反映されます）────────────
# 税込でも少額随意契約の上限に収まる額に置いている（令和7年4月施行の地方自治法施行令改正）。
#   スタンダード 44万（税込48.4万）: 旧基準50万のままの町村でも随意契約可
#   プレミアム   88万（税込96.8万）: 新基準100万（指定都市を除く市区町村の業務委託）に収まる
PRICE = {
    "standard": {"name": "スタンダード", "yen": 440000,
                 "items": ["自治体専用ページの作成・運用",
                           "市内の造り手ページの英語対応",
                           "月次レポート（閲覧数・海外比率・検索語）",
                           "掲載内容の更新（回数制限なし）"]},
    "premium":  {"name": "プレミアム", "yen": 880000,
                 "items": ["スタンダードの全内容",
                           "地域の酒をテーマにした特集記事の制作",
                           "見学・体験の案内ページの整備",
                           "四半期ごとの分析と改善のご提案"]},
}
PRICE_NOTE = "いずれも年額・税別です（税込：スタンダード484,000円／プレミアム968,000円）。年度途中からのご契約は月割りで承ります。"


def esc(s):
    return html.escape(str(s or ""), quote=True)


CSS = """*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#FAFAF7;--surface:#F3F0EA;--border:rgba(0,0,0,.09);--text:#1a1816;--muted:rgba(26,24,22,.6);--gold:#996E1A;--fd:'Shippori Mincho',serif;--fb:'Noto Sans JP',sans-serif;--fn:'Inter',sans-serif}
body{background:var(--bg);color:var(--text);font-family:var(--fb);line-height:1.9;-webkit-font-smoothing:antialiased}
a{color:inherit}
.sheet{max-width:860px;margin:0 auto;background:#fff;border:1px solid var(--border);padding:clamp(1.8rem,4vw,3.4rem)}
.brandrow{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid var(--border);padding-bottom:1rem;margin-bottom:2rem;flex-wrap:wrap;gap:.6rem}
.brand{font-family:var(--fd);font-size:1.15rem;font-weight:700;letter-spacing:.06em}
.date{font-family:var(--fn);font-size:.78rem;color:var(--muted)}
.to{font-size:.95rem;margin-bottom:.4rem}
h1{font-family:var(--fd);font-size:clamp(1.5rem,3.4vw,2.1rem);font-weight:700;line-height:1.45;margin:.6rem 0 1.2rem}
.lead{font-size:.96rem;line-height:2.05;margin-bottom:1.8rem}
h2{font-family:var(--fd);font-size:1.15rem;font-weight:700;margin:2.2rem 0 .7rem;padding-left:.6rem;border-left:3px solid var(--gold)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem;margin:1.2rem 0}
@media(max-width:720px){.grid{grid-template-columns:1fr}}
.kpi{background:var(--surface);border:1px solid var(--border);padding:1.1rem 1rem}
.kpi-n{font-family:var(--fn);font-size:clamp(1.5rem,3.2vw,2rem);font-weight:600;line-height:1.1}
.kpi-l{font-size:.76rem;color:var(--muted);margin-top:.35rem;line-height:1.5}
.urlbox{background:var(--surface);border:1px solid var(--border);padding:1.1rem 1.3rem;margin:1rem 0}
.urlbox a{font-family:var(--fn);font-size:.92rem;color:var(--gold);word-break:break-all}
.urlbox p{font-size:.82rem;color:var(--muted);margin-top:.4rem}
ul{margin:.5rem 0 0 1.2rem}
li{font-size:.92rem;margin-bottom:.3rem}
.plans{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:1rem}
@media(max-width:720px){.plans{grid-template-columns:1fr}}
.plan{border:1px solid var(--border);padding:1.4rem 1.5rem}
.plan.best{border-color:var(--gold);border-width:2px}
.plan-n{font-family:var(--fn);font-size:.72rem;letter-spacing:.14em;color:var(--muted);text-transform:uppercase}
.plan-p{font-family:var(--fd);font-size:1.8rem;font-weight:700;margin:.3rem 0 .6rem}
.plan-p small{font-size:.8rem;font-weight:500;color:var(--muted)}
.plan ul{margin-left:1.1rem}
.plan li{font-size:.85rem;line-height:1.75}
table{width:100%;border-collapse:collapse;font-size:.9rem;margin-top:.6rem}
th,td{text-align:left;padding:.55rem .3rem;border-bottom:1px solid var(--border)}
th{font-size:.75rem;color:var(--muted);font-weight:500}
td.num{text-align:right;font-family:var(--fn)}
.note{background:var(--surface);border:1px solid var(--border);padding:1.1rem 1.3rem;font-size:.82rem;color:var(--muted);line-height:1.9;margin-top:2rem}
.foot{max-width:860px;margin:1.2rem auto 3rem;font-size:.76rem;color:var(--muted);text-align:center;line-height:1.9}
.notyet{color:var(--muted);font-size:.9rem}"""


def render(r, producers_note):
    pref, city = r["pref"], r["city"]
    full = pref + city
    url = f'https://{DOMAIN}{r["url"]}'
    plans = "".join(
        f'''<div class="plan{' best' if k == 'standard' else ''}">
      <div class="plan-n">{esc(v["name"])}</div>
      <div class="plan-p">{v["yen"]:,}<small> 円 / 年（税別）</small></div>
      <ul>{"".join(f"<li>{esc(x)}</li>" for x in v["items"])}</ul>
    </div>''' for k, v in PRICE.items())

    prod_block = (f'<p>{esc(full)}に所在する造り手を <b>{r["producers"]}者</b> 収録しています。'
                  f'各ページに所在地・公式サイト・代表銘柄を、出典を明記して掲載しています。</p>'
                  if r["producers"] else
                  '<p class="notyet">現在、当サイトに収録している貴自治体の造り手はありません。'
                  'ご教示いただければ、無料で掲載いたします。</p>')

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>{esc(full)} ご提案 | Terroir HUB</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@600;700&family=Noto+Sans+JP:wght@300;400;500&family=Inter:wght@500;600&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="sheet">
  <div class="brandrow"><div class="brand">Terroir HUB</div><div class="date">{TODAY.year}年{TODAY.month}月{TODAY.day}日</div></div>

  <div class="to">{esc(full)} ふるさと納税ご担当者様</div>
  <h1>{esc(city)}の返礼品と造り手を、<br>国内外に正しく伝えるご提案</h1>

  <p class="lead">Terroir HUB は、全国 2,800 を超える酒の造り手を、公式情報にもとづいて収録しているデータベースです。
  すでに {esc(full)} の返礼品を掲載したページを公開しており、本書はその内容のご確認と、
  さらに活用いただくためのご提案です。</p>

  <h2>すでに公開しているページ</h2>
  <div class="grid">
    <div class="kpi"><div class="kpi-n">{r["items"]}</div><div class="kpi-l">掲載している{esc(city)}の返礼品</div></div>
    <div class="kpi"><div class="kpi-n">{r["producers"]}</div><div class="kpi-l">収録している市内の造り手</div></div>
    <div class="kpi"><div class="kpi-n">2,800<small style="font-size:.55em">+</small></div><div class="kpi-l">全国の収録生産者</div></div>
  </div>
  <div class="urlbox">
    <a href="{url}">{url}</a>
    <p>寄付金額から絞り込めます。ご覧いただき、誤りがあればご指摘ください。修正は無料で承ります。</p>
  </div>

  <h2>{esc(city)}の造り手について</h2>
  {prod_block}
  {producers_note}

  <h2>Terroir HUB の考え方</h2>
  <ul>
    <li>公式に公表されている情報だけを掲載し、出典と最終確認日を明記しています</li>
    <li>情報がない項目は、推測で埋めずに非表示にしています</li>
    <li>日本酒・焼酎・泡盛・ワイン・ウイスキー・リキュールを横断して収録しています</li>
    <li>主要ページは英語に対応しています</li>
  </ul>

  <h2>ご提供できること</h2>
  <div class="plans">{plans}</div>
  <p style="font-size:.82rem;color:var(--muted);margin-top:.8rem">{esc(PRICE_NOTE)}</p>

  <h2>月次レポートについて</h2>
  <p>貴自治体のページが月に何回検索結果に表示され、何人に閲覧され、そのうち何人が海外からだったかを、
  毎月お届けします。数値は Google Search Console および Google Analytics の実測値で、
  取得できなかった項目は「計測準備中」と明記し、推計値は用いません。</p>

  <div class="note">
    <p>本書に記載した掲載件数は {TODAY.isoformat()} 時点のものです。返礼品は随時入れ替わるため変動します。</p>
    <p>当サイトは楽天ふるさと納税のアフィリエイトリンクを含みます。寄付の受付・決済は行っていません。</p>
    <p>掲載の修正・削除のご要望は、ご契約の有無にかかわらず無料で承ります。</p>
  </div>
</div>
<div class="foot">合同会社FOMUS — Terroir HUB<br>contact@fomus.jp ／ https://www.terroirhub.com/business/municipality/</div>
</body>
</html>"""


def main():
    args = sys.argv[1:]
    top = int(args[args.index("--top") + 1]) if "--top" in args else None
    pref_only = args[args.index("--pref") + 1] if "--pref" in args else None

    rows = json.load(open(INDEX, encoding="utf-8"))
    # 優先度: 造り手がいる自治体ほど「御市の蔵を紹介しています」と言えて話が早い
    for r in rows:
        r["score"] = r["items"] + r["producers"] * 3
    rows.sort(key=lambda r: -r["score"])
    if pref_only:
        rows = [r for r in rows if r["pref_slug"] == pref_only]
    targets = rows[:top] if top else rows

    os.makedirs(OUTROOT, exist_ok=True)
    for r in targets:
        d = os.path.join(OUTROOT, r["pref_slug"])
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, f'{r["slug"]}.html'), "w", encoding="utf-8").write(render(r, ""))

    # 営業の優先順リスト
    csv_path = os.path.join(OUTROOT, "_priority.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["優先度", "都道府県", "自治体", "返礼品数", "収録している造り手",
                    "公開ページURL", "提案書ファイル"])
        for i, r in enumerate(rows, 1):
            w.writerow([i, r["pref"], r["city"], r["items"], r["producers"],
                        f'https://{DOMAIN}{r["url"]}',
                        f'proposals/{r["pref_slug"]}/{r["slug"]}.html'])

    print(f"提案書: {len(targets)}件 → {OUTROOT}")
    print(f"優先リスト: {csv_path}（全{len(rows)}自治体）")
    print("\n優先上位10:")
    for r in rows[:10]:
        print(f'  {r["pref"]}{r["city"]}: 返礼品{r["items"]} 造り手{r["producers"]}')


if __name__ == "__main__":
    main()
