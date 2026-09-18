#!/usr/bin/env python3
"""
どの種類のページが Google に登録されているかを、URL検査APIで実測する。

Search Console の画面ではページ単位の理由が一括で取れないため、
サイトマップからセクションごとにサンプルを取り、1件ずつ検査して集計する。
（URL検査APIの上限は 1日2,000URL / 1分600URL）

出力: data/outreach/index_audit.json
使い方:
  python3 scripts/index_audit.py            # 各セクション8件ずつ
  python3 scripts/index_audit.py --n 15
"""
import os, sys, json, re, random, datetime, urllib.request, collections

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "sc-domain:terroirhub.com"
SITEMAPS = [
    "https://www.terroirhub.com/sitemap.xml",
    "https://sake.terroirhub.com/sitemap.xml",
    "https://wine.terroirhub.com/sitemap.xml",
    "https://shochu.terroirhub.com/sitemap.xml",
    "https://whisky.terroirhub.com/sitemap.xml",
    "https://liqueur.terroirhub.com/sitemap.xml",
]


def section(url):
    host = re.sub(r"https?://", "", url).split("/")[0]
    sub = host.split(".")[0]
    path = "/" + "/".join(url.split("/", 3)[3].split("/")) if url.count("/") > 3 else "/"
    parts = [p for p in path.split("/") if p]
    if sub == "www":
        if not parts:
            return "www トップ"
        if parts[0] == "area":
            return "www 地域ページ"
        if parts[0] == "furusato":
            return "www ふるさと納税"
        if parts[0] == "business":
            return "www 営業ページ"
        if parts[0] == "terroir":
            return "www テロワール"
        return "www その他"
    kind = "造り手"
    if len(parts) >= 2 and parts[1] in ("blog", "guide"):
        kind = parts[1]
    elif len(parts) >= 2 and parts[1] == "en":
        kind = "英語"
    elif len(parts) <= 1:
        kind = "トップ"
    elif len(parts) == 2 and parts[1].endswith("/"):
        kind = "県一覧"
    elif len(parts) == 2:
        kind = "県一覧" if not parts[1].endswith(".html") else "造り手"
    return f"{sub} {kind}"


def fetch_urls():
    out = []
    for sm in SITEMAPS:
        try:
            with urllib.request.urlopen(sm, timeout=40) as r:
                xml = r.read().decode("utf-8", "ignore")
        except Exception as e:
            print(f"  {sm}: 取得失敗 {e}")
            continue
        out += re.findall(r"<loc>([^<]+)</loc>", xml)
    return out


def main():
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 8
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import monthly_report_data as M
    creds = M._credentials()
    if not creds:
        print("THUB_GOOGLE_SA_JSON が無いため検査できません"); return
    from googleapiclient.discovery import build
    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)

    urls = fetch_urls()
    groups = collections.defaultdict(list)
    for u in urls:
        groups[section(u)].append(u)
    random.seed(20260918)

    result, rows = {}, []
    for sec in sorted(groups):
        sample = random.sample(groups[sec], min(n, len(groups[sec])))
        c = collections.Counter()
        for u in sample:
            try:
                r = svc.urlInspection().index().inspect(
                    body={"inspectionUrl": u, "siteUrl": SITE}).execute()
                i = r["inspectionResult"]["indexStatusResult"]
                state = i.get("coverageState", "?")
                c[state] += 1
                rows.append({"section": sec, "url": u, "state": state,
                             "verdict": i.get("verdict"), "last_crawl": i.get("lastCrawlTime", "")[:10]})
            except Exception as e:
                c["検査失敗"] += 1
                rows.append({"section": sec, "url": u, "state": "検査失敗", "error": str(e)[:120]})
        idx = sum(v for k, v in c.items() if "indexed" in k and "not" not in k.lower())
        result[sec] = {"total_urls": len(groups[sec]), "sampled": len(sample),
                       "indexed": idx, "states": dict(c)}
        bar = f'{idx}/{len(sample)}'
        print(f'  {sec:22} 全{len(groups[sec]):5}件　登録 {bar:6}　{ "、".join(f"{k}×{v}" for k,v in c.most_common(3)) }')

    os.makedirs(os.path.join(BASE, "data", "outreach"), exist_ok=True)
    json.dump({"checked_at": datetime.datetime.now().isoformat(timespec="seconds"),
               "sample_per_section": n, "summary": result, "rows": rows},
              open(os.path.join(BASE, "data", "outreach", "index_audit.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    tot = sum(v["sampled"] for v in result.values())
    idx = sum(v["indexed"] for v in result.values())
    print(f'\n全体: {idx}/{tot} が登録済み（サンプル）')


if __name__ == "__main__":
    main()
