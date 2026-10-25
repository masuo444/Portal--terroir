// デモページのAIチャットは 2026-10-25 に停止した（AIの利用料をかけない方針。回数制限も回避できた）。元の実装は git の履歴にある。
module.exports = (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  res.status(410).json({ error: 'This demo chat has ended.' });
};
