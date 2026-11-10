import { reactive } from 'vue';

export const session = reactive({ user: null, loading: true, error: '' });

export async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch(path, {
      ...options,
      signal: options.signal || controller.signal,
      credentials: 'same-origin',
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers || {}),
        ...(session.user?.csrf ? { 'X-CSRF-Token': session.user.csrf } : {}),
      },
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(
        result.error || 'Não foi possível concluir a operação. Tente novamente.',
      );
      error.status = response.status;
      if (response.status === 401) {
        session.user = null;
        if (path !== '/api/auth/me' && path !== '/api/auth/login')
          window.dispatchEvent(new Event('ativa:session-expired'));
      }
      throw error;
    }
    return result;
  } catch (error) {
    if (error.name === 'AbortError')
      throw new Error('A consulta demorou mais que o esperado. Tente atualizar.');
    if (error instanceof TypeError)
      throw new Error(
        'Não foi possível conectar ao sistema. Verifique sua conexão e tente novamente.',
      );
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function loadSession() {
  session.loading = true;
  try {
    session.user = await api('/api/auth/me');
    session.error = '';
  } catch (error) {
    session.user = null;
    session.error = error.status === 401 ? '' : error.message;
  } finally {
    session.loading = false;
  }
  return session.user;
}

export function post(path, body) {
  return api(path, {
    method: 'POST',
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
}
