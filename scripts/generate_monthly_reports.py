#!/usr/bin/env python3
"""
蔵元・ワイナリー向けの月次レポートを自動生成する（商品「掲載強化＋月次レポート」の納品物）。

  python3 scripts/generate_monthly_reports.py                 # 前月分を生成
  python3 scripts/generate_monthly_reports.py --month 2026-08
  python3 scripts/generate_monthly_reports.py --demo          # 数値サンプル（営業資料の見本用）
  python3 scripts/generate_monthly_reports.py --top 50        # 表示回数の多い上位だけ生成

出力:
  ../reports/<YYYY-MM>/<genre>/<producer_id>.html   各社に送るレポート（公開ディレクトリ外）
  ../reports/<YYYY-MM>/index.html                   社内用: 表示回数順＝営業の優先順位

原則: 取得できなかった指標は表示しない（0件と言い切らない・推測で埋めない）。
"""
import os, sys, json, html, datetime, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import monthly_report_data as D

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
# 公開ディレクトリ(Portal-terroir)の外に出す。各社のレポートは配布物であり、Webに置かない。
OUTROOT = os.path.join(ROOT, "reports")
GENRE_BY_KEY = {g["key"]: g for g in D.GENRES}


def esc(s):
    return html.escape(str(s or ""), quote=True)


CSS = """*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#FAFAF7;--surface:#F3F0EA;--border:rgba(0,0,0,.09);--text:#1a1816;--muted:rgba(26,24,22,.6);--gold:#996E1A;--fd:'Shippori Mincho',serif;--fb:'Noto Sans JP',sans-serif;--fn:'Inter',sans-serif}
body{background:var(--bg);color:var(--text);font-family:var(--fb);line-height:1.85;-webkit-font-smoothing:antialiased}
a{color:inherit}
.sheet{max-width:840px;margin:0 auto;background:#fff;border:1px solid var(--border);padding:clamp(1.6rem,4vw,3.2rem)}
.brandrow{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid var(--border);padding-bottom:1rem;margin-bottom:1.8rem;flex-wrap:wrap;gap:.6rem}
.brand{font-family:var(--fd);font-size:1.1rem;font-weight:700;letter-spacing:.06em}
.period{font-family:var(--fn);font-size:.8rem;color:var(--muted);letter-spacing:.06em}
h1{font-family:var(--fd);font-size:clamp(1.4rem,3.2vw,2rem);font-weight:700;line-height:1.4;margin-bottom:.4rem}
.sub{font-size:.88rem;color:var(--muted);margin-bottom:2rem}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem;margin-bottom:1.6rem}
@media(max-width:720px){.grid{grid-template-columns:repeat(2,1fr)}}
.kpi{background:var(--surface);border:1px solid var(--border);padding:1.1rem 1rem}
.kpi-n{font-family:var(--fn);font-size:clamp(1.5rem,3.4vw,2.1rem);font-weight:600;line-height:1.1}
.kpi-l{font-size:.76rem;color:var(--muted);margin-top:.35rem;line-height:1.5}
.kpi-na{font-family:var(--fn);font-size:1rem;color:var(--muted);line-height:2.2}
h2{font-family:var(--fd);font-size:1.12rem;font-weight:700;margin:2rem 0 .7rem;padding-left:.6rem;border-left:3px solid var(--gold)}
table{width:100%;border-collapse:collapse;font-size:.88rem}
th,td{text-align:left;padding:.55rem .2rem;border-bottom:1px solid var(--border)}
th{font-size:.74rem;color:var(--muted);font-weight:500;letter-spacing:.06em}
td.num{text-align:right;font-family:var(--fn)}
.note{background:var(--surface);border:1px solid var(--border);padding:1rem 1.2rem;font-size:.8rem;color:var(--muted);line-height:1.9;margin-top:1.6rem}
.foot{max-width:840px;margin:1.2rem auto 3rem;font-size:.74rem;color:var(--muted);text-align:center;line-height:1.9}
.warn{background:#FFF6E8;border:1px solid #E3C489;color:#6B4B10;padding:.9rem 1.2rem;font-size:.82rem;margin-bottom:1.6rem;line-height:1.8}
.demo{background:#FDECEC;border:1px solid #E0A0A0;color:#8A2A2A;padding:.9rem 1.2rem;font-size:.84rem;font-weight:600;margin-bottom:1.6rem}
.idx td a{text-decoration:none;color:var(--gold)}"""

HEAD = """<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@600;700&family=Noto+Sans+JP:wght@300;400;500&family=Inter:wght@500;600&display=swap" rel="stylesheet">
<style>{css}</style></head><body>"""


def kpi(n, label, unit=""):
    if n is None:
        return f'<div class="kpi"><div class="kpi-na">計測準備中</div><div class="kpi-l">{esc(label)}</div></div>'
    return (f'<div class="kpi"><div class="kpi-n">{n:,}<span style="font-size:.6em">{esc(unit)}</span></div>'
            f'<div class="kpi-l">{esc(label)}</div></div>')


def render_report(r, g, start, end, has_creds, demo=False):
    period = f"{start.year}年{start.month}月"
    pname = r["name"]
    has_search = has_creds and (r["impressions"] or r["clicks"])
    has_ga = has_creds and (r["sessions"] or r["users"])

    kpis = "".join([
        kpi(r["impressions"] if has_search else None, "検索結果に表示された回数", "回"),
        kpi(r["clicks"] if has_search else None, "検索から開かれた回数", "回"),
        kpi(r["users"] if has_ga else None, "ページを見た人", "人"),
        kpi(r["overseas_users"] if has_ga else None, "うち海外から", "人"),
    ])

    qhtml = ""
    if r["queries"]:
        rows = "".join(f'<tr><td>{esc(q)}</td><td class="num">{n:,}</td></tr>' for q, n in r["queries"])
        qhtml = f"""<h2>検索された言葉</h2>
<p class="sub" style="margin-bottom:.8rem">この期間に、御社のページが表示されたときの検索語です。</p>
<table><thead><tr><th>検索された言葉</th><th style="text-align:right">表示回数</th></tr></thead><tbody>{rows}</tbody></table>"""

    fur = ""
    if r["furusato"]:
        fur = f"""<h2>ふるさと納税の掲載</h2>
<p class="sub" style="margin-bottom:0">Terroir HUB のふるさと納税ページに、御社に関連する返礼品を <b>{r["furusato"]:,}件</b> 掲載しています。
自治体ページ・県別ページからも導線があります。</p>"""

    pos = ""
    if has_search and r["position"]:
        pos = f'<p class="sub" style="margin-bottom:0">この期間の平均掲載順位は <b>{r["position"]}位</b> でした。</p>'

    banner = ""
    if demo:
        banner = '<div class="demo">これはサンプルです。数値は実測値ではありません（営業資料の見本用）。</div>'
    elif not has_creds:
        banner = ('<div class="warn">Search Console / GA4 の計測連携がまだ設定されていないため、'
                  '検索・アクセスの数値は表示していません。連携後、翌月分から反映されます。</div>')

    return HEAD.format(title=f'{esc(pname)} 月次レポート {period} | Terroir HUB', css=CSS) + f"""
<div class="sheet">
  <div class="brandrow"><div class="brand">Terroir HUB</div><div class="period">{esc(period)} 月次レポート</div></div>
  {banner}
  <h1>{esc(pname)} 様</h1>
  <p class="sub">Terroir HUB {esc(g["name"])}（{esc(g["domain"])}）に掲載中の御社ページの、{esc(period)}の実績です。</p>
  <div class="grid">{kpis}</div>
  {pos}
  {qhtml}
  {fur}
  <div class="note">
    <p>「検索結果に表示された回数」は、Google検索の結果に御社のページが出た回数です。クリックされなくても数えます。</p>
    <p>数値の出典は Google Search Console および Google Analytics 4 です。Terroir HUB が計測しているのは当サイト内の御社ページのみで、御社の公式サイトの数値ではありません。</p>
    <p>掲載内容の修正・写真の提供はいつでも承ります。<a href="https://www.terroirhub.com/listing-update/">terroirhub.com/listing-update/</a></p>
  </div>
</div>
<div class="foot">Terroir HUB — 日本の酒と土地を、正確な一次情報で。<br>
  <a href="{esc(r["url"])}">{esc(r["url"])}</a></div>
</body></html>"""


def render_index(data, start, end, has_creds, demo):
    period = f"{start.year}年{start.month}月"
    blocks = []
    total = 0
    for gk, rows in data.items():
        g = GENRE_BY_KEY[gk]
        listed = [r for r in rows if r["impressions"] or r["users"] or r["furusato"]]
        listed = listed[:200]
        total += len(rows)
        if not listed:
            continue
        trs = "".join(
            f'<tr><td><a href="{gk}/{esc(r["id"])}.html">{esc(r["name"])}</a></td>'
            f'<td>{esc(PREF_JA.get(r["pref"], r["pref"]))}</td>'
            f'<td class="num">{r["impressions"]:,}</td><td class="num">{r["clicks"]:,}</td>'
            f'<td class="num">{r["users"]:,}</td><td class="num">{r["overseas_users"]:,}</td>'
            f'<td class="num">{r["furusato"]:,}</td></tr>' for r in listed)
        blocks.append(f"""<h2>{esc(g["name"])}（{len(rows):,}件中 上位{len(listed)}）</h2>
<table class="idx"><thead><tr><th>生産者</th><th>県</th><th style="text-align:right">表示回数</th>
<th style="text-align:right">クリック</th><th style="text-align:right">閲覧者</th>
<th style="text-align:right">海外</th><th style="text-align:right">返礼品</th></tr></thead><tbody>{trs}</tbody></table>""")

    banner = '<div class="demo">サンプルデータです。</div>' if demo else (
        '' if has_creds else '<div class="warn">計測連携が未設定のため、検索・アクセスの数値は空です。'
        'ふるさと納税の掲載件数のみ実データです。</div>')
    return HEAD.format(title=f"月次レポート 社内インデックス {period}", css=CSS) + f"""
<div class="sheet">
  <div class="brandrow"><div class="brand">Terroir HUB</div><div class="period">{esc(period)} 社内用</div></div>
  {banner}
  <h1>月次レポート インデックス</h1>
  <p class="sub">表示回数の多い順に並べています。上にいる生産者ほど「自分のページが見られている」実感を持ちやすく、
  掲載強化の提案が通りやすい相手です。収録 {total:,}件。</p>
  {''.join(blocks)}
  <div class="note"><p>このページは社内用です（noindex）。各行のリンクが、その生産者に送るレポートです。</p></div>
</div></body></html>"""


PREF_JA = {'hokkaido':'北海道','aomori':'青森','iwate':'岩手','miyagi':'宮城','akita':'秋田','yamagata':'山形',
 'fukushima':'福島','ibaraki':'茨城','tochigi':'栃木','gunma':'群馬','saitama':'埼玉','chiba':'千葉','tokyo':'東京',
 'kanagawa':'神奈川','niigata':'新潟','toyama':'富山','ishikawa':'石川','fukui':'福井','yamanashi':'山梨','nagano':'長野',
 'gifu':'岐阜','shizuoka':'静岡','aichi':'愛知','mie':'三重','shiga':'滋賀','kyoto':'京都','osaka':'大阪','hyogo':'兵庫',
 'nara':'奈良','wakayama':'和歌山','tottori':'鳥取','shimane':'島根','okayama':'岡山','hiroshima':'広島','yamaguchi':'山口',
 'tokushima':'徳島','kagawa':'香川','ehime':'愛媛','kochi':'高知','fukuoka':'福岡','saga':'佐賀','nagasaki':'長崎',
 'kumamoto':'熊本','oita':'大分','miyazaki':'宮崎','kagoshima':'鹿児島','okinawa':'沖縄'}


def make_demo(data):
    rnd = random.Random(42)
    for rows in data.values():
        for r in rows[:60]:
            r["impressions"] = rnd.randint(80, 3200)
            r["clicks"] = max(1, int(r["impressions"] * rnd.uniform(0.01, 0.08)))
            r["users"] = max(1, int(r["clicks"] * rnd.uniform(0.7, 1.4)))
            r["overseas_users"] = int(r["users"] * rnd.uniform(0.05, 0.45))
            r["position"] = round(rnd.uniform(3, 28), 1)
            if not r["queries"]:
                pj = PREF_JA.get(r["pref"], r["pref"])
                r["queries"] = [(f'{r["name"]} 見学', r["impressions"] // 3),
                                (f'{r["name"]}', r["impressions"] // 4),
                                (f'{pj} 酒蔵 おすすめ', r["impressions"] // 8)]
    for k in data:
        data[k] = sorted(data[k], key=lambda r: -r["impressions"])
    return data


def main():
    args = sys.argv[1:]
    ym = args[args.index("--month") + 1] if "--month" in args else None
    top = int(args[args.index("--top") + 1]) if "--top" in args else None
    demo = "--demo" in args

    data, start, end, has_creds = D.collect(ym)
    if demo:
        data = make_demo(data)
        has_creds = True
    outdir = os.path.join(OUTROOT, f"{start.year}-{start.month:02d}")
    made = 0
    for gk, rows in data.items():
        g = GENRE_BY_KEY[gk]
        target = [r for r in rows if r["impressions"] or r["users"] or r["furusato"]] or rows
        if top:
            target = target[:top]
        d = os.path.join(outdir, gk)
        os.makedirs(d, exist_ok=True)
        for r in target:
            open(os.path.join(d, f'{r["id"]}.html'), "w", encoding="utf-8").write(
                render_report(r, g, start, end, has_creds, demo))
            made += 1
    os.makedirs(outdir, exist_ok=True)
    open(os.path.join(outdir, "index.html"), "w", encoding="utf-8").write(
        render_index(data, start, end, has_creds, demo))
    print(f"対象月: {start} 〜 {end}")
    print(f"計測連携: {'あり' if has_creds and not demo else ('サンプル' if demo else 'なし（THUB_GOOGLE_SA_JSON 未設定）')}")
    print(f"生成: {made}件 → {outdir}")
    print(f"社内インデックス: {os.path.join(outdir, 'index.html')}")


if __name__ == "__main__":
    main()
