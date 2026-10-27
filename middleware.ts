// Terroir HUB — AI・検索エンジンのクローラー来訪の記録（全サイト共通、2026-10-26）
// 原本: テロワールハブ　総合/automation/botlog/middleware.ts（各リポジトリのルートにコピーする）
// 人の訪問では何もしない。クローラーのときだけ、応答を返した後に www の /api/bot-log へ1件送る。
// 応答は一切変えない（何も return しない＝そのまま静的ページを返す）。失敗しても握りつぶす。
export const config = {
  runtime: 'nodejs',  // 焼酎プロジェクトは指定しないと edge で動き、記録が送られなかった
  matcher: ['/((?!.*\\.(?:js|css|png|jpe?g|webp|gif|svg|ico|woff2?|json|map|mp4|webm|pdf|avif)$).*)'],
};

// [UAに含まれる文字列, 名前, 種類]。種類: ai_user=AIが利用者の質問に答えるため今読んだ / ai_search=AI検索の索引 / ai_train=学習用 / search=検索エンジン
const BOTS: [RegExp, string, string][] = [
  [/ChatGPT-User/i, 'ChatGPT-User', 'ai_user'],
  [/Claude-User/i, 'Claude-User', 'ai_user'],
  [/Perplexity-User/i, 'Perplexity-User', 'ai_user'],
  [/MistralAI-User/i, 'MistralAI-User', 'ai_user'],
  [/DuckAssistBot/i, 'DuckAssistBot', 'ai_user'],
  [/OAI-SearchBot/i, 'OAI-SearchBot', 'ai_search'],
  [/Claude-SearchBot/i, 'Claude-SearchBot', 'ai_search'],
  [/PerplexityBot/i, 'PerplexityBot', 'ai_search'],
  [/GPTBot/i, 'GPTBot', 'ai_train'],
  [/ClaudeBot|anthropic-ai/i, 'ClaudeBot', 'ai_train'],
  [/CCBot/i, 'CCBot', 'ai_train'],
  [/Bytespider/i, 'Bytespider', 'ai_train'],
  [/meta-externalagent|meta-externalfetcher/i, 'Meta-AI', 'ai_train'],
  [/Amazonbot/i, 'Amazonbot', 'ai_train'],
  [/cohere-ai|Diffbot|YouBot|Timpibot|ImagesiftBot/i, 'other-ai', 'ai_train'],
  [/bingbot/i, 'Bingbot', 'search'],
  [/Googlebot|Google-InspectionTool/i, 'Googlebot', 'search'],
  [/Applebot/i, 'Applebot', 'search'],
  [/YandexBot/i, 'YandexBot', 'search'],
  [/Baiduspider/i, 'Baiduspider', 'search'],
  [/DuckDuckBot/i, 'DuckDuckBot', 'search'],
];
// 検索エンジンとAIの学習用は件数が多いので10件に1件だけ送る（集計時に weight=10 を掛ける）。Supabase無料枠(500MB)を守るため
const SAMPLE = { search: 10, ai_train: 10 } as Record<string, number>;

export default async function middleware(request: Request, context: { waitUntil?: (p: Promise<unknown>) => void }) {
  try {
    const ua = request.headers.get('user-agent') || '';
    if (!/bot|crawl|spider|-User|agent/i.test(ua)) return;
    const hit = BOTS.find(([re]) => re.test(ua));
    if (!hit) return;
    const rate = SAMPLE[hit[2]] || 1;
    if (rate > 1 && Math.random() * rate >= 1) return;
    const token = process.env.BOT_LOG_TOKEN;
    if (!token) return;
    const url = new URL(request.url);
    const body = JSON.stringify({
      host: url.hostname, path: url.pathname, bot: hit[1], kind: hit[2], weight: rate,
      country: request.headers.get('x-vercel-ip-country') || '', ua: ua.slice(0, 200),
    });
    const send = fetch('https://www.terroirhub.com/api/bot-log', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'x-bot-token': token }, body,
      signal: AbortSignal.timeout(1500),
    }).catch(() => {});
    // waitUntil が無い設定のプロジェクト（焼酎）では、クローラーのときだけ送信を待つ（最大1.5秒）
    if (context && context.waitUntil) context.waitUntil(send);
    else await send;
  } catch (e) {}
}
