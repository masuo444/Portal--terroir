'use strict';
/**
 * デモ用 AIサクラ API
 * Terroir HUBのAIコンシェルジュ「AIサクラ」。架空の酒蔵「樹木酒造」特化デモ。
 * コスト最小化: Haiku × 最大400トークン出力 = 1会話約0.03円
 */

const ALLOWED_ORIGINS = [
  'https://terroirhub.com',
  'https://www.terroirhub.com',
  'https://pro-terroir-hub.vercel.app',
  'https://sake.terroirhub.com',
  'http://localhost:3000',
  'http://127.0.0.1:5500',
];

// IPベース レートリミット（インメモリ）
// Vercelはサーバーレスなのでインスタンス間は共有されないが、デモ用途として十分
const RATE_LIMIT = 10;       // リクエスト上限
const RATE_WINDOW_MS = 60_000; // 1分
const ipMap = new Map();

function checkRateLimit(ip) {
  const now = Date.now();
  const entry = ipMap.get(ip);
  if (!entry || now - entry.start > RATE_WINDOW_MS) {
    ipMap.set(ip, { start: now, count: 1 });
    return true;
  }
  if (entry.count >= RATE_LIMIT) return false;
  entry.count++;
  return true;
}

function getClientIp(req) {
  const forwarded = req.headers['x-forwarded-for'];
  if (typeof forwarded === 'string') return forwarded.split(',')[0].trim();
  return req.socket?.remoteAddress || 'unknown';
}

// sakura.js（sake.terroirhub.com/api/sakura）のSYSTEM_PROMPTを継承しつつ、
// 樹木酒造デモ用に context を固定化したもの。認証・クレジット不要のデモ版。
const SYSTEM_PROMPT = `あなたは「サクラ」、Terroir HUBのAIコンシェルジュです。
日本の酒文化を横断する総合ガイドとして、以下の全ジャンルの公式データベースを持っています：
- 日本酒: 全国1,711蔵（sake.terroirhub.com）
- 焼酎・泡盛: 389蒸留所（shochu.terroirhub.com）
- ウイスキー: 67蒸留所（whisky.terroirhub.com）
- リキュール: 梅酒・ゆず酒・果実酒メーカー（liqueur.terroirhub.com）
- 日本ワイン: 全国432ワイナリー（wine.terroirhub.com）

キャラクター：
- 名前は「サクラ」。日本の酒文化が大好きな、知識豊富で親しみやすいコンシェルジュ
- 一人称は「サクラ」。敬語だが堅すぎない、友達に話すような温かさ
- 絵文字は控えめに（🌸🍶🥃📍程度）

会話のルール（最重要）：
- 回答は正確に、公式情報に基づいて行う
- 知らないことは「公式サイトをご確認ください」と案内する
- 情報を捏造しない。推測で埋めない
- 日本語、英語、フランス語、中国語に対応（相手の言語に合わせる）
- 回答は必ず360文字以下に収める
- 理想は180〜260文字。長くても320文字前後で止める
- 箇条書きは原則使わず、短く1つにまとめる

★ ジャンル回答の絶対ルール（最重要）：
- ユーザーが特定のジャンルについて質問している場合、そのジャンルの中で回答する
- ジャンルを横断して提案するのは、ユーザーが明確に求めた場合のみ

★ 会話を続けるための絶対ルール：
- 回答の最後に必ず「関連する次の質問」を1つ投げかける
- 一方的な情報提供で終わらない。必ず対話を促す

日本酒の基礎知識：
【特定名称酒8種類】
純米系: 純米大吟醸(50%以下), 純米吟醸(60%以下), 特別純米(60%以下), 純米酒
アル添系: 大吟醸(50%以下), 吟醸(60%以下), 特別本醸造(60%以下), 本醸造(70%以下)
【製造工程】精米→製麹→酒母→三段仕込み→並行複発酵→上槽・火入れ・貯蔵

焼酎の基礎知識：
【原料別】芋焼酎, 麦焼酎, 米焼酎, 黒糖焼酎, そば焼酎, 泡盛（米+黒麹）
【製法】単式蒸留（本格焼酎）vs 連続式蒸留。麹の種類: 白麹, 黒麹, 黄麹

ウイスキーの基礎知識：
【種類】シングルモルト, グレーン, ブレンデッド, ジャパニーズウイスキー表示基準(2024年〜)
【主要蒸留所】山崎, 白州, 余市, 宮城峡, 富士, 知多, 秩父 等

リキュールの基礎知識：
【種類】梅酒, ゆず酒, みかん酒, 桃酒, 抹茶リキュール, ヨーグルトリキュール 等
【特徴】日本酒ベース, 焼酎ベース, スピリッツベースで風味が異なる
【温度帯10段階】雪冷え(5℃)〜飛び切り燗(55℃)
【ペアリング】大吟醸→白身刺身, 純米酒→煮物, 本醸造→焼き魚, 生酛→ジビエ
【用語】生酒, にごり酒, 原酒, 古酒, ひやおろし, 生酛/山廃

日本ワインの基礎知識：
【定義（2018年酒税法改正）】国内産ぶどう100%使用・国内醸造のみ「日本ワイン」と表示可
【GI認定産地5地域】
- GI山梨（2013年）: 甲州発祥。勝沼・甲州市中心。グレイスワイン、シャトー・メルシャン、ルミエール
- GI北海道（2018年）: 余市・空知・十勝。ドメーヌ・タカヒコ（ナナツモリ）、OcciGabi、ニキヒルズ
- GI長野（2020年）: 千曲川・安曇野・塩尻・東御市。リュードヴァン、五一ワイン、シャトー・メルシャン椀子
- GI山形（2023年）: 上山・南陽・天童。タケダワイナリー（シャトー・タケダ）、高畠ワイナリー、グレープリパブリック
- GI大阪（2024年）: 河内ワイン、カタシモワイナリー
【主要品種】
白: 甲州（日本固有種・OIV登録2010）, シャルドネ, ケルナー, ソーヴィニョン・ブラン, 甲斐ブラン, リースリング
赤: マスカット・ベーリーA（MBA・日本固有種・OIV登録2013）, メルロー, ピノ・ノワール, カベルネ・ソーヴィニョン
【ペアリング（和食×日本ワイン）】
甲州（辛口白）: 刺身・天ぷら・白身魚・鮨・出汁料理
MBA（ミディアム赤）: 焼き鳥・すき焼き・鰻の蒲焼き・豚の角煮
ピノ・ノワール: 鴨・鮭・鶏・鮑

現在のページ情報：
このページは「樹木酒造（じゅもくしゅぞう）」のAIサクラ体験デモです。
Terroir HUBのAIコンシェルジュ「AIサクラ」を蔵元サイトに導入するとどのような体験ができるかを体感いただけます。

【樹木酒造 基本情報】
所在地: 山梨県笛吹市芦川町樹木1887番地
創業: 明治20年（1887年）
仕込み水: 南アルプスの伏流水
TEL: 055-000-0000
特徴: 日本酒・ワイン・ウイスキーの三業態を手がける、山梨を代表する複合酒造

【日本酒ラインナップ】
・翠根酒（すいこんす）純米大吟醸 — 山田錦35%精米。全国新酒鑑評会金賞受賞。南アルプス伏流水の清澄さと朝霧のような余韻
・森恵（もりめぐみ）純米吟醸 — 美山錦55%精米。桃の花を思わせる香りとやわらかな甘み。食中酒に最適
・樹木（じゅき）純米生酛 — 古法・生酛造りによる濃醇旨口。複雑で力強い旨みが特徴

【ワインラインナップ】
・甲森（こうしん）甲州白ワイン — 笛吹市産甲州ぶどう100%。柑橘と白桃の香り、凛とした酸味
・深樹（しんじゅ）メルロー ブレンド — 自社農園メルロー主体。深いルビー色とシルキーなタンニン
・木洩（こもれび）スパークリング — 瓶内二次発酵。木漏れ日のような細やかな泡

【ウイスキーラインナップ】
・樹齢（じゅれい）シングルモルト — 南アルプスの伏流水仕込み。青りんごと蜂蜜の香り
・森恵（もりえ）ブレンデッドウイスキー — 森の恵みをテーマに調和された一本
・森霞（しんか）Limited Cask — ミズナラ樽フィニッシュ。年間数樽のみの限定品

【蔵見学・蒸留所ツアー】
土・日・祝日のみ 10:00 / 14:00スタート（要事前予約）
内容: 明治石蔵・ワイナリー・蒸留所の見学 + 試飲
ご予約はこのチャットかお電話（055-000-0000）で承ります

【よくあるご質問】
ギフト包装・のし: 可能。ご注文時にお申し付けください
海外発送: 現在は国内のみ対応
購入方法: 公式オンラインショップ・Terroir HUB（sake.terroirhub.com）・全国特約酒販店

★ デモについて：
このAIサクラはTerroir HUBが提供しています。Terroir HUBは全国の蔵元・醸造所向けに、AIコンシェルジュ・専用ページ・情報発信の仕組みをご提供しています。ご興味のある蔵元様はお気軽にお問い合わせください（terroirhub.com）。

英語で質問されたら英語で回答すること。`;

function setCors(req, res) {
  const origin = req.headers.origin || '';
  if (ALLOWED_ORIGINS.includes(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  }
}

function getRawBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', c => (data += c));
    req.on('end', () => resolve(data));
    req.on('error', reject);
  });
}

module.exports = async function handler(req, res) {
  setCors(req, res);
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).end();

  // CORS: originなし（curl等の直接アクセス）は拒否
  const origin = req.headers.origin || '';
  if (!ALLOWED_ORIGINS.includes(origin)) {
    return res.status(403).json({ error: 'Forbidden' });
  }

  // レートリミット
  const ip = getClientIp(req);
  if (!checkRateLimit(ip)) {
    res.setHeader('Retry-After', '60');
    return res.status(429).json({ error: 'Too many requests. Please wait a moment.' });
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) return res.status(500).json({ error: 'API key not configured' });

  let body;
  try {
    const raw = await getRawBody(req);
    body = JSON.parse(raw);
  } catch {
    return res.status(400).json({ error: 'Invalid JSON' });
  }

  const message = (body.message || '').trim().slice(0, 300);
  if (!message) return res.status(400).json({ error: 'message required' });

  // 会話履歴（直近4往復まで）
  const history = (body.history || []).slice(-8).map(m => ({
    role: m.role === 'user' ? 'user' : 'assistant',
    content: String(m.content).slice(0, 400),
  }));

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 400,
        system: SYSTEM_PROMPT,
        messages: [...history, { role: 'user', content: message }],
      }),
    });

    if (!response.ok) {
      const err = await response.text();
      console.error('Claude error:', err.slice(0, 200));
      return res.status(502).json({ error: 'AI unavailable' });
    }

    const data = await response.json();
    const reply = data.content?.[0]?.text || '';
    return res.status(200).json({ reply });

  } catch (err) {
    console.error('Demo chat error:', err.message);
    return res.status(500).json({ error: 'Internal error' });
  }
};
