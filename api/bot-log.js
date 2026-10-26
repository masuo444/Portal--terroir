// 7サイトの middleware.ts から、AI・検索エンジンのクローラーの来訪を受け取って Supabase に記録する（2026-10-26）。
// 書き込みは BOT_LOG_TOKEN を知っている middleware だけ。読み出しは日報（サービスキー）だけ。
const SUPABASE_URL = process.env.SUPABASE_URL || 'https://hhwavxavuqqfiehrogwv.supabase.co';
const clip = (s, n) => String(s || '').slice(0, n);

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).end();
  const token = process.env.BOT_LOG_TOKEN;
  if (!token || req.headers['x-bot-token'] !== token) return res.status(401).end();
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!key) return res.status(500).end();

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
