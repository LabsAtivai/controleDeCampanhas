import test from 'node:test';
import assert from 'node:assert/strict';
import { isAvailable, chartMaximum, linePath } from '../src/lib/chart.js';
import {
  metricColumns,
  groupDashboard,
  total,
  filteredRows,
  sortRows,
  statusDefinitions,
  number,
  percent,
} from '../src/lib/metrics.js';

test('preserva todas as seis métricas de campanha e não duplica avanços por campanha', () => {
  const metrics = Object.fromEntries(metricColumns.map(({ key }, index) => [key, index + 1]));
  const result = groupDashboard([
    { cliente: 'Cliente', conta: 'a@example.test', data: '2026-11-08', avancosHoje: 4, ...metrics },
    { cliente: 'Cliente', conta: 'b@example.test', data: '2026-11-09', avancosHoje: 4, ...metrics },
  ])[0];
  metricColumns.forEach(({ key }, index) => assert.equal(result[key], (index + 1) * 2));
  assert.equal(result.avancosHoje, 4);
  assert.equal(result.campanhas, 2);
  assert.equal(result.contas.length, 2);
  assert.equal(result.minData, '2026-11-08');
  assert.equal(result.data, '2026-11-09');
});

test('indisponibilidade continua diferente de zero', () => {
  assert.equal(total([{ avancos: 2 }, { avancos: null }], 'avancos'), null);
  assert.equal(number(null), '—');
  assert.equal(number(0), '0');
  assert.equal(percent(0), '0%');
});

test('agregacao preserva metricas indisponiveis entre campanhas', () => {
  const base = Object.fromEntries(metricColumns.map(({ key }) => [key, 0]));
  const rows = groupDashboard([
    { cliente: 'A', ...base, emailOpens: null },
    { cliente: 'A', ...base, emailOpens: 12 },
  ]);
  assert.equal(rows[0].emailOpens, null);
  assert.equal(rows[0].emailsSent, 0);
});

test('grafico interrompe linhas em lacunas e mantem zero como observacao', () => {
  const rows = [2, null, 0, 4, undefined, 3].map((value) => ({ value }));
  assert.equal(
    linePath(
      rows,
      'value',
      (i) => i,
      (v) => v,
    ),
    'M 0.0 2.0 M 2.0 0.0 L 3.0 4.0 M 5.0 3.0',
  );
  assert.equal(chartMaximum(rows, ['value']), 4);
  assert.equal(chartMaximum([{ value: null }], ['value']), 1);
  assert.equal(isAvailable(null), false);
  assert.equal(isAvailable(undefined), false);
  assert.equal(isAvailable(''), false);
  assert.equal(isAvailable(NaN), false);
  assert.equal(isAvailable(0), true);
});

test('preserva os cinco estados do semáforo vindos do backend', () => {
  assert.deepEqual(Object.keys(statusDefinitions), [
    'verde',
    'amarelo',
    'vermelho',
    'sem_vinculo',
    'indisponivel',
  ]);
  assert.equal(
    filteredRows(
      [
        { cliente: 'A', statusAvanco: 'vermelho' },
        { cliente: 'B', statusAvanco: 'verde' },
      ],
      '',
      'vermelho',
    ).length,
    1,
  );
});

test('busca também por conta e ordena números sem alterar os dados recebidos', () => {
  const rows = [
    { cliente: 'Cliente A', contas: ['teste@example.test'], emailsSent: 10 },
    { cliente: 'Cliente B', emailsSent: 20 },
  ];
  assert.equal(filteredRows(rows, 'teste@')[0].cliente, 'Cliente A');
  assert.equal(sortRows(rows, 'emailsSent')[0].cliente, 'Cliente B');
  assert.equal(rows[0].cliente, 'Cliente A');
});
