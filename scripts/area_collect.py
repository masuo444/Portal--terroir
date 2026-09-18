#!/usr/bin/env python3
"""
地域（市区町村）の「風土のもの」を全ジャンルで収集する。

楽天ふるさと納税の自治体ショップ（店舗コード f+JIS-ローマ字）から返礼品をすべて取得し、
楽天のジャンル階層（大分類）で「酒・果物・肉…」などの風土カテゴリに振り分けて保存する。
分類は楽天のジャンル情報による機械的なもので、AIは使わない（費用ゼロ・再現可能）。

出力: data/area/<県slug>/<自治体slug>.json
使い方:
  python3 scripts/area_collect.py f192139-koshu f281000-kobe ...
  python3 scripts/area_collect.py --demo10        # 見本の10市
"""
import json, os, sys, time, urllib.request, urllib.parse, urllib.error, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
CFG = json.load(open(os.path.join(ROOT, "TerriorHUB　sake", "scripts", "rakuten_config.json"), encoding="utf-8"))
ITEM_EP = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
GENRE_EP = "https://openapi.rakuten.co.jp/ichibagt/api/IchibaGenre/Search/20260701"
H = {"Referer": CFG["referer"], "Origin": CFG["referer"], "User-Agent": "terroirhub-batch/1.0"}
MUNI = json.load(open(os.path.join(BASE, "data", "furusato_municipalities.json"), encoding="utf-8"))
GENRE_CACHE_PATH = os.path.join(BASE, "data", "rakuten_genres.json")
SLEEP = 1.5
_last = [0.0]

DEMO10 = ["f014087-yoichi", "f151009-niigata", "f192139-koshu", "f202193-tomi", "f212032-takayama",
          "f281000-kobe", "f402036-kurume", "f412074-kashima", "f422100-iki", "f452025-miyakonojo"]

# 風土カテゴリ（表示順）。楽天の大分類名・中分類名から決める
CATEGORIES = [
    ("sake",    "酒",           "日本酒・焼酎・ワイン・ビール"),
    ("fruit",   "果物",         "旬の果物"),
    ("meat",    "肉",           "ブランド牛・豚・鶏"),
    ("seafood", "魚介",         "海と川の幸"),
    ("farm",    "米・野菜",      "米と野菜"),
    ("food",    "加工品・調味料", "土地の食文化"),
    ("sweets",  "菓子",         "郷土の菓子"),
    ("craft",   "工芸・ものづくり", "土地の技"),
    ("stay",    "体験・宿泊",    "訪れて楽しむ"),
]


def _throttle():
    dt = time.monotonic() - _last[0]
    if dt < SLEEP:
        time.sleep(SLEEP - dt)
    _last[0] = time.monotonic()


def _get(url, params):
    q = {"applicationId": CFG["applicationId"], "accessKey": CFG["accessKey"], "format": "json", **params}
    for attempt in range(5):
        _throttle()
        try:
            req = urllib.request.Request(url + "?" + urllib.parse.urlencode(q), headers=H)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 4:
                time.sleep(4 * (attempt + 1)); continue
            raise
        except Exception:
            if attempt < 4:
                time.sleep(3 * (attempt + 1)); continue
            raise
    return {}


_genres = json.load(open(GENRE_CACHE_PATH, encoding="utf-8")) if os.path.exists(GENRE_CACHE_PATH) else {}


def genre_path(gid):
    """ジャンルID → [大分類, 中分類, ...] の名前リスト（キャッシュあり）"""
    k = str(gid)
    if k not in _genres:
        try:
            d = _get(GENRE_EP, {"genreId": gid})
            names = [a["nameJa"] for a in d.get("ancestors", [])]
            if d.get("genre", {}).get("nameJa"):
                names.append(d["genre"]["nameJa"])
            _genres[k] = names
        except Exception:
            _genres[k] = []
    return _genres[k]


def categorize(path, name):
    p = " > ".join(path)
    top = path[0] if path else ""
    if top in ("日本酒・焼酎", "ビール・洋酒"):
        return "sake"
    if "フルーツ" in p or "果物" in p:
        return "fruit"
    if "肉" in p and top == "食品":
        return "meat"
    if "魚介" in p or "水産" in p:
        return "seafood"
    if "米・雑穀" in p or "野菜" in p:
        return "farm"
    if top in ("スイーツ・お菓子",):
        return "sweets"
    if top in ("食品", "水・ソフトドリンク"):
        return "food"
    if top in ("ジュエリー・アクセサリー", "キッチン用品・食器・調理器具", "インテリア・寝具・収納",
               "日用品雑貨・文房具・手芸", "バッグ・小物・ブランド雑貨", "ファッション", "花・ガーデン・DIY",
               "ホビー", "美容・コスメ・香水"):
        return "craft"
    if top in ("サービス・リフォーム", "旅行・出張・チケット") or "宿泊" in name or "体験" in name or "チケット" in name:
        return "stay"
    return "other"


def collect(code):
    rec = next((v for v in MUNI.values() if v.get("code") == code), None)
    if not rec or not rec.get("city"):
        print(f"  {code}: 自治体名が未解決のためスキップ"); return None
    items, page, pages = [], 1, 1
    while page <= min(pages, 100):
        d = _get(ITEM_EP, {"shopCode": code, "hits": 30, "page": page, "imageFlag": 1,
                           "affiliateId": CFG["affiliateId"]})
        pages = d.get("pageCount", 0) or 0
        for w in d.get("Items", []):
            it = w.get("Item", w)
            imgs = it.get("mediumImageUrls") or []
            img = imgs[0].get("imageUrl") if imgs and isinstance(imgs[0], dict) else ""
            if not img:
                continue
            path = genre_path(it.get("genreId"))
            items.append({
                "name": it.get("itemName", "").strip(),
                "price": int(it.get("itemPrice") or 0),
                "image": img.split("?")[0] + "?_ex=400x400",
                "url": it.get("affiliateUrl") or it.get("itemUrl"),
                "genre": path,
                "cat": categorize(path, it.get("itemName", "")),
                "review_count": int(it.get("reviewCount") or 0),
            })
        page += 1
    counts = {}
    for it in items:
        counts[it["cat"]] = counts.get(it["cat"], 0) + 1
    out = {"code": code, "pref": rec["pref"], "pref_slug": rec["pref_slug"], "city": rec["city"],
           "slug": rec["slug"], "collected_at": datetime.date.today().isoformat(),
           "source": f"楽天ふるさと納税（{rec['pref']}{rec['city']}）", "total": len(items),
           "counts": counts, "items": items}
    d = os.path.join(BASE, "data", "area", rec["pref_slug"])
    os.makedirs(d, exist_ok=True)
    json.dump(out, open(os.path.join(d, f"{rec['slug']}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(_genres, open(GENRE_CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    lab = {k: n for k, n, _ in CATEGORIES}
    summary = " / ".join(f"{lab.get(k, 'その他')}{v}" for k, v in sorted(counts.items(), key=lambda x: -x[1]))
    print(f"  {rec['pref']}{rec['city']}: {len(items)}件（{summary}）", flush=True)
    return out


def main():
    codes = DEMO10 if "--demo10" in sys.argv else [a for a in sys.argv[1:] if a.startswith("f")]
    print(f"{len(codes)}自治体を収集します", flush=True)
    for c in codes:
        try:
            collect(c)
        except Exception as e:
            print(f"  {c}: 失敗 {e}", flush=True)


if __name__ == "__main__":
    main()
