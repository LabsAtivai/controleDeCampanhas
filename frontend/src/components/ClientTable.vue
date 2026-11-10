<script setup>
import { computed, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';
import { metricColumns, number, percent, dateLabel, sortRows } from '../lib/metrics.js';
import StatusBadge from './StatusBadge.vue';
import UiIcon from './UiIcon.vue';
import EmptyState from './EmptyState.vue';
const props = defineProps({
  rows: Array,
  loading: Boolean,
  daily: Boolean,
  compact: Boolean,
  context: String,
});
const sortKey = ref(props.daily ? 'totalContacted' : 'emailsSent');
const direction = ref('desc');
const page = ref(1);
const pageSize = 15;
const columns = computed(() =>
  props.compact ? [{ key: 'emailsSent', label: 'Enviados' }] : metricColumns,
);
const sorted = computed(() => sortRows(props.rows, sortKey.value, direction.value));
const pages = computed(() => Math.max(1, Math.ceil(sorted.value.length / pageSize)));
const visibleRows = computed(() =>
  sorted.value.slice((page.value - 1) * pageSize, page.value * pageSize),
);
watch(
  () => props.rows,
  () => {
    page.value = 1;
  },
);
function sort(key) {
  direction.value = sortKey.value === key && direction.value === 'desc' ? 'asc' : 'desc';
  sortKey.value = key;
}
function collectDate(row) {
  return row.minData && row.minData !== row.data
    ? `${dateLabel(row.minData)} – ${dateLabel(row.data)}`
    : dateLabel(row.data || row.ultimaColeta);
}
</script>

<template>
  <section class="data-panel" :aria-busy="loading">
    <div
      class="table-scroll"
      tabindex="0"
      aria-label="Tabela de métricas por cliente, com rolagem horizontal quando necessário"
    >
      <table class="data-table">
        <thead>
          <tr>
            <th scope="col" class="client-column">
              <button @click="sort('cliente')">
                Cliente<UiIcon name="ArrowUpDown" :size="13" />
              </button>
            </th>
            <th v-if="!daily && !compact" scope="col" class="number-cell">
              <button @click="sort('diasDisparos')">Dias de disparo</button>
            </th>
            <th
              v-for="column in columns"
              :key="column.key"
              scope="col"
              class="number-cell"
              :aria-sort="
                sortKey === column.key ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'
              "
            >
              <button @click="sort(column.key)">
                {{ column.label }}<UiIcon name="ArrowUpDown" :size="12" />
              </button>
            </th>
            <th scope="col" class="number-cell">
              <button @click="sort(daily ? 'avancosHoje' : 'avancos')">
                Avanços<span class="th-context">{{ daily ? 'hoje' : 'no período' }}</span>
              </button>
            </th>
            <template v-if="!daily && !compact"
              ><th scope="col" class="number-cell">Taxa abertura</th>
              <th scope="col" class="number-cell">Taxa resposta</th></template
            >
            <th scope="col">Semáforo</th>
            <th v-if="!compact" scope="col">Última coleta</th>
            <th scope="col" class="row-end"><span class="sr-only">Abrir análise</span></th>
          </tr>
        </thead>
        <tbody id="gridBody">
          <template v-if="loading"
            ><tr v-for="i in 6" :key="i" class="skeleton-row" aria-hidden="true">
              <td :colspan="columns.length + 7"><span class="skeleton"></span></td></tr
          ></template>
          <tr v-else v-for="row in visibleRows" :key="row.cliente" :data-client="row.cliente">
            <td class="client-column">
              <div class="client-cell">
                <span class="client-monogram" aria-hidden="true">{{
                  row.cliente
                    .replace(/^cliente /i, '')
                    .slice(0, 2)
                    .toUpperCase()
                }}</span>
                <div>
                  <RouterLink
                    class="client-link"
                    :to="{ path: '/analise.html', query: { cliente: row.cliente } }"
                    >{{ row.cliente }}</RouterLink
                  >
                  <p class="account-subline" :title="(row.contas || []).join(', ')">
                    {{
                      daily
                        ? `${number(row.campanhas)} campanha${row.campanhas === 1 ? '' : 's'} · `
                        : ''
                    }}{{ number(row.contas?.length || 0) }} conta{{
                      row.contas?.length === 1 ? '' : 's'
                    }}
                  </p>
                </div>
              </div>
            </td>
            <td v-if="!daily && !compact" class="number-cell">{{ number(row.diasDisparos) }}</td>
            <td v-for="column in columns" :key="column.key" class="number-cell">
              {{ number(row[column.key]) }}
            </td>
            <td class="number-cell advance-value">
              {{ number(row[daily ? 'avancosHoje' : 'avancos']) }}
            </td>
            <template v-if="!daily && !compact"
              ><td class="number-cell">{{ percent(row.taxaAbertura) }}</td>
              <td class="number-cell">{{ percent(row.taxaResposta) }}</td></template
            >
            <td><StatusBadge :status="row.statusAvanco" small /></td>
            <td v-if="!compact" class="date-cell" :class="{ 'stale-date': row.stale }">
              <span v-if="row.stale" class="status-dot"></span>{{ collectDate(row) }}
            </td>
            <td class="row-end">
              <RouterLink
                :to="{ path: '/analise.html', query: { cliente: row.cliente } }"
                class="icon-button"
                :aria-label="`Abrir análise de ${row.cliente}`"
                ><UiIcon name="ChevronRight" :size="16"
              /></RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <EmptyState v-if="!loading && !rows.length" />
    <footer class="table-footer">
      <span
        >{{ number(rows.length) }} cliente{{ rows.length === 1 ? '' : 's'
        }}<span v-if="context" class="footer-context"> · {{ context }}</span></span
      >
      <div class="pagination">
        <span>{{ page }} de {{ pages }}</span
        ><button
          class="icon-button"
          :disabled="page <= 1"
          aria-label="Página anterior"
          @click="page--"
        >
          <UiIcon name="ChevronLeft" :size="16" /></button
        ><button
          class="icon-button"
          :disabled="page >= pages"
          aria-label="Próxima página"
          @click="page++"
        >
          <UiIcon name="ChevronRight" :size="16" />
        </button>
      </div>
    </footer>
  </section>
</template>
