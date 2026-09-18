#!/usr/bin/env python3
"""
収集した見学情報（visit_info）を検証してから、各ジャンルの蔵データに取り込む。

収集は別プロセス（エージェント）が行い、結果を /tmp/visit_tasks/out_*.json に置く。
このスクリプトは**取り込む前の門番**で、次を確認する。通らないものは捨てる。

  1. 対象の蔵が実在するか（pref と id がデータにあるか）
  2. スキーマ（status/reservation/tasting/english の値が規定のものか、空文字やnullが無いか）
  3. source（出典URL）と last_checked（確認日）が揃っているか
  4. **出典URLが実際に開けるか**（HTTPで確認。404や接続不可は採用しない）
  5. found:false に visit_info が紛れ込んでいないか

使い方:
  python3 scripts/merge_visit_info.py --check          # 検証だけ（書き込まない）
  python3 scripts/merge_visit_info.py --check --no-http # URL確認を省く（速い）
  python3 scripts/merge_visit_info.py --apply          # 検証を通ったものを書き込む
"""
import os, re, sys, json, glob, ssl, datetime, urllib.request, urllib.parse, urllib.error
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
IN_DIR = "/tmp/visit_tasks"

GENRES = {
    "whisky": "terroirHUB whisky/data/data_{pref}_distilleries.json",
    "wine": "terroirHUB wine/data/data_{pref}_wineries.json",
    "shochu": "terroirHUB 焼酎/data/data_{pref}_distilleries.json",
}
# 出力ファイル名 → ジャンル
SOURCES = {"out_whisky.json": "whisky", "out_wine_yamanashi.json": "wine",
           "out_wine_other.json": "wine", "out_shochu.json": "shochu"}

ENUM = {
    "status": {"open", "paused", "closed", "inquire"},
    "reservation": {"required", "recommended", "not_required", "inquire"},
    "tasting": {"paid", "free", "available", "none"},
    "english": {"tour", "materials", "none"},
}
ALLOWED = set(ENUM) | {"reservation_url", "fee", "duration", "shop", "facility",
                       "notes_ja", "notes_en", "source", "last_checked"}

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126 Safari/537.36"}
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def load_data(genre, pref):
    p = os.path.join(ROOT, GENRES[genre].format(pref=pref))
    if not os.path.exists(p):
        return None, None
    return p, json.load(open(p, encoding="utf-8"))


def url_ok(u):
    """出典URLが開けるか。404や接続不可なら False"""
    # 日本語を含むURL（例 /施設紹介/）はパーセントエンコードしないと接続できない
    try:
        sp = urllib.parse.urlsplit(u)
        u = urllib.parse.urlunsplit((sp.scheme, sp.netloc,
                                     urllib.parse.quote(sp.path, safe="/%"),
                                     urllib.parse.quote(sp.query, safe="=&%"), ""))
    except Exception:
        pass
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(u, headers=UA, method=method)
            with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
                if r.status < 400:
                    return True
        except urllib.error.HTTPError as e:
            if e.code in (403, 405, 406) and method == "HEAD":
                continue          # HEADを拒む site は GET で試す
            if e.code < 400:
                return True
        except Exception:
            if method == "HEAD":
                continue
    return False


def validate(rec, genre, cache):
    """1件を検証し、(採用する visit_info または None, 理由) を返す"""
    pref, bid = rec.get("pref"), rec.get("id")
    if not pref or not bid:
        return None, "pref/idが無い"
    path, rows = load_data(genre, pref)
    if rows is None:
        return None, f"データファイルが無い（{pref}）"
    if not any(b.get("id") == bid for b in rows):
        return None, f"その蔵がデータに無い（{pref}:{bid}）"
    if not rec.get("found"):
        if rec.get("visit_info"):
            return None, "found:false なのに visit_info がある"
        return None, "記載なし（対象外）"
    v = rec.get("visit_info") or {}
    if not isinstance(v, dict) or not v:
        return None, "visit_info が空"
    for k in list(v):
        if k not in ALLOWED:
            return None, f"想定外のキー: {k}"
        if v[k] is None or v[k] == "":
            return None, f"空の値: {k}"
    for k, allowed in ENUM.items():
        if k in v and v[k] not in allowed:
            return None, f"{k} の値が規定外: {v[k]}"
    if "status" not in v:
        return None, "status が無い"
    if not v.get("source"):
        return None, "出典URLが無い"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v.get("last_checked", ""))):
        return None, "last_checked が無い/形式不正"
    if not str(v["source"]).startswith("http"):
        return None, "出典URLの形式が不正"
    if cache is not None:
        if v["source"] not in cache:
            cache[v["source"]] = url_ok(v["source"])
        if not cache[v["source"]]:
            return None, f"出典URLが開けない: {v['source'][:60]}"
    return v, "ok"


def main():
    do_apply = "--apply" in sys.argv
    check_http = "--no-http" not in sys.argv

    records = []
    for fn, genre in SOURCES.items():
        p = os.path.join(IN_DIR, fn)
        if not os.path.exists(p):
            print(f"  {fn}: まだ無い")
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            print(f"  {fn}: 読めない {e}")
            continue
        for rec in d:
            records.append((genre, rec))
        print(f"  {fn}: {len(d)}件（{genre}）")
    if not records:
        print("入力がありません"); return

    # 出典URLの生存確認を並列で先に済ませる
    cache = {} if check_http else None
    if check_http:
        urls = sorted({(r.get("visit_info") or {}).get("source")
                       for _, r in records if r.get("found") and (r.get("visit_info") or {}).get("source")})
        urls = [u for u in urls if u]
        print(f"\n出典URLの生存確認: {len(urls)}件")
        with ThreadPoolExecutor(max_workers=8) as ex:
            for u, ok in zip(urls, ex.map(url_ok, urls)):
                cache[u] = ok
        print(f"  開けた {sum(cache.values())} / 開けない {len(cache)-sum(cache.values())}")

    ok_by = {}
    reasons = {}
    for genre, rec in records:
        v, why = validate(rec, genre, cache)
        reasons[why.split("（")[0].split(":")[0]] = reasons.get(why.split("（")[0].split(":")[0], 0) + 1
        if v:
            ok_by.setdefault((genre, rec["pref"]), []).append((rec["id"], v))

    total = sum(len(x) for x in ok_by.values())
    print(f"\n検証結果: 採用 {total}件")
    for k, n in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"   {n:4}  {k}")

    if not do_apply:
        print("\n（--apply で蔵データへ書き込み）")
        return

    written = 0
    for (genre, pref), items in sorted(ok_by.items()):
        path, rows = load_data(genre, pref)
        idx = {b.get("id"): b for b in rows}
        for bid, v in items:
            idx[bid]["visit_info"] = v
            written += 1
        json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{written}件を書き込みました")


if __name__ == "__main__":
    main()
