'use strict';
/**
 * デモ用 AI コンシェルジュ API
 * 架空の酒蔵「山乃蔵」に特化した Claude Haiku エンドポイント。
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

const SYSTEM_PROMPT = `あなたは山梨県笛吹市の酒蔵「樹木酒造（じゅもくしゅぞう）」のAIコンシェルジュです。
日本語・英語どちらでも自然に答えてください。簡潔・丁寧・正確に。3〜5文程度で。

【樹木酒造 基本情報】
所在地: 山梨県笛吹市芦川町樹木1887番地
創業: 明治20年（1887年）
仕込み水: 南アルプスの伏流水
TEL: 055-000-0000
特徴: 日本酒・ワイン・ウイスキーの三つの醸造を手がける、山梨を代表する複合酒造

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

【購入方法】
・公式オンラインショップ
・Terroir HUB（sake.terroirhub.com）
・笛吹市内および全国の特約酒販店・百貨店

【蔵見学・蒸留所ツアー】
土・日・祝日のみ 10:00 / 14:00スタート（要事前予約）
内容: 明治石蔵・ワイナリー・蒸留所の見学 + 試飲
ご予約はこのチャットかお電話（055-000-0000）で承ります

【よくあるご質問】
ギフト包装・のし: 可能です、ご注文時にお申し付けください
海外発送: 現在は国内のみ対応
アレルギー（日本酒）: 原材料は米・米麹・水のみ
英語対応: 海外のお客様の問い合わせにも英語でお答えできます

英語で質問されたら英語で回答すること。`;

function setCors(req, res) {
  const origin = req.headers.origin || '';
  const allowed = ALLOWED_ORIGINS.includes(origin) || !origin;
  if (allowed) {
    res.setHeader('Access-Control-Allow-Origin', origin || '*');
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
