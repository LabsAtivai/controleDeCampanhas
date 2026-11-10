<script setup>
import { computed, onMounted, ref } from 'vue';
import { api, session } from '../lib/api.js';
import { notify } from '../lib/notifications.js';
import {
  groupDashboard,
  total,
  filteredRows,
  number,
  dateLabel,
  todaySP,
  metricColumns,
} from '../lib/metrics.js';
import PageHeading from '../components/PageHeading.vue';
import UiIcon from '../components/UiIcon.vue';
import DataNotice from '../components/DataNotice.vue';
import MetricBand from '../components/MetricBand.vue';
import SquadTabs from '../components/SquadTabs.vue';
import TrafficFilter from '../components/TrafficFilter.vue';
import ClientTable from '../components/ClientTable.vue';
const loading = ref(true),
  error = ref(''),
  warnings = ref([]),
  updated = ref(null);
const snapshot = ref({
  Onboarding: [],
  'SDR REMOTO': [],
  Geral: [],
  'Sem squad': [],
});
const analysis = ref({}),
  selected = ref('Onboarding'),
  search = ref(''),
  status = ref('all');
let version = 0;
const statusMap = computed(
  () =>
    new Map(
      Object.values(analysis.value)
        .flat()
        .map((row) => [row.cliente, row.statusAvanco]),
    ),
);
const squads = computed(() =>
  Object.fromEntries(
    Object.entries(snapshot.value).map(([name, campaigns]) => [
      name,
      groupDashboard(campaigns).map((row) => ({
        ...row,
        statusAvanco: statusMap.value.get(row.cliente) || 'indisponivel',
      })),
    ]),
  ),
);
const rows = computed(() => squads.value[selected.value] || []);
const visible = computed(() => filteredRows(rows.value, search.value, status.value));
const metrics = computed(() => [
  ...metricColumns.map((column) => ({ label: column.label, value: total(rows.value, column.key) })),
  { label: 'Avanços', context: 'hoje', value: total(rows.value, 'avancosHoje'), emphasis: true },
]);
async function load() {
  const current = ++version;
  loading.value = true;
  error.value = '';
  const [latest, summary] = await Promise.allSettled([
    api('/api/squads'),
    api(`/api/analise-contas?inicio=${todaySP(-29)}&fim=${todaySP()}`),
  ]);
  if (current !== version) return;
  const notes = [];
  if (latest.status === 'fulfilled') {
    snapshot.value = latest.value.squads;
    updated.value = latest.value.geradoEm;
    notes.push(...(latest.value.warnings || []));
  } else error.value = latest.reason.message;
  if (summary.status === 'fulfilled') {
    analysis.value = summary.value.squads;
    notes.push(...(summary.value.warnings || []));
  } else {
    analysis.value = {};
    notes.push(
      'Não foi possível consultar o semáforo. As métricas de campanha disponíveis continuam visíveis.',
    );
  }
  warnings.value = [...new Set(notes)];
  loading.value = false;
}
function chooseSquad(name) {
  selected.value = name;
  search.value = '';
  status.value = 'all';
}
function advances() {
  if (!session.user?.avancosUrl) {
    notify('O endereço do sistema oficial de avanços ainda não foi configurado.', 'error');
    return;
  }
  try {
    const url = new URL(session.user.avancosUrl, location.origin);
    if (['http:', 'https:'].includes(url.protocol))
      window.open(url.href, '_blank', 'noopener,noreferrer');
  } catch {
    notify('O endereço do sistema de avanços não é válido.', 'error');
  }
}
onMounted(load);
</script>

<template>
  <div class="page-stack">
    <PageHeading
      title="Visão geral"
      subtitle="Cada campanha no seu contexto. Cada cliente, com o próximo passo à vista."
      ><button class="button button-secondary" :disabled="loading" @click="load">
        <UiIcon name="RefreshCw" :class="{ spinning: loading }" :size="16" />Atualizar</button
      ><button class="button button-primary" @click="advances">
        <UiIcon name="Plus" :size="17" />Registrar avanço</button
      ><template #meta
        ><p class="update-stamp" v-if="updated">
          <span class="fresh-dot"></span>Consultado em
          {{ dateLabel(updated, { hour: '2-digit', minute: '2-digit' }) }}
        </p></template
      ></PageHeading
    ><DataNotice :error="error" :warnings="warnings" @retry="load" /><SquadTabs
      :squads="squads"
      :model-value="selected"
      @update:model-value="chooseSquad"
    /><MetricBand :items="metrics" :loading="loading" />
    <div class="scope-note">
      <UiIcon name="Clock3" :size="15" /><span
        >Métricas da última coleta de cada campanha. As datas podem variar entre clientes.</span
      >
    </div>
    <TrafficFilter
      v-model="status"
      :rows="rows"
      :loading="loading"
      :types="session.user?.semaforoTipos"
    />
    <section class="client-section">
      <div class="section-toolbar">
        <div>
          <h2>
            Clientes do squad<span class="count-label">{{ number(rows.length) }}</span>
          </h2>
          <p>Volume de campanha e semáforo, lado a lado.</p>
        </div>
        <label class="search-field"
          ><UiIcon name="Search" :size="17" /><input
            v-model="search"
            type="search"
            placeholder="Buscar cliente ou conta"
            aria-label="Buscar cliente ou conta"
        /></label>
      </div>
      <div v-if="status !== 'all' || search" class="filter-summary">
        <span
          >{{ number(visible.length) }} de {{ number(rows.length) }} clientes nesta consulta</span
        ><button
          class="text-button"
          @click="
            search = '';
            status = 'all';
          "
        >
          Limpar filtros<UiIcon name="X" :size="13" />
        </button>
      </div>
      <ClientTable :rows="visible" :loading="loading" daily :context="selected" />
    </section>
    <div class="page-footnote">
      <UiIcon name="Info" :size="15" />
      <p>
        O semáforo considera os tipos configurados no sistema nos três dias fechados anteriores a
        hoje. Ele é independente da data da última coleta.
      </p>
    </div>
  </div>
</template>
