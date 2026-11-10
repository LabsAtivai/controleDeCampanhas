export const metricColumns = [
  { key: 'totalContacted', label: 'Contatados' },
  { key: 'emailsSent', label: 'Enviados' },
  { key: 'delivered', label: 'Entregues' },
  { key: 'emailOpens', label: 'Aberturas' },
  { key: 'linkClicks', label: 'Cliques' },
  { key: 'emailReplies', label: 'Respostas' },
];

export const statusDefinitions = {
  verde: {
    label: 'Em dia',
    description: 'Dois ou mais avanços na janela do semáforo.',
    tone: 'success',
    order: 2,
  },
  amarelo: {
    label: 'Atenção',
    description: 'Um avanço na janela do semáforo.',
    tone: 'warning',
    order: 1,
  },
  vermelho: {
    label: 'Sem avanço',
    description: 'Nenhum avanço na janela do semáforo.',
    tone: 'danger',
    order: 0,
  },
  sem_vinculo: {
    label: 'Sem vínculo',
    description: 'Cliente sem vínculo no sistema de avanços.',
    tone: 'neutral',
    order: 3,
  },
  indisponivel: {
    label: 'Indisponível',
    description: 'Não foi possível consultar o semáforo.',
    tone: 'neutral',
    order: 4,
  },
};

export function number(value) {
  return value == null || !Number.isFinite(Number(value))
    ? '—'
    : Number(value).toLocaleString('pt-BR');
}

export function percent(value) {
  return value == null || !Number.isFinite(Number(value))
    ? '—'
    : `${Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 2 })}%`;
}

export function dateLabel(value, options = {}) {
  if (!value) return '—';
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00-03:00` : value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: 'short',
    timeZone: 'America/Sao_Paulo',
    ...options,
  }).format(date);
}

export function todaySP(offset = 0) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Sao_Paulo' }).format(
    new Date(Date.now() + offset * 86400000),
  );
}

export function total(rows, key) {
  return rows.some((row) => row[key] == null)
    ? null
    : rows.reduce((sum, row) => sum + Number(row[key] || 0), 0);
}

export function groupDashboard(campaigns) {
  const grouped = new Map();
  for (const row of campaigns) {
    const name = row.cliente || row.conta || '—';
    if (!grouped.has(name))
      grouped.set(name, {
        cliente: name,
        contas: new Set(),
        campanhas: 0,
        minData: row.data,
        data: null,
        avancosHoje: row.avancosHoje,
        stale: false,
        ...Object.fromEntries(metricColumns.map(({ key }) => [key, 0])),
      });
    const item = grouped.get(name);
    item.contas.add(row.conta);
    item.campanhas += 1;
    item.stale ||= Boolean(row.stale);
    for (const { key } of metricColumns) {
      item[key] =
        item[key] == null || row[key] == null || !Number.isFinite(Number(row[key]))
          ? null
          : item[key] + Number(row[key]);
    }
    if (row.data && (!item.data || row.data > item.data)) item.data = row.data;
    if (row.data && (!item.minData || row.data < item.minData)) item.minData = row.data;
  }
  return [...grouped.values()].map((item) => ({ ...item, contas: [...item.contas] }));
}

export function filteredRows(rows, search = '', status = 'all') {
  const query = search.trim().toLocaleLowerCase('pt-BR');
  return rows.filter(
    (row) =>
      (status === 'all' || row.statusAvanco === status) &&
      (!query ||
        `${row.cliente} ${(row.contas || []).join(' ')}`
          .toLocaleLowerCase('pt-BR')
          .includes(query)),
  );
}

export function sortRows(rows, key, direction = 'desc') {
  return [...rows].sort((a, b) => {
    if (a[key] == null) return b[key] == null ? 0 : 1;
    if (b[key] == null) return -1;
    const difference =
      typeof a[key] === 'number'
        ? a[key] - b[key]
        : String(a[key]).localeCompare(String(b[key]), 'pt-BR');
    return difference * (direction === 'asc' ? 1 : -1);
  });
}
