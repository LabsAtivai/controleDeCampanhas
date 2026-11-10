<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api, session } from '../lib/api.js';
import { total, filteredRows, metricColumns, number, dateLabel, todaySP } from '../lib/metrics.js';
import PageHeading from '../components/PageHeading.vue';
import UiIcon from '../components/UiIcon.vue';
import DataNotice from '../components/DataNotice.vue';
import MetricBand from '../components/MetricBand.vue';
import SquadTabs from '../components/SquadTabs.vue';
import TrafficFilter from '../components/TrafficFilter.vue';
import ClientTable from '../components/ClientTable.vue';
import PeriodControl from '../components/PeriodControl.vue';
import StatusBadge from '../components/StatusBadge.vue';
import MetricChart from '../components/MetricChart.vue';
import EmptyState from '../components/EmptyState.vue';
const route = useRoute(),
  router = useRouter();
const period = ref('30dias'),
  start = ref(todaySP(-29)),
  end = ref(todaySP());
const summary = ref({
  Onboarding: [],
  'SDR REMOTO': [],
  Geral: [],
  'Sem squad': [],
});
const selected = ref('Onboarding'),
  search = ref(''),
  status = ref('all'),
  detailed = ref(false);
const loading = ref(true),
  error = ref(''),
  warnings = ref([]),
  days = ref([]),
  customerStatus = ref('indisponivel');
let version = 0;
const customer = computed(() => String(route.query.cliente || route.query.conta || ''));
const rows = computed(() => summary.value[selected.value] || []);
const visible = computed(() => filteredRows(rows.value, search.value, status.value));
const allCustomers = computed(() =>
  [
    ...new Set(
      Object.values(summary.value)
        .flat()
        .map((row) => row.cliente),
    ),
  ].sort((a, b) => a.localeCompare(b, 'pt-BR')),
);
const currentCustomer = computed(() =>
  Object.values(summary.value)
    .flat()
    .find((row) => row.cliente === customer.value),
);
const metrics = computed(() =>
  customer.value
    ? [
        { label: 'Dias de disparo', value: days.value.filter((day) => day.emailsSent > 0).length },
        { label: 'Enviados', context: 'acumulado', value: days.value.at(-1)?.cumEmailsSent },
        { label: 'Aberturas', context: 'acumulado', value: days.value.at(-1)?.cumEmailOpens },
        { label: 'Respostas', context: 'acumulado', value: days.value.at(-1)?.cumEmailReplies },
        {
          label: 'Avanços',
          context: 'no período',
          value: total(days.value, 'avancos'),
          emphasis: true,
        },
      ]
    : [
        ...metricColumns.map((column) => ({
          label: column.label,
          value: total(rows.value, column.key),
        })),
        {
          label: 'Avanços',
          context: 'no período',
          value: total(rows.value, 'avancos'),
          emphasis: true,
        },
      ],
);
const chartSeries = [
  { key: 'cumEmailsSent', label: 'Enviados', color: '#2b61d9' },
  { key: 'cumEmailOpens', label: 'Aberturas', color: '#147c83' },
  { key: 'cumEmailReplies', label: 'Respostas', color: '#7860af' },
];
const barSeries = [{ key: 'avancos', label: 'Avanços', color: '#2b61d9' }];
function params() {
  return period.value === 'geral' ? '' : `inicio=${start.value}&fim=${end.value}`;
}
async function load() {
  const current = ++version;
  loading.value = true;
  error.value = '';
  try {
    if (customer.value) {
      const response = await api(
        `/api/analise-cliente?cliente=${encodeURIComponent(customer.value)}${params() ? '&' + params() : ''}`,
      );
      if (current !== version) return;
      days.value = response.dias;
      customerStatus.value = response.statusAvanco;
      warnings.value = response.warnings || [];
    } else {
      const response = await api(`/api/analise-contas${params() ? '?' + params() : ''}`);
      if (current !== version) return;
      summary.value = response.squads;
      warnings.value = response.warnings || [];
    }
  } catch (failure) {
    if (current === version) error.value = failure.message;
  } finally {
    if (current === version) loading.value = false;
  }
}
function changePeriod(value) {
  period.value = value;
  if (value === 'especifico') return;
  if (value === '30dias') {
    start.value = todaySP(-29);
    end.value = todaySP();
  }
  load();
}
function applyPeriod(dates) {
  start.value = dates.start;
  end.value = dates.end;
  load();
}
function chooseCustomer(event) {
  router.push({
    path: '/analise.html',
    query: event.target.value ? { cliente: event.target.value } : {},
  });
}
function chooseSquad(name) {
  selected.value = name;
  search.value = '';
  status.value = 'all';
}
watch(customer, load);
onMounted(async () => {
  if (customer.value) {
    try {
      summary.value = (
        await api(`/api/analise-contas?inicio=${todaySP(-29)}&fim=${todaySP()}`)
      ).squads;
    } catch {}
  }
  await load();
});
</script>

<template>
  <div class="page-stack">
    <button v-if="customer" class="back-button" @click="router.push('/analise.html')">
      <UiIcon name="ArrowLeft" :size="15" />Todos os clientes</button
    ><PageHeading
      :title="customer || 'Análise por cliente'"
      :subtitle="
        customer
          ? 'Evolução das campanhas e avanços no período selecionado.'
          : 'Do panorama do squad ao detalhe que ajuda a decidir.'
      "
      ><button class="button button-secondary" :disabled="loading" @click="load">
        <UiIcon name="RefreshCw" :class="{ spinning: loading }" :size="16" />Atualizar
      </button></PageHeading
    >
    <div class="analysis-controls">
      <PeriodControl
        :model-value="period"
        :start="start"
        :end="end"
        @update:model-value="changePeriod"
        @apply="applyPeriod"
      /><label class="customer-select"
        ><span class="sr-only">Selecionar cliente</span><UiIcon name="Users" :size="16" /><select
          :value="customer"
          aria-label="Selecionar cliente"
          @change="chooseCustomer"
        >
          <option value="">Todos os clientes</option>
          <option v-if="customer && !allCustomers.includes(customer)" :value="customer">
            {{ customer }}
          </option>
          <option v-for="name in allCustomers" :key="name" :value="name">{{ name }}</option>
        </select></label
      >
    </div>
    <DataNotice :error="error" :warnings="warnings" @retry="load" /><template v-if="!customer"
      ><SquadTabs
        :squads="summary"
        :model-value="selected"
        scope="analysis"
        @update:model-value="chooseSquad" /><MetricBand
        :items="metrics"
        :loading="loading" /><TrafficFilter
        v-model="status"
        :rows="rows"
        :loading="loading"
        :types="session.user?.semaforoTipos" />
      <section class="client-section">
        <div class="section-toolbar">
          <div>
            <h2>
              Desempenho por cliente<span class="count-label">{{ number(rows.length) }}</span>
            </h2>
            <p>O volume é do período. O semáforo mantém sua janela de três dias.</p>
          </div>
          <div class="table-tools">
            <label class="search-field"
              ><UiIcon name="Search" :size="16" /><input
                v-model="search"
                type="search"
                placeholder="Buscar cliente ou conta"
                aria-label="Buscar cliente ou conta"
            /></label>
            <div
              class="segmented-control compact-toggle"
              role="group"
              aria-label="Detalhamento da tabela"
            >
              <button
                :class="{ active: !detailed }"
                :aria-pressed="!detailed"
                @click="detailed = false"
              >
                Resumo</button
              ><button
                :class="{ active: detailed }"
                :aria-pressed="detailed"
                @click="detailed = true"
              >
                Detalhado
              </button>
            </div>
          </div>
        </div>
        <div v-if="status !== 'all' || search" class="filter-summary">
          <span>{{ number(visible.length) }} clientes nesta consulta</span
          ><button
            class="text-button"
            @click="
              status = 'all';
              search = '';
            "
          >
            Limpar filtros<UiIcon name="X" :size="13" />
          </button>
        </div>
        <ClientTable
          :rows="visible"
          :loading="loading"
          :compact="!detailed"
          :context="selected"
        /></section></template
    ><template v-else
      ><div class="customer-context">
        <div>
          <span class="context-label">Semáforo atual</span><StatusBadge :status="customerStatus" />
        </div>
        <p>
          3 dias fechados, sem hoje<span
            >Tipos considerados: {{ session.user?.semaforoTipos || 'Interessado' }}</span
          >
        </p>
        <div v-if="currentCustomer?.contas?.length" class="customer-accounts">
          <span class="context-label">Contas vinculadas</span
          ><span>{{ currentCustomer.contas.join(', ') }}</span>
        </div>
      </div>
      <MetricBand :items="metrics" :loading="loading" /><template v-if="days.length && !loading"
        ><MetricChart
          :rows="days"
          :series="chartSeries"
          title="Evolução acumulada"
          description="Envios, aberturas e respostas, ao longo do período."
        /><MetricChart
          :rows="days"
          :series="barSeries"
          bars
          title="Avanços por dia"
          description="Registros vindos do sistema oficial de avanços."
        />
        <section class="client-section">
          <div class="section-toolbar">
            <div>
              <h2>Dia a dia</h2>
              <p>Todas as métricas e seus acumulados, sem perder o detalhe.</p>
            </div>
            <span class="subtle-text">{{ number(days.length) }} dias com registros</span>
          </div>
          <div
            class="data-panel table-scroll"
            tabindex="0"
            aria-label="Métricas diárias com rolagem horizontal"
          >
            <table class="data-table daily-table">
              <thead>
                <tr>
                  <th scope="col">Data</th>
                  <th
                    v-for="column in metricColumns"
                    :key="column.key"
                    scope="col"
                    class="number-cell"
                  >
                    {{ column.label }}
                  </th>
                  <th scope="col" class="number-cell">Avanços</th>
                  <th scope="col" class="number-cell">Enviados acum.</th>
                  <th scope="col" class="number-cell">Aberturas acum.</th>
                  <th scope="col" class="number-cell">Respostas acum.</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="day in [...days].reverse()" :key="day.data">
                  <td>{{ dateLabel(day.data, { year: 'numeric' }) }}</td>
                  <td v-for="column in metricColumns" :key="column.key" class="number-cell">
                    {{ number(day[column.key]) }}
                  </td>
                  <td class="number-cell advance-value">{{ number(day.avancos) }}</td>
                  <td class="number-cell">{{ number(day.cumEmailsSent) }}</td>
                  <td class="number-cell">{{ number(day.cumEmailOpens) }}</td>
                  <td class="number-cell">{{ number(day.cumEmailReplies) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section></template
      >
      <div v-else-if="loading" class="chart-panel chart-skeleton"><div class="skeleton"></div></div>
      <EmptyState
        v-else
        title="Sem registros neste período"
        description="Escolha outro intervalo para consultar o histórico deste cliente."
        icon="CalendarDays"
    /></template>
  </div>
</template>
