#!/usr/bin/env python3
"""
月次レポートのデータ層。Search Console と GA4 から当月の実績を取り、
Terroir HUB の生産者ページ単位に集計する。

認証（どちらも無ければ、その指標は「無し」として扱う。推測では埋めない）:
  THUB_GOOGLE_SA_JSON   サービスアカウントJSONのパス
  THUB_GA4_PROPERTY_<GENRE>  GA4のプロパティID（数値）。例: THUB_GA4_PROPERTY_SAKE=123456789

Search Console 側はサービスアカウントを各プロパティの「ユーザー」に追加しておくこと。
"""
import os, json, glob, datetime, collections

GENRES = [
    dict(key="sake", name="日本酒", unit="酒蔵", domain="sake.terroirhub.com",
         path="sake", data="TerriorHUB　sake/data_*_breweries.json", suffix="_breweries.json"),
    dict(key="wine", name="日本ワイン", unit="ワイナリー", domain="wine.terroirhub.com",
         path="wine", data="terroirHUB wine/data/data_*_wineries.json", suffix="_wineries.json"),
    dict(key="shochu", name="焼酎・泡盛", unit="蔵", domain="shochu.terroirhub.com",
         path="shochu", data="terroirHUB 焼酎/data/data_*_distilleries.json", suffix="_distilleries.json"),
    dict(key="whisky", name="ウイスキー", unit="蒸溜所", domain="whisky.terroirhub.com",
         path="whisky", data="terroirHUB whisky/data/data_*_distilleries.json", suffix="_distilleries.json"),
    dict(key="liqueur", name="梅酒・リキュール", unit="メーカー", domain="liqueur.terroirhub.com",
         path="liqueur", data="terroirHUB liqueur/data/data_*_liqueurs.json", suffix="_liqueurs.json"),
]

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly",
          "https://www.googleapis.com/auth/analytics.readonly"]

# GA4のプロパティID（数値）。測定ID(G-...)とは別物。2026-09-15にAdmin APIで確認。
# 環境変数 THUB_GA4_PROPERTY_<GENRE> があればそちらを優先する。
GA4_PROPERTY = {
    "sake": "529921642",
    "wine": "534564535",
    "shochu": "529923851",
    "whisky": "531246960",
    "liqueur": "531285585",
    "portal": "531278763",
}


# ── 生産者インデックス ────────────────────────────────────────────
def load_producers():
    """{genre_key: {page_path: producer}} — page_path は '/sake/yamanashi/xxx.html'"""
    out = {}
    for g in GENRES:
        m = {}
        for jf in glob.glob(os.path.join(ROOT, g["data"])):
            pref = os.path.basename(jf).replace("data_", "").replace(g["suffix"], "")
            try:
                rows = json.load(open(jf, encoding="utf-8"))
            except Exception:
                continue
            for b in rows:
                bid = b.get("id")
                if not bid:
                    continue
                p = f'/{g["path"]}/{pref}/{bid}.html'
                m[p] = {"id": bid, "name": b.get("name", ""), "pref": pref,
                        "genre": g["key"], "page": p, "address": b.get("address", ""),
                        "url": f'https://{g["domain"]}{p}'}
                # 英語ページも同じ蔵に合算する
                m[f'/{g["path"]}/en/{pref}/{bid}.html'] = m[p]
        out[g["key"]] = m
    return out


# ── 認証 ──────────────────────────────────────────────────────────
def _credentials():
    path = os.environ.get("THUB_GOOGLE_SA_JSON")
    if not path or not os.path.exists(path):
        return None
    try:
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
    except Exception as e:
        print(f"  認証に失敗: {e}")
        return None


def month_range(ym=None):
    """ym='2026-08' → (開始日, 終了日)。未指定なら前月。"""
    today = datetime.date.today()
    if ym:
        y, m = (int(x) for x in ym.split("-"))
    else:
        first = today.replace(day=1)
        prev = first - datetime.timedelta(days=1)
        y, m = prev.year, prev.month
    start = datetime.date(y, m, 1)
    end = (datetime.date(y + (m == 12), (m % 12) + 1, 1) - datetime.timedelta(days=1))
    return start, min(end, today)


# ── Search Console ───────────────────────────────────────────────
GSC_PROPERTY = os.environ.get("THUB_GSC_PROPERTY", "sc-domain:terroirhub.com")


def fetch_gsc(creds, domain, start, end, _cache={}):
    """ドメインプロパティから1回だけ取得し、以降はキャッシュを返す（domainは互換のため残す）"""
    key = (start, end)
    if key not in _cache:
        _cache[key] = _fetch_gsc_domain(creds, start, end)
    return _cache[key]


def _fetch_gsc_domain(creds, start, end):
    """{page_path: {impressions, clicks, position, queries:[(q, imp)], countries:{}}}"""
    if not creds:
        return {}
    from googleapiclient.discovery import build
    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    site = GSC_PROPERTY
    out = collections.defaultdict(lambda: {"impressions": 0, "clicks": 0, "pos_sum": 0.0,
                                           "rows": 0, "queries": [], "countries": {}})

    def run(dims, limit=25000):
        body = {"startDate": start.isoformat(), "endDate": end.isoformat(),
                "dimensions": dims, "rowLimit": limit}
        try:
            return svc.searchanalytics().query(siteUrl=site, body=body).execute().get("rows", [])
        except Exception as e:
            print(f"  GSC {site} {dims}: {e}")
            return []

    for r in run(["page"]):
        p = _pathof(r["keys"][0])
        d = out[p]
        d["impressions"] += int(r.get("impressions", 0))
        d["clicks"] += int(r.get("clicks", 0))
        d["pos_sum"] += float(r.get("position", 0)) * int(r.get("impressions", 0))
        d["rows"] += 1
    for r in run(["page", "query"]):
        p = _pathof(r["keys"][0])
        out[p]["queries"].append((r["keys"][1], int(r.get("impressions", 0))))
    for r in run(["page", "country"]):
        p = _pathof(r["keys"][0])
        out[p]["countries"][r["keys"][1]] = out[p]["countries"].get(r["keys"][1], 0) + int(r.get("impressions", 0))
    for d in out.values():
        d["position"] = round(d["pos_sum"] / d["impressions"], 1) if d["impressions"] else None
        d["queries"].sort(key=lambda x: -x[1])
    return dict(out)


def _pathof(url):
    if url.startswith("http"):
        i = url.find("/", 8)
        return url[i:] if i > 0 else "/"
    return url


# ── GA4 ───────────────────────────────────────────────────────────
def fetch_ga4(creds, property_id, start, end):
    """{page_path: {sessions, users, overseas_users}}"""
    if not creds or not property_id:
        return {}
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest)
    except Exception:
        return _ga4_rest(creds, property_id, start, end)
    client = BetaAnalyticsDataClient(credentials=creds)
    out = collections.defaultdict(lambda: {"sessions": 0, "users": 0, "overseas_users": 0})
    req = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
        dimensions=[Dimension(name="pagePath"), Dimension(name="country")],
        metrics=[Metric(name="sessions"), Metric(name="totalUsers")],
        limit=100000)
    try:
        resp = client.run_report(req)
    except Exception as e:
        print(f"  GA4 {property_id}: {e}")
        return {}
    for row in resp.rows:
        path = row.dimension_values[0].value
        country = row.dimension_values[1].value
        s = int(row.metric_values[0].value or 0)
        u = int(row.metric_values[1].value or 0)
        d = out[path]
        d["sessions"] += s
        d["users"] += u
        if country != "Japan":
            d["overseas_users"] += u
    return dict(out)


def _ga4_rest(creds, property_id, start, end):
    """google-analytics-data が無い環境向けのRESTフォールバック"""
    import google.auth.transport.requests as gart
    import requests
    creds.refresh(gart.Request())
    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
    body = {"dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
            "dimensions": [{"name": "pagePath"}, {"name": "country"}],
            "metrics": [{"name": "sessions"}, {"name": "totalUsers"}], "limit": 100000}
    try:
        r = requests.post(url, json=body, headers={"Authorization": f"Bearer {creds.token}"}, timeout=60)
        if r.status_code != 200:
            print(f"  GA4 {property_id}: HTTP {r.status_code} {r.text[:120]}")
            return {}
        data = r.json()
    except Exception as e:
        print(f"  GA4 {property_id}: {e}")
        return {}
    out = collections.defaultdict(lambda: {"sessions": 0, "users": 0, "overseas_users": 0})
    for row in data.get("rows", []):
        path = row["dimensionValues"][0]["value"]
        country = row["dimensionValues"][1]["value"]
        s = int(row["metricValues"][0]["value"] or 0)
        u = int(row["metricValues"][1]["value"] or 0)
        d = out[path]
        d["sessions"] += s
        d["users"] += u
        if country != "Japan":
            d["overseas_users"] += u
    return dict(out)


# ── ふるさと納税の掲載件数（自社データ）───────────────────────────
def furusato_counts():
    """{genre: {producer_id: 件数}}"""
    out = {}
    for g in GENRES:
        p = os.path.join(ROOT, os.path.dirname(g["data"]).replace("/data", ""), "")
        items_path = {
            "sake": "TerriorHUB　sake/sake/rakuten_items.json",
            "wine": "terroirHUB wine/wine/rakuten_items.json",
            "shochu": "terroirHUB 焼酎/shochu/rakuten_items.json",
            "whisky": "terroirHUB whisky/whisky/rakuten_items.json",
            "liqueur": "terroirHUB liqueur/liqueur/rakuten_items.json",
        }[g["key"]]
        f = os.path.join(ROOT, items_path)
        c = {}
        if os.path.exists(f):
            try:
                d = json.load(open(f, encoding="utf-8"))
                for bid, grp in d.items():
                    n = sum(1 for i in grp.get("items", []) if "ふるさと納税" in i.get("name", ""))
                    if n:
                        c[bid.split(":")[-1]] = n
            except Exception:
                pass
        out[g["key"]] = c
    return out


def collect(ym=None):
    """1か月分を集計して {genre: [producer_with_metrics]} を返す"""
    start, end = month_range(ym)
    creds = _credentials()
    producers = load_producers()
    fur = furusato_counts()
    result = {}
    for g in GENRES:
        gsc = fetch_gsc(creds, g["domain"], start, end)
        prop = (os.environ.get(f'THUB_GA4_PROPERTY_{g["key"].upper()}')
                or GA4_PROPERTY.get(g["key"]))
        ga4 = fetch_ga4(creds, prop, start, end)
        rows = {}
        for path, prod in producers[g["key"]].items():
            key = prod["id"]
            r = rows.setdefault(key, {**prod, "impressions": 0, "clicks": 0, "sessions": 0,
                                      "users": 0, "overseas_users": 0, "queries": [],
                                      "position": None, "furusato": fur[g["key"]].get(prod["id"], 0)})
            s = gsc.get(path)
            if s:
                r["impressions"] += s["impressions"]
                r["clicks"] += s["clicks"]
                r["queries"].extend(s["queries"])
                if s.get("position") is not None:
                    r["position"] = s["position"] if r["position"] is None else min(r["position"], s["position"])
            a = ga4.get(path)
            if a:
                r["sessions"] += a["sessions"]
                r["users"] += a["users"]
                r["overseas_users"] += a["overseas_users"]
        for r in rows.values():
            r["queries"] = sorted(r["queries"], key=lambda x: -x[1])[:5]
        result[g["key"]] = sorted(rows.values(), key=lambda r: -r["impressions"])
    return result, start, end, bool(creds)
