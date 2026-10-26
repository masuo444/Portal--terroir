// 7サイトの middleware.ts から、AI・検索エンジンのクローラーの来訪を受け取って Supabase に記録する（2026-10-26）。
// 書き込みは BOT_LOG_TOKEN を知っている middleware だけ。読み出しは日報（サービスキー）だけ。
const SUPABASE_URL = process.env.SUPABASE_URL || 'https://hhwavxavuqqfiehrogwv.supabase.co';
const clip = (s, n) => String(s || '').slice(0, n);

// 日報用の集計（GET ?days=28）。ついでに120日より古い記録を消す
async function summary(req, res, key) {
  const days = Math.min(Number(req.query.days) || 28, 120);
  const since = new Date(Date.now() - days * 864e5).toISOString();
  const h = { apikey: key, Authorization: `Bearer ${key}` };
  const old = new Date(Date.now() - 120 * 864e5).toISOString();
  fetch(`${SUPABASE_URL}/rest/v1/analytics?event=eq.bot_crawl&timestamp=lt.${old}`, { method: 'DELETE', headers: h }).catch(() => {});
  const byBot = {}, byHostKind = {}, aiPages = {}, daily = {};
  for (let from = 0; from < 200000; from += 1000) {
    const r = await fetch(`${SUPABASE_URL}/rest/v1/analytics?event=eq.bot_crawl&timestamp=gte.${since}&select=timestamp,page,properties&order=id.asc`,
      { headers: { ...h, Range: `${from}-${from + 999}` } });
    if (!r.ok) return res.status(502).end();
    const rows = await r.json();
    for (const x of rows) {
      const p = x.properties || {}, w = Number(p.weight) || 1;
      const bk = `${p.kind}|${p.bot}`; byBot[bk] = (byBot[bk] || 0) + w;
      const hk = `${p.host}|${p.kind}`; byHostKind[hk] = (byHostKind[hk] || 0) + w;
      const d = String(x.timestamp).slice(0, 10), dk = `${d}|${String(p.kind).startsWith('ai') ? 'ai' : 'search'}`; daily[dk] = (daily[dk] || 0) + w;
      if (String(p.kind).startsWith('ai')) { const pk = `${p.host}${x.page}|${p.kind}`; aiPages[pk] = (aiPages[pk] || 0) + w; }
    }
    if (rows.length < 1000) break;
  }
  const top = (o, n) => Object.entries(o).sort((a, b) => b[1] - a[1]).slice(0, n).map(([k, v]) => [...k.split('|'), v]);
  return res.status(200).json({ days, by_bot: top(byBot, 40), by_host_kind: top(byHostKind, 60), ai_pages: top(aiPages, 40),
    daily: Object.entries(daily).sort().map(([k, v]) => [...k.split('|'), v]) });
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  const token = process.env.BOT_LOG_TOKEN;
  if (!token || req.headers['x-bot-token'] !== token) return res.status(401).end();
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!key) return res.status(500).end();
  if (req.method === 'GET') return summary(req, res, key);
  if (req.method !== 'POST') return res.status(405).end();

  const b = req.body || {};
  if (!b.bot || !b.host || !/(^|\.)terroirhub\.com$/.test(String(b.host))) return res.status(400).end();
  const row = {
    event: 'bot_crawl',
    page: clip(b.path, 300),
    country: clip(b.country, 8),
    properties: { host: clip(b.host, 60), bot: clip(b.bot, 40), kind: clip(b.kind, 20), weight: Number(b.weight) || 1, ua: clip(b.ua, 200) },
  };
  try {
    const r = await fetch(`${SUPABASE_URL}/rest/v1/analytics`, {
      method: 'POST',
      headers: { apikey: key, Authorization: `Bearer ${key}`, 'Content-Type': 'application/json', Prefer: 'return=minimal' },
      body: JSON.stringify(row),
    });
    return res.status(r.ok ? 204 : 502).end();
  } catch (e) {
    return res.status(502).end();
  }
};
