#!/usr/bin/env python3
"""
インデックスされているサイト（liqueur・whisky）の県一覧ページから、
同じ県の sake・wine・shochu の県一覧ページへ直接リンクを張る。

なぜ必要か（2026-09-18のURL検査APIの実測）:
  liqueur は 31/46、whisky は 6/34 が登録済みなのに、
  sake・wine・shochu は 0/48・0/35・0/34 で、そもそもクロールされない。
  サイトマップに出しても「Discovered - currently not indexed」で読まれないため、
  すでに読まれているページから発見経路をつくる。

リンクは「同じ県の別ジャンル」だけを張る（読者にとって自然で、収録数が0の県には張らない）。
既存の「〇〇県のテロワールを見る」リンクの下に、同じ見た目で並べる。

使い方:
  python3 scripts/add_cross_links.py --dry     # 何を書き換えるか表示するだけ
  python3 scripts/add_cross_links.py
"""
import os, re, sys, glob, json, collections

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
DRY = "--dry" in sys.argv

MARK = "<!-- cross-genre-links -->"

GENRES = {
    "sake":    dict(name="日本酒", unit="蔵", domain="sake.terroirhub.com", path="sake",
                    data="TerriorHUB　sake/data_*_breweries.json", suffix="_breweries.json"),
    "wine":    dict(name="日本ワイン", unit="ワイナリー", domain="wine.terroirhub.com", path="wine",
                    data="terroirHUB wine/data/data_*_wineries.json", suffix="_wineries.json"),
    "shochu":  dict(name="焼酎・泡盛", unit="蔵", domain="shochu.terroirhub.com", path="shochu",
                    data="terroirHUB 焼酎/data/data_*_distilleries.json", suffix="_distilleries.json"),
    "whisky":  dict(name="ウイスキー", unit="蒸溜所", domain="whisky.terroirhub.com", path="whisky",
                    data="terroirHUB whisky/data/data_*_distilleries.json", suffix="_distilleries.json"),
    "liqueur": dict(name="梅酒・リキュール", unit="メーカー", domain="liqueur.terroirhub.com", path="liqueur",
                    data="terroirHUB liqueur/data/data_*_liqueurs.json", suffix="_liqueurs.json"),
}

# 書き換える側（すでにインデックスされていて、発見経路になれるサイト）
SOURCES = [("liqueur", "terroirHUB liqueur/liqueur"), ("whisky", "terroirHUB whisky/whisky")]
# リンク先にするジャンル（クロールされていないサイト）
TARGETS = ["sake", "wine", "shochu"]

PREF_JA = {
    "hokkaido": "北海道", "aomori": "青森県", "iwate": "岩手県", "miyagi": "宮城県", "akita": "秋田県",
    "yamagata": "山形県", "fukushima": "福島県", "ibaraki": "茨城県", "tochigi": "栃木県", "gunma": "群馬県",
    "saitama": "埼玉県", "chiba": "千葉県", "tokyo": "東京都", "kanagawa": "神奈川県", "niigata": "新潟県",
    "toyama": "富山県", "ishikawa": "石川県", "fukui": "福井県", "yamanashi": "山梨県", "nagano": "長野県",
    "gifu": "岐阜県", "shizuoka": "静岡県", "aichi": "愛知県", "mie": "三重県", "shiga": "滋賀県",
    "kyoto": "京都府", "osaka": "大阪府", "hyogo": "兵庫県", "nara": "奈良県", "wakayama": "和歌山県",
    "tottori": "鳥取県", "shimane": "島根県", "okayama": "岡山県", "hiroshima": "広島県", "yamaguchi": "山口県",
    "tokushima": "徳島県", "kagawa": "香川県", "ehime": "愛媛県", "kochi": "高知県", "fukuoka": "福岡県",
    "saga": "佐賀県", "nagasaki": "長崎県", "kumamoto": "熊本県", "oita": "大分県", "miyazaki": "宮崎県",
    "kagoshima": "鹿児島県", "okinawa": "沖縄県",
}


def counts():
    """{genre: {pref_slug: 収録数}}"""
    out = {}
    for key, g in GENRES.items():
        c = collections.Counter()
        for jf in glob.glob(os.path.join(ROOT, g["data"])):
            pref = os.path.basename(jf).replace("data_", "").replace(g["suffix"], "")
            try:
                rows = json.load(open(jf, encoding="utf-8"))
            except Exception:
                continue
            c[pref] = len([b for b in rows if b.get("id")])
        out[key] = c
    return out


def block(pref, cnt, exclude, color="#6B4423"):
    """同じ県の別ジャンルへのリンク。収録0のジャンルは出さない。色はそのサイトの差し色に合わせる"""
    links = []
    for key in TARGETS:
        if key == exclude:
            continue
        n = cnt[key].get(pref, 0)
        if n <= 0:
            continue
        g = GENRES[key]
        links.append(f'<a href="https://{g["domain"]}/{g["path"]}/{pref}/" '
                     f'style="color:{color};text-decoration:none;">'
                     f'{PREF_JA[pref]}の{g["name"]}（{n}{g["unit"]}）</a>')
    if not links:
        return None
    return (f'{MARK}\n<div style="max-width:1080px;margin:10px auto 0;padding:0 24px;text-align:center;'
            f'font-size:13px;letter-spacing:0.03em;line-height:2;">'
            + '　/　'.join(links) + '</div>')


def main():
    cnt = counts()
    changed = skipped = 0
    for genre, rel in SOURCES:
        for path in sorted(glob.glob(os.path.join(ROOT, rel, "*", "index.html"))):
            pref = os.path.basename(os.path.dirname(path))
            if pref not in PREF_JA:
                continue
            html = open(path, encoding="utf-8").read()
            if MARK in html:
                skipped += 1
                continue
            # 既存の「テロワールを見る」リンクの直後に置く。無ければ </main> の直後
            m = re.search(r'(<div[^>]*>\s*<a href="https://www\.terroirhub\.com/terroir/[a-z]+\.html".*?</div>)',
                          html, re.S)
            col = "#6B4423"
            if m:
                mc = re.search(r'color:\s*(#[0-9A-Fa-f]{3,6})', m.group(1))
                if mc:
                    col = mc.group(1)
            b = block(pref, cnt, genre, col)
            if not b:
                skipped += 1
                continue
            if m:
                new = html[:m.end()] + "\n" + b + html[m.end():]
            elif "</main>" in html:
                i = html.index("</main>") + len("</main>")
                new = html[:i] + "\n" + b + html[i:]
            else:
                skipped += 1
                continue
            if DRY:
                print(f'  {genre}/{pref}: 追加予定 {b.count("<a href")}本')
            else:
                open(path, "w", encoding="utf-8").write(new)
            changed += 1
    print(f'{"（下見）" if DRY else ""}書き換え {changed}ページ / 対象外 {skipped}ページ')


if __name__ == "__main__":
    main()
