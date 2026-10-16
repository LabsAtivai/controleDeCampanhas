

// A conexão fica no sessionStorage: o token some quando a aba fecha.
function getConn() {
  return {
    url: (sessionStorage.getItem('painel_api_url') || '').replace(/\/$/, ''),
    token: sessionStorage.getItem('painel_api_token') || '',
  };
}

function setConn(url, token) {
  sessionStorage.setItem('painel_api_url', url);
  sessionStorage.setItem('painel_api_token', token);
}

// Versões antigas guardavam a conexão no localStorage. Copia para a sessão
// (se ela ainda não tiver) e apaga do localStorage.
function migrarConexaoAntiga() {
  for (const chave of ['painel_api_url', 'painel_api_token']) {
    const antigo = localStorage.getItem(chave);
    if (antigo === null) continue;
    if (sessionStorage.getItem(chave) === null) sessionStorage.setItem(chave, antigo);
    localStorage.removeItem(chave);
  }
}
migrarConexaoAntiga();

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
