/*!
 * Terroir HUB — GA4 計測（全サイト共通）
 * 原本: テロワールハブ　総合/automation/analytics/thub-analytics.js
 * 各リポジトリのルートに /thub-analytics.js としてコピーされる。直接編集せず原本を直して
 * automation/analytics/inject_analytics.py を流すこと。
 *
 * GA4のカスタムディメンション登録なしでレポートできるよう、標準パラメータだけを使う:
 *   content_group = ページ種別 / link_url, link_domain = 送客先 / percent_scrolled = 読了率
 */
(function () {
  'use strict';
  if (window.__thubAnalytics) return;
  window.__thubAnalytics = true;

  // host → [読み込むタグID, 送信先の測定ID]
  // 焼酎(G-P1JQ4K6PT7)は日本酒のGoogleタグに送信先として統合されているため、単独の gtag/js が404になる。
  var HOSTS = {
    'sake.terroirhub.com': ['G-LLQJRCXB4N', 'G-LLQJRCXB4N'],
    'shochu.terroirhub.com': ['G-LLQJRCXB4N', 'G-P1JQ4K6PT7'],
    'wine.terroirhub.com': ['G-9JWN7TVZ6N', 'G-9JWN7TVZ6N'],
    'whisky.terroirhub.com': ['G-1RF78SC8FH', 'G-1RF78SC8FH'],
    'liqueur.terroirhub.com': ['G-RXSS3P04XJ', 'G-RXSS3P04XJ'],
    'craft.terroirhub.com': ['G-NW4GE31MHC', 'G-NW4GE31MHC'],
    'www.terroirhub.com': ['G-NG35V7K1JH', 'G-NG35V7K1JH'],
    'terroirhub.com': ['G-NG35V7K1JH', 'G-NG35V7K1JH']
  };
  var ids = HOSTS[location.hostname];
  if (!ids) return; // プレビュー環境・localhost は計測しない

  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function () { dataLayer.push(arguments); };

  // ── ページ種別 ──────────────────────────────────────────
  var PREFS = 'hokkaido aomori iwate miyagi akita yamagata fukushima ibaraki tochigi gunma saitama chiba tokyo kanagawa niigata toyama ishikawa fukui yamanashi nagano gifu shizuoka aichi mie shiga kyoto osaka hyogo nara wakayama tottori shimane okayama hiroshima yamaguchi tokushima kagawa ehime kochi fukuoka saga nagasaki kumamoto oita miyazaki kagoshima okinawa'.split(' ');
  var path = location.pathname.replace(/\/index\.html$/, '/');
  var segs = path.split('/').filter(Boolean);
  var lang = segs.indexOf('en') >= 0 || /^\/en(\/|$)/.test(path) ? 'en' : 'ja';
  var rest = segs.filter(function (s) { return s !== 'en'; });
  var GENRES = ['sake', 'shochu', 'wine', 'whisky', 'liqueur', 'craft'];
  if (rest.length && GENRES.indexOf(rest[0]) >= 0) rest = rest.slice(1);

  var pageType = 'other';
  if (!rest.length) pageType = 'top';
  else if (PREFS.indexOf(rest[0]) >= 0) pageType = rest.length >= 2 && /\.html$/.test(rest[1]) ? 'producer' : 'pref_list';
  else {
    var map = { guide: 'guide', blog: 'blog', visit: 'visit', furusato: 'furusato', terroir: 'terroir',
      area: 'area', travel: 'travel', textbook: 'guide', ranking: 'ranking', search: 'search',
      business: 'business', 'for-breweries': 'business', pricing: 'business', contact: 'contact', login: 'account', mypage: 'account' };
    var k = rest[0].replace(/\.html$/, '');
    pageType = map[k] || 'other';
  }
  var contentGroup = pageType + (lang === 'en' ? '_en' : '');

  var s = document.createElement('script');
  s.async = true;
  s.src = 'https://www.googletagmanager.com/gtag/js?id=' + ids[0];
  document.head.appendChild(s);
  gtag('js', new Date());
  gtag('config', ids[1], { content_group: contentGroup });

  function ev(name, params) {
    try {
      params = params || {};
      params.send_to = ids[1];
      params.content_group = contentGroup;
      gtag('event', name, params);
    } catch (e) {}
  }

  // ── 送客クリック ────────────────────────────────────────
  var PARTNERS = [
    [/(^|\.)rakuten\.co\.jp$|(^|\.)rakuten\.ne\.jp$/, 'rakuten'],
    [/valuecommerce\.com$|(^|\.)vc\.jp/, 'valuecommerce'],
    [/(^|\.)klook\.com$/, 'klook'],
    [/(^|\.)amazon\.co\.jp$|(^|\.)amzn\.(to|asia)$/, 'amazon'],
    [/(^|\.)a8\.net$/, 'a8'],
    [/(^|\.)moshimo\.com$/, 'moshimo'],
    [/furusato-tax\.jp$|furunavi\.jp$|satofull\.jp$|furusato\.|ふるさと/, 'furusato'],
    [/(^|\.)byfood\.com$/, 'byfood'],
    [/(^|\.)expedia\.co\.jp$|(^|\.)expedia\.com$/, 'expedia'],
    [/(^|\.)his-j\.com$/, 'his'],
    [/travel\.yahoo\.co\.jp$/, 'yahoo_travel']
  ];
  function partnerOf(host, href) {
    for (var i = 0; i < PARTNERS.length; i++) if (PARTNERS[i][0].test(host)) return PARTNERS[i][1];
    // バリューコマースのMyLink経由（例: Klook/Expediaの遷移URLがvcのクエリに埋め込まれる）
    if (/vc_url=|vc_pid=/.test(href)) return 'valuecommerce';
    return '';
  }
  function placementOf(el) {
    var n = el;
    for (var i = 0; n && i < 8; i++, n = n.parentElement) {
      if (n.id) return n.id;
      if (n.tagName === 'SECTION' || n.tagName === 'ASIDE' || n.tagName === 'NAV' || n.tagName === 'FOOTER' || n.tagName === 'HEADER') {
        return (n.className && String(n.className).split(' ')[0]) || n.tagName.toLowerCase();
      }
    }
    return '';
  }

  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a) return;
    var href = a.getAttribute('href') || '';
    if (/^mailto:/i.test(href)) return ev('contact_click', { method: 'mail', link_url: href.split('?')[0] });
    if (/^tel:/i.test(href)) return ev('contact_click', { method: 'tel', link_url: href });
    var u;
    try { u = new URL(a.href, location.href); } catch (err) { return; }
    var host = u.hostname;
    var common = { link_url: u.href.slice(0, 300), link_domain: host, link_text: (a.textContent || '').trim().slice(0, 80), placement: placementOf(a) };

    var partner = partnerOf(host, u.href);
    if (partner) { common.partner = partner; return ev('affiliate_click', common); }

    if (/(^|\.)terroirhub\.com$/.test(host)) {
      if (host !== location.hostname) ev('cross_site_click', common);
      if (/\/(contact|business|for-breweries|pricing|lp|listing-update)/.test(u.pathname)) ev('contact_click', { method: /listing-update/.test(u.pathname) ? 'listing_update' : 'business', link_url: common.link_url, placement: common.placement });
      return;
    }
    // 外部サイト：生産者ページからの外部リンクは「公式サイト等への送客」
    ev(pageType === 'producer' ? 'producer_site_click' : 'outbound_click', common);
  }, true);

  document.addEventListener('submit', function (e) {
    var f = e.target;
    ev('form_submit', { form_id: (f && (f.id || f.getAttribute('name') || f.getAttribute('action'))) || '' });
  }, true);

  // ── AIサクラ（/api/sakura への送信を1メッセージとして数える）────
  if (window.fetch) {
    var _fetch = window.fetch;
    window.fetch = function (input) {
      try {
        var url = typeof input === 'string' ? input : (input && input.url) || '';
        if (/\/api\/sakura/.test(url)) ev('sakura_message', {});
      } catch (e) {}
      return _fetch.apply(this, arguments);
    };
  }

  // ── 読了率（25/50/75/100%）と30秒以上の熟読 ─────────────────
  var marks = [25, 50, 75, 100], sent = {};
  function onScroll() {
    var h = document.documentElement.scrollHeight - window.innerHeight;
    if (h <= 0) return;
    var p = Math.round(window.scrollY / h * 100);
    for (var i = 0; i < marks.length; i++) {
      if (p >= marks[i] && !sent[marks[i]]) { sent[marks[i]] = 1; ev('scroll_depth', { percent_scrolled: marks[i] }); }
    }
  }
  window.addEventListener('scroll', onScroll, { passive: true });

  var visibleMs = 0, last = Date.now(), readSent = false;
  setInterval(function () {
    var now = Date.now();
    if (document.visibilityState === 'visible') visibleMs += now - last;
    last = now;
    if (!readSent && visibleMs >= 30000) { readSent = true; ev('read_30s', {}); }
  }, 5000);
})();
