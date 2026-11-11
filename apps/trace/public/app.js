const $ = (id) => document.getElementById(id);
const ms = (v) => v == null ? '—' : (v < 1 ? '<1' : v < 10 ? v.toFixed(1) : Math.round(v)) + ' ms';
const mk = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

const ENTRY = {
  tailscale: ['your device → edge, over Tailscale',
    "An encrypted WireGuard tunnel straight to the edge server's tailnet address. No public port is involved: Tailscale Serve terminates HTTPS on the server and hands the request to Caddy on 127.0.0.1."],
  internet: ['your device → edge, over the internet',
    "Across the internet to the edge's public IP, through Oracle's Internet Gateway, the VCN security list and the nsg-edge network security group, then the host firewall. Caddy terminates TLS."],
};

function hop(title, timing, text) {
  const li = mk('li', 'hop'), h = mk('h3', null, title);
  if (timing) { const s = mk('span', 'ms'); s.append(mk('b', null, timing[0]), document.createTextNode(timing[1] || '')); h.append(s); }
  li.append(h, mk('p', null, text));
  return li;
}

function renderPath(d, netMs) {
  const [title, text] = ENTRY[d.entry] || ENTRY.internet;
  const hops = [
    hop('you', null, d.client ? `Your request leaves from ${d.client}.` : 'Your request leaves your browser.'),
    hop(title, [ms(netMs), ' round trip'], text),
    hop('caddy → trace app', [ms(d.caddy_to_app_ms), ''], "Caddy, the single HTTP entry point, forwards the request over Docker's bridge network to this app's container. Admin interfaces are never on this path."),
    hop('trace app', [ms(d.app_ms), ' to answer'], 'A small Python service in a locked-down container (read-only, no extra privileges) builds the response and reports its own timing in a Server-Timing header.'),
  ];
  hops.forEach((h, i) => h.style.setProperty('--i', i));
  const packet = mk('span', 'packet');
  packet.setAttribute('aria-hidden', 'true');
  $('path').replaceChildren(...hops, packet);
  return { packet, hops, segs: [netMs, d.caddy_to_app_ms, d.app_ms] };
}

function animate({ packet, hops, segs }) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches || !packet.animate) return;
  const ys = hops.map((h) => h.offsetTop + 6);
  // Each segment's duration grows with its measured latency, on a log scale so 1 ms and 300 ms both read.
  const durs = segs.map((v) => 380 + 280 * Math.log10(1 + (v || 0)));
  const total = durs.reduce((a, b) => a + b, 0);
  const frames = [{ transform: `translateY(${ys[0]}px) scale(.4)`, opacity: 0, offset: 0 }, { transform: `translateY(${ys[0]}px)`, opacity: 1, offset: .03 }];
  let acc = 0;
  durs.forEach((dur, i) => { acc += dur; frames.push({ transform: `translateY(${ys[i + 1]}px)`, opacity: 1, offset: Math.min(.97, acc / total) }); });
  frames.push({ transform: `translateY(${ys[ys.length - 1]}px) scale(1.8)`, opacity: 0, offset: 1 });
  packet.animate(frames, { duration: total + 400, easing: 'ease-in-out' });
}

function renderProbes(probes, at) {
  const max = Math.max(...probes.map((p) => p.ms || 0), 1);
  $('probe-note').textContent = `TCP handshake time from the server to fixed targets, measured ${new Date(at).toLocaleTimeString()}.`;
  $('bars').replaceChildren(...probes.map((p) => {
    const row = mk('div', 'bar-row'), top = mk('div', 'top');
    top.append(mk('span', null, p.label), mk('span', 'val', p.ok ? ms(p.ms) : 'no answer'));
    const track = mk('div', 'track'), fill = mk('div', 'fill' + (p.ok ? '' : ' none'));
    track.append(fill);
    requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.width = (p.ok ? Math.max(1, p.ms / max * 100) : 100) + '%'; }));
    row.append(top, track, mk('p', null, p.ok ? p.why : `${p.why} Right now: ${p.note}.`));
    row.setAttribute('aria-label', `${p.label} (${p.target}): ${p.ok ? ms(p.ms) : p.note}`);
    return row;
  }));
}

async function trace() {
  $('run').disabled = true;
  try {
    const url = '/api/trace?t=' + Date.now();
    const r = await fetch(url, { cache: 'no-store' });
    const d = await r.json();
    if (!r.ok) throw new Error(r.statusText);
    // Browser-measured round trip minus the time the server says it spent = time on the network.
    const e = performance.getEntriesByName(new URL(url, location).href).pop();
    const server = (e && e.serverTiming || []).reduce((a, s) => a + s.duration, 0);
    const netMs = e && e.responseStart ? Math.max(0, e.responseStart - e.requestStart - server) : null;
    animate(renderPath(d, netMs));
    renderProbes(d.probes, d.probes_measured_at);
  } catch (err) {
    const li = hop('trace failed', null, err.message);
    li.querySelector('p').className = 'err-text';
    $('path').replaceChildren(li);
  } finally {
    $('run').disabled = false;
  }
}
$('run').addEventListener('click', trace);
trace();
