<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue';
import { number, dateLabel } from '../lib/metrics.js';
import { isAvailable, chartMaximum, linePath } from '../lib/chart.js';
const props = defineProps({
  rows: Array,
  series: Array,
  bars: Boolean,
  title: String,
  description: String,
});
const host = ref(null);
const width = ref(800);
const hovered = ref(null);
const disabled = ref([]);
const height = 240;
const left = 46,
  right = 18,
  top = 16,
  bottom = 35;
const activeSeries = computed(() =>
  props.series.filter((series) => !disabled.value.includes(series.key)),
);
const max = computed(() =>
  chartMaximum(
    props.rows,
    activeSeries.value.map((series) => series.key),
  ),
);
const chartWidth = computed(() => Math.max(230, width.value - left - right));
const chartHeight = height - top - bottom;
const divisions = computed(() => Math.min(4, Math.ceil(max.value)));
const ticks = computed(() =>
  Array.from({ length: divisions.value + 1 }, (_, i) => ({
    y: top + (i * chartHeight) / divisions.value,
    value: Math.round(max.value * (1 - i / divisions.value)),
  })),
);
const dateIndexes = computed(() =>
  props.rows.length > 2 && width.value > 500
    ? [0, Math.floor((props.rows.length - 1) / 2), props.rows.length - 1]
    : [...new Set([0, props.rows.length - 1])],
);
const current = computed(() => (hovered.value == null ? null : props.rows[hovered.value]));
function x(i) {
  if (props.rows.length <= 1) return left + chartWidth.value / 2;
  const first = new Date(props.rows[0].data + 'T00:00:00Z').getTime();
  const last = new Date(props.rows.at(-1).data + 'T00:00:00Z').getTime();
  const day = new Date(props.rows[i].data + 'T00:00:00Z').getTime();
  return (
    left +
    (last > first ? (day - first) / (last - first) : i / (props.rows.length - 1)) * chartWidth.value
  );
}
function y(value) {
  return isAvailable(value) ? top + chartHeight - (Number(value) / max.value) * chartHeight : null;
}
function path(key) {
  return linePath(props.rows, key, x, y);
}
function hover(event) {
  if (!props.rows.length) return;
  const position = event.clientX - event.currentTarget.getBoundingClientRect().left;
  hovered.value = props.rows.reduce(
    (best, _, index) =>
      Math.abs(x(index) - position) < Math.abs(x(best) - position) ? index : best,
    0,
  );
}
function toggle(key) {
  disabled.value = disabled.value.includes(key)
    ? disabled.value.filter((item) => item !== key)
    : [...disabled.value, key];
}
let observer;
onMounted(() => {
  observer = new ResizeObserver((entries) => {
    width.value = Math.max(300, entries[0].contentRect.width);
  });
  observer.observe(host.value);
});
onBeforeUnmount(() => observer?.disconnect());
</script>

<template>
  <section class="chart-panel">
    <div class="chart-heading">
      <div>
        <h2>{{ title }}</h2>
        <p>{{ description }}</p>
      </div>
      <div v-if="!bars" class="chart-legend" role="group" aria-label="Séries do gráfico">
        <button
          v-for="series in series"
          :key="series.key"
          :class="{ 'series-muted': disabled.includes(series.key) }"
          :aria-pressed="!disabled.includes(series.key)"
          @click="toggle(series.key)"
        >
          <span :style="{ backgroundColor: series.color }"></span>{{ series.label }}
        </button>
      </div>
    </div>
    <div ref="host" class="chart-canvas">
      <svg
        :viewBox="`0 0 ${width} ${height}`"
        width="100%"
        :height="height"
        role="img"
        :aria-label="`${title}. Dados detalhados na tabela diária abaixo.`"
        @pointermove="hover"
        @pointerleave="hovered = null"
      >
        <g v-for="(tick, index) in ticks" :key="index">
          <line :x1="left" :x2="width - right" :y1="tick.y" :y2="tick.y" class="chart-grid" />
          <text :x="left - 10" :y="tick.y + 4" text-anchor="end" class="chart-label">
            {{ number(tick.value) }}
          </text>
        </g>
        <template v-if="!bars">
          <g v-for="series in activeSeries" :key="series.key">
            <path
              :d="path(series.key)"
              fill="none"
              :stroke="series.color"
              stroke-width="2.5"
              stroke-linejoin="round"
              stroke-linecap="round"
            />
            <template v-for="(row, i) in rows" :key="row.data">
              <circle
                v-if="
                  isAvailable(row[series.key]) &&
                  !isAvailable(rows[i - 1]?.[series.key]) &&
                  !isAvailable(rows[i + 1]?.[series.key])
                "
                :cx="x(i)"
                :cy="y(row[series.key])"
                r="4"
                :fill="series.color"
              />
            </template>
          </g>
        </template>
        <template v-else>
          <template v-for="(row, i) in rows" :key="row.data">
            <rect
              v-if="isAvailable(row[series[0].key])"
              :x="x(i) - Math.min(18, (chartWidth / Math.max(rows.length, 1)) * 0.6) / 2"
              :y="y(row[series[0].key])"
              :width="Math.min(18, (chartWidth / Math.max(rows.length, 1)) * 0.6)"
              :height="Math.max(0, top + chartHeight - y(row[series[0].key]))"
              rx="2"
              :fill="series[0].color"
            />
          </template>
        </template>
        <text
          v-for="index in dateIndexes"
          :key="index"
          :x="x(index)"
          :y="height - 10"
          :text-anchor="index === 0 ? 'start' : index === rows.length - 1 ? 'end' : 'middle'"
          class="chart-label"
        >
          {{ dateLabel(rows[index]?.data) }}
        </text>
        <g v-if="current">
          <line
            :x1="x(hovered)"
            :x2="x(hovered)"
            :y1="top"
            :y2="top + chartHeight"
            class="chart-crosshair"
          />
          <template v-for="series in activeSeries" :key="series.key">
            <circle
              v-if="isAvailable(current[series.key])"
              :cx="x(hovered)"
              :cy="y(current[series.key])"
              r="4"
              :fill="series.color"
              stroke="white"
              stroke-width="2"
            />
          </template>
        </g>
      </svg>
      <div
        v-if="current"
        class="chart-tooltip"
        :style="{ left: `${Math.max(0, Math.min(width - 190, x(hovered) - 80))}px` }"
      >
        <strong>{{ dateLabel(current.data, { year: 'numeric' }) }}</strong
        ><span v-for="series in activeSeries" :key="series.key"
          >{{ series.label }}<b>{{ number(current[series.key]) }}</b></span
        >
      </div>
    </div>
    <label v-if="rows.length > 1" class="chart-keyboard"
      ><span>Explorar dia</span
      ><input
        type="range"
        min="0"
        :max="rows.length - 1"
        :value="hovered || 0"
        :aria-label="`Explorar ${title} por dia`"
        @input="hovered = Number($event.target.value)"
      /><span>{{ dateLabel(rows[hovered || 0]?.data) }}</span></label
    >
  </section>
</template>
