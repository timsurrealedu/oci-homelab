const f = document.getElementById('f'), go = document.getElementById('go'), res = document.getElementById('res');
const line = (text, cls, d) => {
  const s = document.createElement('span');
  s.className = 'ln' + (cls ? ' ' + cls : '');
  s.style.setProperty('--d', d);
  s.textContent = text;
  return s;
};

f.tool.addEventListener('change', () => { f.type.hidden = f.tool.value !== 'dns'; });
f.addEventListener('submit', async (e) => {
  e.preventDefault();
  go.disabled = true;
  res.className = 'term';
  res.replaceChildren(line(f.tool.value === 'mtr' ? 'tracing the route, about 10 seconds…' : 'running…', 'muted', 0));
  try {
    const r = await fetch('/api/run?' + new URLSearchParams(new FormData(f)));
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || r.statusText);
    const out = (d.output.trim() || '(no output)').split('\n').slice(0, 200);
    res.replaceChildren(line('$ ' + d.command, 'cmd', 0), ...out.map((t, i) => line(t, '', Math.min(i + 1, 40))));
  } catch (err) {
    res.className = 'term err';
    res.replaceChildren(line('error: ' + err.message, '', 0));
  } finally {
    go.disabled = false;
  }
});
