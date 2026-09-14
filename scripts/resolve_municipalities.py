#!/usr/bin/env python3
"""
各ジャンルの rakuten_items.json から【ふるさと納税】返礼品を集め、
楽天の店舗コード（f+JISコード6桁-ローマ字）から自治体を同定して
data/furusato_municipalities.json を作る。

- 自治体名は楽天の店舗ページ<title>から取得（「楽天市場 | 宮崎県都城市 - ...」）。
  出典が明確で、推測で埋めない（RULES.md準拠）。
- 取得済みはキャッシュして再取得しない（追記型・中断再開可）。
- 楽天APIは使わない（商品取得バッチとQPSを取り合わないため）。

使い方: python3 scripts/resolve_municipalities.py [--limit N]
"""
import json, os, re, sys, time, glob, urllib.request, urllib.error, urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASE)
OUT = os.path.join(BASE, 'data', 'furusato_municipalities.json')
SLEEP = 1.0

GENRES = [
    ('sake',    'TerriorHUB　sake/sake/rakuten_items.json'),
    ('wine',    'terroirHUB wine/wine/rakuten_items.json'),
    ('shochu',  'terroirHUB 焼酎/shochu/rakuten_items.json'),
    ('whisky',  'terroirHUB whisky/whisky/rakuten_items.json'),
    ('liqueur', 'terroirHUB liqueur/liqueur/rakuten_items.json'),
]

PREF_BY_CODE = {
    '01':'北海道','02':'青森県','03':'岩手県','04':'宮城県','05':'秋田県','06':'山形県','07':'福島県',
    '08':'茨城県','09':'栃木県','10':'群馬県','11':'埼玉県','12':'千葉県','13':'東京都','14':'神奈川県',
    '15':'新潟県','16':'富山県','17':'石川県','18':'福井県','19':'山梨県','20':'長野県','21':'岐阜県',
    '22':'静岡県','23':'愛知県','24':'三重県','25':'滋賀県','26':'京都府','27':'大阪府','28':'兵庫県',
    '29':'奈良県','30':'和歌山県','31':'鳥取県','32':'島根県','33':'岡山県','34':'広島県','35':'山口県',
    '36':'徳島県','37':'香川県','38':'愛媛県','39':'高知県','40':'福岡県','41':'佐賀県','42':'長崎県',
    '43':'熊本県','44':'大分県','45':'宮崎県','46':'鹿児島県','47':'沖縄県',
}
PREF_SLUG = {
    '北海道':'hokkaido','青森県':'aomori','岩手県':'iwate','宮城県':'miyagi','秋田県':'akita','山形県':'yamagata',
    '福島県':'fukushima','茨城県':'ibaraki','栃木県':'tochigi','群馬県':'gunma','埼玉県':'saitama','千葉県':'chiba',
    '東京都':'tokyo','神奈川県':'kanagawa','新潟県':'niigata','富山県':'toyama','石川県':'ishikawa','福井県':'fukui',
    '山梨県':'yamanashi','長野県':'nagano','岐阜県':'gifu','静岡県':'shizuoka','愛知県':'aichi','三重県':'mie',
    '滋賀県':'shiga','京都府':'kyoto','大阪府':'osaka','兵庫県':'hyogo','奈良県':'nara','和歌山県':'wakayama',
    '鳥取県':'tottori','島根県':'shimane','岡山県':'okayama','広島県':'hiroshima','山口県':'yamaguchi',
    '徳島県':'tokushima','香川県':'kagawa','愛媛県':'ehime','高知県':'kochi','福岡県':'fukuoka','佐賀県':'saga',
    '長崎県':'nagasaki','熊本県':'kumamoto','大分県':'oita','宮崎県':'miyazaki','鹿児島県':'kagoshima','沖縄県':'okinawa',
}

SHOP_RE = re.compile(r'item\.rakuten\.co\.jp/(f\d{6}-[a-z0-9_\-]+)/')


def collect_shops():
    """{shop_code: {genres:set, items:int}} を返す"""
    shops = {}
    for gkey, rel in GENRES:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding='utf-8'))
        for bid, grp in d.items():
            for it in grp.get('items', []):
                if 'ふるさと納税' not in it.get('name', ''):
                    continue
                u = urllib.parse.unquote(it.get('url', '') or '')
                m = SHOP_RE.search(u)
                if not m:
                    continue
                code = m.group(1)
                e = shops.setdefault(code, {'genres': set(), 'items': 0})
                e['genres'].add(gkey)
                e['items'] += 1
    return shops


def fetch_title(code):
    url = f'https://www.rakuten.co.jp/{code}/'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept-Language': 'ja'})
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode('utf-8', 'replace')
    m = re.search(r'<title>(.*?)</title>', html, re.S)
    return m.group(1).strip() if m else ''


def parse_name(title, pref):
    """『楽天市場 | 宮崎県都城市 - ...』→ ('宮崎県','都城市')。県が一致しなければNone"""
    m = re.search(r'楽天市場\s*[|｜]\s*([^-－\n]+?)\s*[-－]', title)
    seg = (m.group(1) if m else '').strip()
    if not seg.startswith(pref):
        return None
    city = seg[len(pref):].strip()
    return city or None


def main():
    limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None
    cache = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
    shops = collect_shops()
    print(f'ふるさと納税の店舗コード: {len(shops)}件 / 解決済み {len(cache)}件')
    todo = [c for c in shops if c not in cache or not cache[c].get('city')]
    if limit:
        todo = todo[:limit]
    print(f'今回取得: {len(todo)}件')
    ng = 0
    for i, code in enumerate(todo):
        jis6 = code[1:7]
        pref = PREF_BY_CODE.get(jis6[:2], '')
        rec = {'code': code, 'jis': jis6[:5], 'pref': pref,
               'pref_slug': PREF_SLUG.get(pref, ''), 'slug': code.split('-', 1)[1],
               'city': None, 'title': ''}
        try:
            time.sleep(SLEEP)
            t = fetch_title(code)
            rec['title'] = t[:200]
            rec['city'] = parse_name(t, pref)
        except urllib.error.HTTPError as e:
            rec['error'] = f'HTTP {e.code}'
        except Exception as e:
            rec['error'] = type(e).__name__
        if not rec['city']:
            ng += 1
        cache[code] = rec
        if (i + 1) % 25 == 0:
            json.dump(cache, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print(f'  [{i+1}/{len(todo)}] 保存 / 未解決{ng}')
    json.dump(cache, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    ok = sum(1 for v in cache.values() if v.get('city'))
    print(f'\n保存: {OUT}\n解決 {ok}/{len(cache)} 自治体')


if __name__ == '__main__':
    main()
