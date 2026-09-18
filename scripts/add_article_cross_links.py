#!/usr/bin/env python3
"""
検索流入のあるリキュール記事の「関連記事」欄に、姉妹サイトの関連ページを足す。

2026-09-18の実測では、liqueur の記事2本（梅酒に合うおつまみ／プラムワインとは）だけで
サイト全体の表示回数の57%を占める。一方 sake・wine・shochu は
「Discovered - currently not indexed」で、そもそもクロールされない。
読まれている記事から、読まれていないサイトへ発見経路をつくる。

リンクは記事の内容に沿うものだけを手で選んである（機械的な相互リンクはしない）。
リンク先のファイルが実在しない場合は、そのリンクを出さない。

使い方:
  python3 scripts/add_article_cross_links.py --dry
  python3 scripts/add_article_cross_links.py
"""
import os, re, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
DRY = "--dry" in sys.argv
MARK = "<!-- sister-site-links -->"

# リンク先の定義: (サイト内のファイルパス, 公開URL, リンク文言)
def sake(p, label):
    return (f"TerriorHUB　sake/sake/{p}", f"https://sake.terroirhub.com/sake/{p}", label)


def wine(p, label):
    return (f"terroirHUB wine/wine/{p}", f"https://wine.terroirhub.com/wine/{p}", label)


def shochu(p, label):
    return (f"terroirHUB 焼酎/shochu/{p}", f"https://shochu.terroirhub.com/shochu/{p}", label)


def portal(p, label):
    return (f"Portal-terroir/{p}", f"https://www.terroirhub.com/{p}", label)


# 記事ごとの関連ページ（内容に沿うものだけ）
MAP = {
    "blog/umeshu-food-pairing.html": [
        sake("blog/nihonshu-ryori.html", "日本酒に合う料理 — 和食から洋食まで"),
        shochu("guide/pairing.html", "焼酎・泡盛のペアリング"),
        wine("guide/pairing.html", "日本ワインと料理の合わせ方"),
    ],
    "blog/umeshu-vs-plumwine.html": [
        wine("guide/index.html", "日本ワインとは — 基礎からの手引き"),
        wine("guide/varieties.html", "日本ワインのぶどう品種"),
    ],
    "blog/best-umeshu-2026.html": [
        sake("blog/osusume-nihonshu-2026.html", "【2026年版】日本酒のおすすめ"),
        portal("furusato/", "ふるさと納税で地域の酒を探す"),
    ],
    "blog/how-to-drink-umeshu.html": [
        sake("blog/nihonshu-nomikata.html", "日本酒の飲み方 — 温度と器で変わる"),
        shochu("guide/drinking.html", "焼酎の飲み方 — お湯割り・ロック・水割り"),
    ],
    "blog/homemade-umeshu.html": [
        shochu("guide/types.html", "焼酎の種類 — 芋・麦・米・黒糖・泡盛"),
        sake("guide/brewing.html", "日本酒のつくり方"),
    ],
    "blog/yuzu-liqueur-guide.html": [
        shochu("kochi/", "高知県の焼酎蔵"),
        sake("kochi/", "高知県の酒蔵"),
    ],
    "blog/umeshu-english.html": [
        sake("guide/types.html", "日本酒の種類 — 純米・吟醸・大吟醸"),
        portal("furusato/", "ふるさと納税で地域の酒を探す"),
    ],
}

LIQUEUR = os.path.join(ROOT, "terroirHUB liqueur", "liqueur")


def main():
    changed = skipped = dropped = 0
    for rel, targets in MAP.items():
        rel = rel.strip()
        if not targets:
            continue
        path = os.path.join(LIQUEUR, rel)
        if not os.path.exists(path):
            print(f"  {rel}: 記事が無い"); skipped += 1; continue
        html = open(path, encoding="utf-8").read()
        if MARK in html:
            skipped += 1; continue
        items = []
        for src, url, label in targets:
            if not os.path.exists(os.path.join(ROOT, src)):
                print(f"    リンク先が無いので出さない: {src}")
                dropped += 1
                continue
            items.append(f'<li><a href="{url}">{label}</a></li>')
        if not items:
            skipped += 1; continue
        block = (f'{MARK}\n<p style="margin:18px 0 6px;font-weight:600;">姉妹サイトの関連ページ</p>\n'
                 f'<ul>\n' + "\n".join(items) + "\n</ul>")
        m = re.search(r'(<div class="related">.*?)(</div>)', html, re.S)
        if not m:
            print(f"  {rel}: 関連記事の枠が無い"); skipped += 1; continue
        new = html[:m.end(1)] + block + "\n" + html[m.end(1):]
        if DRY:
            print(f"  {rel}: {len(items)}本 追加予定")
        else:
            open(path, "w", encoding="utf-8").write(new)
        changed += 1
    print(f'{"（下見）" if DRY else ""}書き換え {changed}記事 / 見送り {skipped} / リンク先なしで除外 {dropped}本')


if __name__ == "__main__":
    main()
