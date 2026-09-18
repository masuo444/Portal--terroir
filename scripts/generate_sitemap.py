#!/usr/bin/env python3
"""
www.terroirhub.com の sitemap.xml を生成する（実在するHTMLだけ・noindexは除外）。

2026-09-18: 「core方式」で作る。URL検査APIで調べたところ、
  /terroir/ は 5/8 登録済みなのに、/furusato/ の市町村ページ482枚は 0/8
  （Discovered - currently not indexed ＝ 存在は知られているが読まれない）、
  /area/ も 0/8 だった。自動生成の市町村ページにクロール予算を食われて、
  本格版の地域ページが読まれていない。
  そこで市町村ページはサイトマップから外し（ページと内部リンクは残す）、
  県インデックスと本格版の地域ページにクロールを集中させる。
  全件版が要るときは --all を付ける。

使い方: python3 scripts/generate_sitemap.py
"""
import os, re, sys, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMAIN = "https://www.terroirhub.com"
TODAY = datetime.date.today().isoformat()
CORE_ONLY = "--all" not in sys.argv

# 公開対象外（アプリ・素材・作業用）
SKIP_DIRS = {"api", "scripts", "data", "img", "node_modules", "demo", "admin",
             "components", "drafts", "reports", "proposals", ".git", ".vercel"}
SKIP_FILES = {"404.html", "sakura-widget.html", "lp-btob.html"}

# 市町村ごとのふるさと納税ページ（/furusato/<県>/<市区町村>/）
MUNI = re.compile(r"^furusato/[a-z_]+/[a-z0-9_-]+/index\.html$")


def priority(rel):
    if rel == "index.html":
        return "1.0"
    if rel.startswith("area/"):
        return "0.9"
    if rel.startswith("terroir/"):
        return "0.8"
    if rel.startswith("furusato/"):
        return "0.8"
    if rel.startswith("business/") or rel.startswith("listing-update"):
        return "0.7"
    return "0.6"


def url_for(rel):
    return f"{DOMAIN}/" + (rel[:-len("index.html")] if rel.endswith("index.html") else rel)


def main():
    rows, skipped = [], {"noindex": 0, "muni": 0}
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in files:
            if not fn.endswith(".html") or fn in SKIP_FILES:
                continue
            rel = os.path.relpath(os.path.join(root, fn), BASE).replace(os.sep, "/")
            if CORE_ONLY and MUNI.match(rel):
                skipped["muni"] += 1
                continue
            try:
                head = open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read(4000)
            except Exception:
                continue
            if re.search(r'name=["\']robots["\'][^>]*noindex', head, re.I):
                skipped["noindex"] += 1
                continue
            rows.append(rel)

    rows.sort(key=lambda r: (r != "index.html", r))
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    seen = set()
    for rel in rows:
        u = url_for(rel)
        if u in seen:
            continue
        seen.add(u)
        out.append(f'  <url>\n    <loc>{u}</loc>\n    <lastmod>{TODAY}</lastmod>'
                   f'\n    <priority>{priority(rel)}</priority>\n  </url>')
    out.append("</urlset>\n")
    open(os.path.join(BASE, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(out))

    kinds = {}
    for rel in rows:
        k = rel.split("/")[0] if "/" in rel else "（トップ・固定）"
        kinds[k] = kinds.get(k, 0) + 1
    print(f"sitemap.xml 生成: {len(seen)} URL"
          + (f"（core方式: 市町村ページ {skipped['muni']}枚を除外）" if CORE_ONLY else "（--all: 全件）")
          + f"　noindex除外 {skipped['noindex']}枚")
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        print(f"   {v:5}  /{k}")


if __name__ == "__main__":
    main()
