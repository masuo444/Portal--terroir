#!/usr/bin/env python3
"""
アウトリーチの対象台帳をつくる（送信はしない）。

5ジャンルの造り手データと、Search Console / GA4 の実測値を突き合わせて
「誰に・何の数字を根拠に声をかけられるか」を1つのJSONにまとめる。
数字が取れなかった相手は metrics=null のままにする（推測で埋めない）。

出力: data/outreach/targets.json
使い方:
  python3 scripts/outreach_targets.py                 # 前月ぶん
  python3 scripts/outreach_targets.py --ym 2026-08
  python3 scripts/outreach_targets.py --no-metrics    # 台帳だけ（API を呼ばない）
"""
import json, os, sys, glob, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
OUT_DIR = os.path.join(BASE, "data", "outreach")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import monthly_report_data as M

GENRE_UNIT = {g["key"]: (g["name"], g["unit"], g["domain"]) for g in M.GENRES}


def load_raw():
    """{(genre, id): 生データ}"""
    out = {}
    for g in M.GENRES:
        for jf in glob.glob(os.path.join(ROOT, g["data"])):
            pref = os.path.basename(jf).replace("data_", "").replace(g["suffix"], "")
            try:
                rows = json.load(open(jf, encoding="utf-8"))
            except Exception:
                continue
            for b in rows:
                if b.get("id"):
                    out[(g["key"], b["id"])] = (pref, b)
    return out


def main():
    ym = None
    if "--ym" in sys.argv:
        ym = sys.argv[sys.argv.index("--ym") + 1]
    use_metrics = "--no-metrics" not in sys.argv

    raw = load_raw()
    metrics, start, end, had_creds = ({}, None, None, False)
    if use_metrics:
        metrics, start, end, had_creds = M.collect(ym)
        if not had_creds:
            print("認証が無いため実測値は付けません（THUB_GOOGLE_SA_JSON）")
    if start is None:
        start, end = M.month_range(ym)

    mrows = {}
    for gk, rows in (metrics or {}).items():
        for r in rows:
            mrows[(gk, r["id"])] = r

    targets = []
    for (gk, bid), (pref, b) in sorted(raw.items()):
        name_g, unit, domain = GENRE_UNIT[gk]
        m = mrows.get((gk, bid))
        met = None
        if had_creds and m:
            met = {"impressions": m["impressions"], "clicks": m["clicks"],
                   "users": m["users"], "overseas_users": m["overseas_users"],
                   "position": m["position"], "queries": m["queries"][:3],
                   "furusato": m["furusato"]}
        site = (b.get("url") or "").strip()
        targets.append({
            "genre": gk, "genre_name": name_g, "unit": unit, "id": bid, "pref": pref,
            "name": b.get("name", ""), "company": b.get("company", "") or b.get("name", ""),
            "address": b.get("address", ""), "tel": (b.get("tel") or "").strip(),
            "site": site if site.startswith("http") else "",
            "page": f'https://{domain}/{gk}/{pref}/{bid}.html',
            "has_visit": bool((b.get("visit_info") or {}).get("status") in ("open", "limited")),
            "metrics": met,
        })

    os.makedirs(OUT_DIR, exist_ok=True)
    doc = {"generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "period": {"start": start.isoformat(), "end": end.isoformat(), "measured": had_creds},
           "count": len(targets), "targets": targets}
    json.dump(doc, open(os.path.join(OUT_DIR, "targets.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    withsite = sum(1 for t in targets if t["site"])
    withmet = sum(1 for t in targets if t["metrics"])
    shown = sum(1 for t in targets if (t["metrics"] or {}).get("impressions", 0) > 0)
    print(f'{len(targets)}者を台帳にしました（{start}〜{end}）')
    print(f'  公式サイトあり: {withsite}者　電話あり: {sum(1 for t in targets if t["tel"] and t["tel"] != "—")}者')
    print(f'  実測値あり: {withmet}者　うち表示回数1回以上: {shown}者')
    if shown:
        top = sorted((t for t in targets if t["metrics"]), key=lambda t: -t["metrics"]["impressions"])[:5]
        for t in top:
            print(f'    {t["name"]}（{t["pref"]}）: 表示{t["metrics"]["impressions"]}回 / 訪問{t["metrics"]["users"]}人')


if __name__ == "__main__":
    main()
