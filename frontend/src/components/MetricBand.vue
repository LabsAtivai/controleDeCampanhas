<script setup>
import { number, percent } from '../lib/metrics.js';
defineProps({ items: { type: Array, default: () => [] }, loading: Boolean });
</script>
<template>
  <dl
    class="metric-band"
    :style="{ '--metric-count': items.length }"
    :data-count="items.length"
    :aria-busy="loading"
  >
    <div
      v-for="item in items"
      :key="item.label"
      class="metric-cell"
      :class="{
        'metric-emphasis': item.emphasis,
        'metric-wide': String(item.value ?? '').length > 7,
      }"
    >
      <dt>
        {{ item.label }}<span v-if="item.context" class="metric-context">{{ item.context }}</span>
      </dt>
      <dd :class="{ skeleton: loading }">
        {{
          loading ? '0000' : item.format === 'percent' ? percent(item.value) : number(item.value)
        }}
      </dd>
    </div>
  </dl>
</template>
