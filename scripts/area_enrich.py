#!/usr/bin/env python3
"""
地域ページの文章を AI で作る（事実は作らせない）。

AI にやらせるのは次の3つだけ:
  1. 返礼品名からの「事業者名の抽出」（商品名に書かれているものだけ。推測禁止）
  2. 渡した事実（件数・代表的な品目・収録済みの造り手）だけを使った紹介文の作成
  3. その英訳

渡していない事実は書かせない。人物・受賞・創業年・味の評価などは一切扱わない。
出力は「下書き」であり、公開前に事業者・自治体の確認を受ける前提。

使い方:
  python3 scripts/area_enrich.py nagano/tomi          # 1地域
  python3 scripts/area_enrich.py --all                # data/area にある全地域
  python3 scripts/area_enrich.py nagano/tomi --dry    # 費用見積もりだけ（APIを呼ばない）
"""
import json, os, sys, glob, re, urllib.request, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
OUT_DIR = os.path.join(BASE, "data", "area_text")
API = "https://api.anthropic.com/v1/messages"
JPY = 155.0
PRICE = {"claude-opus-5": (5.0, 25.0), "claude-haiku-4-5": (1.0, 5.0)}
CATS = [("sake", "酒"), ("fruit", "果物"), ("meat", "肉"), ("seafood", "魚介"),
        ("farm", "米・野菜"), ("food", "加工品・調味料"), ("sweets", "菓子"),
        ("craft", "工芸・ものづくり"), ("stay", "体験・宿泊")]
USAGE = {"in": 0, "out": 0, "cost": 0.0, "calls": 0}


def api_key():
    for p in [os.path.join(ROOT, "TerriorHUB　sake", ".env.production.local"),
              os.path.join(ROOT, "TerriorHUB　sake", ".env.local")]:
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                if line.startswith("ANTHROPIC_API_KEY"):
                    return line.split("=", 1)[1].strip().strip('"')
    return os.environ.get("ANTHROPIC_API_KEY", "")


KEY = api_key()


def call(model, system, user, max_tokens=2000):
    body = {"model": model, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": user}]}
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={
        "x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.load(r)
            u = d.get("usage", {})
            pin, pout = PRICE.get(model, (1.0, 5.0))
            USAGE["in"] += u.get("input_tokens", 0)
            USAGE["out"] += u.get("output_tokens", 0)
            USAGE["cost"] += (u.get("input_tokens", 0) / 1e6 * pin + u.get("output_tokens", 0) / 1e6 * pout) * JPY
            USAGE["calls"] += 1
            return "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
        except Exception as e:
            if attempt < 3:
                time.sleep(4 * (attempt + 1)); continue
            print(f"    API失敗: {str(e)[:120]}")
            return ""
    return ""


def jsonify(txt):
    m = re.search(r'\{.*\}|\[.*\]', txt, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


EXTRACT_SYS = """あなたは日本の返礼品リストから事業者名を抽出する担当です。

絶対の規則:
- 商品名に明示的に書かれている事業者名・工房名・農園名・蔵元名だけを抜き出す
- 書かれていない事業者名を推測して補ってはいけない
- 産地名・自治体名・ブランド名だけのもの（例：佐賀牛、飛騨）は事業者名ではないので除外
- 確信が持てないものは出力しない

出力は JSON 配列のみ。例: ["〇〇醸造","△△農園"]"""

INTRO_SYS = """あなたは日本の地域紹介文を書く編集者です。

絶対の規則:
- 与えられた事実だけを使う。与えられていない事実（創業年・受賞歴・味の評価・歴史・人物）は書かない
- 産地の一般的な知識であっても、与えられていなければ書かない
- 誇大な表現（日本一、最高、絶品）は使わない
- 断定できないことは書かない

出力は JSON のみ:
{"intro":"140〜200字の地域紹介","cats":{"カテゴリキー":"40〜70字の説明", ...}}"""


def build_facts(d, producers):
    lines = [f'地域: {d["pref"]}{d["city"]}', f'掲載している返礼品の総数: {d["total"]}件']
    for k, n in CATS:
        c = d["counts"].get(k, 0)
        if not c:
            continue
        items = [i for i in d["items"] if i["cat"] == k]
        items.sort(key=lambda x: -x.get("review_count", 0))
        ex = "／".join(re.sub(r'^[【\[]?\s*ふるさと納税\s*[】\]]?\s*', '', i["name"])[:28] for i in items[:4])
        lines.append(f'- {n}（キー: {k}）: {c}件。代表的な品目: {ex}')
    if producers:
        lines.append("当サイトが収録している、この地域の酒の造り手: " + "、".join(producers[:12]))
    return "\n".join(lines)


def load_producers(pref, city):
    out, key = [], (pref + city).replace(" ", "")
    specs = [("TerriorHUB　sake/data_*_breweries.json",), ("terroirHUB wine/data/data_*_wineries.json",),
             ("terroirHUB 焼酎/data/data_*_distilleries.json",), ("terroirHUB whisky/data/data_*_distilleries.json",),
             ("terroirHUB liqueur/data/data_*_liqueurs.json",)]
    for (pat,) in specs:
        for jf in glob.glob(os.path.join(ROOT, pat)):
            try:
                rows = json.load(open(jf, encoding="utf-8"))
            except Exception:
                continue
            for b in rows:
                a = (b.get("address") or "").replace(" ", "").replace("　", "")
                if a.startswith(key) and b.get("name"):
                    out.append(b["name"])
    return sorted(set(out))


def enrich(path, dry=False):
    d = json.load(open(path, encoding="utf-8"))
    producers = load_producers(d["pref"], d["city"])
    facts = build_facts(d, producers)
    names = [re.sub(r'^[【\[]?\s*ふるさと納税\s*[】\]]?\s*', '', i["name"])[:60] for i in d["items"]]
    chunks = [names[i:i + 60] for i in range(0, len(names), 60)]
    print(f'{d["pref"]}{d["city"]}: 返礼品{d["total"]}件 / 抽出{len(chunks)}回 + 文章2回')
    if dry:
        est = (len(chunks) * 2500 / 1e6 * 1.0 + len(chunks) * 300 / 1e6 * 5.0) * JPY + (4000 / 1e6 * 5 + 1500 / 1e6 * 25) * JPY * 2
        print(f'  概算費用: 約{est:.0f}円')
        return None

    # 1) 事業者名の抽出（大量処理なので Haiku）
    found = []
    for i, ch in enumerate(chunks, 1):
        txt = call("claude-haiku-4-5", EXTRACT_SYS,
                   "次の返礼品名から事業者名を抽出してください。\n\n" + "\n".join(ch), max_tokens=900)
        arr = jsonify(txt) or []
        found += [str(x).strip() for x in arr if isinstance(x, (str,)) and 1 < len(str(x)) < 40]
        print(f'    抽出 {i}/{len(chunks)}', end="\r", flush=True)
    cnt = {}
    for n in found:
        cnt[n] = cnt.get(n, 0) + 1
    biz = [n for n, c in sorted(cnt.items(), key=lambda x: -x[1])]
    print(f'    事業者候補 {len(biz)}件                     ')

    # 2) 紹介文（事実だけを渡す）
    ja = jsonify(call("claude-opus-5", INTRO_SYS,
                      "次の事実だけを使って、地域紹介文とカテゴリ説明を書いてください。\n\n" + facts, max_tokens=2000)) or {}
    # 3) 英訳
    en = {}
    if ja:
        en = jsonify(call("claude-opus-5",
                          "あなたは翻訳者です。与えられた日本語を自然な英語にします。事実の追加・削除はしません。出力は同じ構造のJSONのみ。",
                          json.dumps(ja, ensure_ascii=False), max_tokens=2000)) or {}

    out = {"pref": d["pref"], "city": d["city"], "pref_slug": d["pref_slug"], "slug": d["slug"],
           "intro_ja": ja.get("intro", ""), "cats_ja": ja.get("cats", {}),
           "intro_en": en.get("intro", ""), "cats_en": en.get("cats", {}),
           "businesses": biz, "facts_used": facts,
           "note": "文章は掲載データのみを根拠にAIが作成した下書き。公開前に事業者・自治体の確認を受けること。"}
    dd = os.path.join(OUT_DIR, d["pref_slug"])
    os.makedirs(dd, exist_ok=True)
    json.dump(out, open(os.path.join(dd, f'{d["slug"]}.json'), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out


def main():
    dry = "--dry" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--all" in sys.argv:
        paths = sorted(glob.glob(os.path.join(BASE, "data", "area", "*", "*.json")))
    else:
        paths = [os.path.join(BASE, "data", "area", a + ".json") for a in args]
    if not KEY and not dry:
        print("ANTHROPIC_API_KEY が見つかりません"); return
    for p in paths:
        if not os.path.exists(p):
            print(f"{p} がありません"); continue
        enrich(p, dry)
    if USAGE["calls"]:
        print(f'\n実費: 約{USAGE["cost"]:.1f}円（{USAGE["calls"]}回 / 入力{USAGE["in"]:,}・出力{USAGE["out"]:,}トークン）')


if __name__ == "__main__":
    main()
