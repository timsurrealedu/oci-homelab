const $ = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const fmtDate = (ms) => new Date(ms).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
const fmtNum = (v, d = 2) => v == null ? '—' : v.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
const signed = (v, suffix = '') => v == null ? '—' : (v > 0 ? '+' : '') + fmtNum(v) + suffix;
const dir = (v) => v > 0 ? 'up' : v < 0 ? 'down' : '';
const svgEl = (name, attrs, text) => {
  const e = document.createElementNS(NS, name);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (text != null) e.textContent = text;
  return e;
};
const cell = (row, text, cls) => { const td = row.insertCell(); td.textContent = text; if (cls) td.className = cls; };

function tiles(s) {
  const c = s.stake_currency || '';
  const items = [
    ['return', signed(s.return_pct, '%')],
    [`wallet ${c}`, fmtNum(s.balance)],
    [`started ${c}`, fmtNum(s.starting_capital, 0)],
    ['closed trades', s.closed_trades ?? '—'],
    ['win rate', s.winrate_pct == null ? '—' : s.winrate_pct + '%'],
    ['profit factor', fmtNum(s.profit_factor)],
    ['max drawdown', s.max_drawdown_pct == null ? '—' : '−' + s.max_drawdown_pct + '%'],
  ];
  $('tiles').replaceChildren(...items.map(([k, v]) => {
    const d = document.createElement('div'); d.className = 'tile';
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd'); dd.textContent = v;
    d.append(dt, dd); return d;
  }));
}

let firstDraw = true;
function chart(points, start, currency) {
  const svg = $('chart'), W = 900, H = 300, L = 56, R = 64, T = 14, B = 30;
  svg.querySelectorAll(':scope > :not(desc)').forEach((n) => n.remove());
  if (points.length < 2) { svg.append(svgEl('text', { class: 'axis', x: W / 2, y: H / 2, 'text-anchor': 'middle' }, 'not enough trades yet')); return; }
  const xs = points.map((p) => p[0]), ys = points.map((p) => p[1]).concat([start]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  let y0 = Math.min(...ys), y1 = Math.max(...ys); const pad = (y1 - y0) * 0.08 || 10; y0 -= pad; y1 += pad;
  const X = (v) => L + (v - x0) / (x1 - x0) * (W - L - R), Y = (v) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);

  const step = Math.pow(10, Math.floor(Math.log10((y1 - y0) / 4)));
  const nice = [1, 2, 5, 10].map((m) => m * step).find((s) => (y1 - y0) / s <= 5);
  for (let v = Math.ceil(y0 / nice) * nice; v <= y1; v += nice) {
    svg.append(svgEl('line', { class: 'grid', x1: L, x2: W - R, y1: Y(v), y2: Y(v) }));
    svg.append(svgEl('text', { class: 'axis', x: L - 8, y: Y(v) + 4, 'text-anchor': 'end' }, fmtNum(v, 0)));
  }
  const d = new Date(x0); d.setDate(1); d.setHours(0, 0, 0, 0);
  for (d.setMonth(d.getMonth() + 1); d.getTime() <= x1; d.setMonth(d.getMonth() + 1)) {
    svg.append(svgEl('text', { class: 'axis', x: X(d.getTime()), y: H - 8, 'text-anchor': 'middle' }, d.toLocaleDateString(undefined, { month: 'short' })));
  }
  svg.append(svgEl('line', { class: 'ref', x1: L, x2: W - R, y1: Y(start), y2: Y(start) }));
  svg.append(svgEl('text', { class: 'axis', x: W - R + 6, y: Y(start) + 4 }, 'start'));

  const path = svgEl('path', { class: 'series', d: points.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join('') });
  svg.append(path);
  if (firstDraw) { path.style.setProperty('--len', Math.ceil(path.getTotalLength())); path.classList.add('draw'); }
  const last = points[points.length - 1];
  svg.append(svgEl('circle', { class: 'dot end', cx: X(last[0]), cy: Y(last[1]), r: 4.5 }));
  svg.append(svgEl('text', { class: 'end-label', x: X(last[0]) + 9, y: Y(last[1]) + 4 }, fmtNum(last[1], 0)));
  firstDraw = false;

  // Crosshair + tooltip snapped to the nearest closed trade; keyboard steps with the arrow keys.
  const hair = svgEl('line', { class: 'hair', y1: T, y2: H - B, visibility: 'hidden' });
  const dot = svgEl('circle', { class: 'dot', r: 4.5, visibility: 'hidden' });
  const hit = svgEl('rect', { x: L, y: T, width: W - L - R, height: H - T - B, fill: 'transparent', tabindex: 0, 'aria-label': 'Equity chart. Use the arrow keys to step through trades.' });
  svg.append(hair, dot, hit);
  const tip = $('tip'); let idx = points.length - 1;
  const show = (i) => {
    idx = Math.max(0, Math.min(points.length - 1, i)); const [t, v] = points[idx];
    hair.setAttribute('x1', X(t)); hair.setAttribute('x2', X(t));
    dot.setAttribute('cx', X(t)); dot.setAttribute('cy', Y(v));
    hair.setAttribute('visibility', 'visible'); dot.setAttribute('visibility', 'visible');
    const box = svg.getBoundingClientRect(), k = box.width / W;
    const b = document.createElement('b'); b.textContent = `${fmtNum(v)} ${currency}`;
    tip.replaceChildren(document.createTextNode(fmtDate(t) + '  '), b);
    tip.style.left = Math.min(box.width - 90, Math.max(90, X(t) * k)) + 'px';
    tip.style.top = Y(v) * k + 'px';
    tip.hidden = false;
  };
  const hide = () => { hair.setAttribute('visibility', 'hidden'); dot.setAttribute('visibility', 'hidden'); tip.hidden = true; };
  hit.addEventListener('pointermove', (e) => {
    const box = svg.getBoundingClientRect(), t = x0 + ((e.clientX - box.left) / box.width * W - L) / (W - L - R) * (x1 - x0);
    let best = 0; points.forEach((p, i) => { if (Math.abs(p[0] - t) < Math.abs(points[best][0] - t)) best = i; }); show(best);
  });
  hit.addEventListener('pointerleave', hide);
  hit.addEventListener('blur', hide);
  hit.addEventListener('focus', () => show(idx));
  hit.addEventListener('keydown', (e) => { if (e.key === 'ArrowLeft') show(idx - 1); else if (e.key === 'ArrowRight') show(idx + 1); else return; e.preventDefault(); });

  $('chart-desc').textContent = `Equity from ${fmtNum(start)} to ${fmtNum(last[1])} ${currency} over ${points.length - 1} closed trades.`;
  $('eqtable').tBodies[0].replaceChildren(...points.map(([t, v]) => { const r = document.createElement('tr'); cell(r, fmtDate(t)); cell(r, fmtNum(v), 'n'); return r; }));
}

function table(id, rows, cols, empty) {
  const body = $(id).tBodies[0]; body.replaceChildren();
  if (!rows.length) { const r = body.insertRow(); const td = r.insertCell(); td.textContent = empty; td.className = 'muted'; td.colSpan = cols; return; }
  rows.forEach((fill) => fill(body.insertRow()));
}

async function load() {
  try {
    const r = await fetch('/api/summary'); const d = await r.json();
    if (!r.ok) throw new Error(d.error || r.statusText);
    const s = d.summary, b = d.bot;
    $('sub').textContent = `${b.strategy} on ${b.exchange} (${b.trading_mode}, ${b.timeframe} candles), ${b.state}. ` +
      (s.first_trade ? `Trading since ${fmtDate(s.first_trade)}; last trade ${fmtDate(s.latest_trade)}.` : 'No trades yet.');
    tiles(s);
    chart(d.equity, s.starting_capital, s.stake_currency);
    table('open', d.open.map((t) => (r) => { cell(r, t.pair); cell(r, fmtDate(t.opened)); cell(r, signed(t.profit_pct, '%'), 'n ' + dir(t.profit_pct)); }), 3, 'No open positions right now.');
    table('recent', d.recent.map((t) => (r) => {
      cell(r, t.pair); cell(r, fmtDate(t.opened)); cell(r, fmtDate(t.closed));
      cell(r, signed(t.profit_pct, '%'), 'n ' + dir(t.profit_pct)); cell(r, signed(t.profit_abs), 'n'); cell(r, t.exit || '—');
    }), 6, 'No closed trades yet.');
    $('foot').textContent = `Updated ${new Date(d.generated_at).toLocaleTimeString()}. Data refreshes every minute through a read-only backend; the bot's own API is never exposed. Part of oci-homelab, a $0 Oracle Cloud platform.`;
  } catch (e) {
    $('sub').textContent = 'Could not load the bot: ' + e.message;
    $('sub').classList.add('err-text');
  }
}
load();
setInterval(load, 60000);
