// Shared header behaviour: point the tabs at the right address on the tailnet (ports) or on the
// public domain (subdomains), and mark the current page.
const APPS = { lg: 8446, trading: 8447, trace: 8448 };
const host = location.hostname;
const onTailnet = host.endsWith('.ts.net');
const base = host.split('.').slice(1).join('.');
for (const a of document.querySelectorAll('.tabs a[data-app]')) {
  const app = a.dataset.app;
  a.href = onTailnet ? `https://${host}:${APPS[app]}/` : `https://${app}.${base}/`;
  if (app === document.body.dataset.app) a.setAttribute('aria-current', 'page');
}
