// Funções compartilhadas pelas páginas do painel (index, dados, analise).
// Script clássico, sem módulo: tudo aqui fica global.

function getConn() {
  return {
    url: (localStorage.getItem('painel_api_url') || '').replace(/\/$/, ''),
    token: localStorage.getItem('painel_api_token') || '',
  };
}

function estaNoIndex() {
  return /(^|\/)(index\.html)?$/.test(location.pathname);
}

async function api(path, opts = {}) {
  const c = getConn();
  if (!c.url) throw new Error('configure a conexão na tela inicial');
  let res;
  try {
    res = await fetch(c.url + path, {
      ...opts,
      headers: { ...(opts.headers || {}), 'X-API-Token': c.token },
    });
  } catch (e) {
    throw new Error('Não foi possível falar com a API — confira a URL e se o servidor está no ar');
  }
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) {
    // No index só lança: o polling de lá chamaria o redirect a cada 2 s.
    if (!estaNoIndex()) location.href = 'index.html?erro=token';
    throw new Error(data.error || 'token inválido');
  }
  if (res.status >= 500) throw new Error('Erro no servidor, tente de novo');
  if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function formatNumero(n) {
  if (n === null || n === undefined) return '—';
  return Number(n).toLocaleString('pt-BR');
}
