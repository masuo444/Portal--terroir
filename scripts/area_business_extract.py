#!/usr/bin/env python3
"""
返礼品名から事業者名の候補を抜き出す（ルールベース・API不要）。

商品名に「〇〇酒造」「〇〇農園」「〇〇牧場」のように事業者を示す語が
含まれている場合だけを拾う。推測はしない。拾えたものは候補であって確定ではないため、
公開前に自治体・事業者への確認を前提とする。

出力: data/area_text/<県slug>/<自治体slug>.businesses.json
使い方: python3 scripts/area_business_extract.py --all
"""
import json, os, re, sys, glob, collections

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "data", "area_text")

# 事業者を示す語尾（この語で終わる固有名詞だけを拾う）
SUFFIX = ("酒造", "酒造場", "醸造", "醸造所", "酒販", "酒店", "蒸溜所", "蒸留所", "ワイナリー",
          "農園", "農場", "牧場", "果樹園", "ぶどう園", "茶園", "漁協", "水産", "製茶",
          "工房", "窯", "織物", "製陶", "木工", "製菓", "菓子舗", "製麺", "製粉", "食品",
          "商店", "商会", "本舗", "本店", "屋", "堂", "庵", "舎", "苑", "園")
# 事業者名ではないもの（産地・一般語）
STOP = re.compile(r'^(ふるさと|返礼|山梨|長野|佐賀|長崎|宮崎|福岡|兵庫|新潟|岐阜|北海道|高山|神戸|'
                  r'数量|期間|送料|訳あり|先行|季節|限定|新作|人気|特産|名物|老舗|国産|地元|自家|'
                  r'こだわり|厳選|贅沢|高級|特選|上質|絶品)')
# 事業者名ではない一般語（完全一致で除外）
GENERIC = {"加工食品", "冷凍食品", "発酵食品", "健康食品", "自然食品", "保存食品", "子供部屋", "自社農園",
           "契約農園", "提携農園", "地元農園", "観光農園", "自社工房", "農林水産", "日本ワイナリー",
           "カレー屋", "ラーメン屋", "パン屋", "居酒屋", "蕎麦屋", "洋菓子店", "和菓子店", "精肉店",
           "直売所", "醸造所", "製造所", "加工所", "共同農園", "果樹園", "ぶどう園", "牧場", "農園",
           "健康補助食品", "機能性表示食品", "天然醸造", "生産者直送", "産地直送", "冷蔵食品"}
NAME = re.compile(r'([一-龥ぁ-んァ-ヶA-Za-z0-9ー・々]{2,12}(?:' + "|".join(SUFFIX) + r'))')


def extract(names):
    cnt = collections.Counter()
    for nm in names:
        s = re.sub(r'^[【\[]?\s*ふるさと納税\s*[】\]]?\s*', '', nm or '')
        s = re.sub(r'[【】\[\]（）()｜|/]', ' ', s)
        for m in NAME.findall(s):
            m = m.strip('・ ')
            if len(m) < 3 or STOP.match(m) or m in GENERIC:
                continue
            # 「〇〇屋」「〇〇園」など1文字語尾は、短すぎるものを除く（誤検出が多いため）
            if m[-1] in "屋堂庵舎苑園" and len(m) < 4:
                continue
            cnt[m] += 1
    # 2回以上出てくるものだけを候補にする（1回だけの表記ゆれ・誤検出を落とす）
    return [{"name": n, "items": c} for n, c in cnt.most_common() if c >= 2]


def main():
    paths = (sorted(glob.glob(os.path.join(BASE, "data", "area", "*", "*.json")))
             if "--all" in sys.argv else
             [os.path.join(BASE, "data", "area", a + ".json") for a in sys.argv[1:] if not a.startswith("--")])
    total = 0
    for p in paths:
        d = json.load(open(p, encoding="utf-8"))
        biz = extract([i["name"] for i in d["items"]])
        dd = os.path.join(OUT_DIR, d["pref_slug"])
        os.makedirs(dd, exist_ok=True)
        json.dump({"pref": d["pref"], "city": d["city"], "count": len(biz), "businesses": biz,
                   "note": "返礼品名から機械的に抽出した候補。確定ではなく、公開前に確認が必要。"},
                  open(os.path.join(dd, f'{d["slug"]}.businesses.json'), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        total += len(biz)
        top = "、".join(b["name"] for b in biz[:6])
        print(f'  {d["pref"]}{d["city"]}: {len(biz)}者　{top}')
    print(f'\n合計 {total}者の候補')


if __name__ == "__main__":
    main()
