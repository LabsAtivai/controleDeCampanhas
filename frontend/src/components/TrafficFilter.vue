<script setup>
import { computed } from 'vue';
import { statusDefinitions, number } from '../lib/metrics.js';
import UiIcon from './UiIcon.vue';
const props = defineProps({
  rows: Array,
  modelValue: String,
  loading: Boolean,
  types: { type: String, default: 'Interessado' },
});
defineEmits(['update:modelValue']);
const counts = computed(() =>
  Object.fromEntries(
    Object.keys(statusDefinitions).map((key) => [
      key,
      props.rows.filter((row) => row.statusAvanco === key).length,
    ]),
  ),
);
</script>

<template>
  <section class="traffic-section" aria-label="Semáforo dos clientes">
    <div class="traffic-heading">
      <h2>Semáforo dos clientes</h2>
      <span
        class="help-hint"
        tabindex="0"
        :aria-label="`Semáforo dos três dias fechados anteriores a hoje. Tipos: ${types}. Os estados são fornecidos pelo sistema.`"
        :title="`3 dias fechados, sem hoje · ${types}`"
        ><UiIcon name="Info" :size="14" /><span>3 dias fechados, sem hoje</span></span
      >
    </div>
    <div class="traffic-filters" role="group" aria-label="Filtrar pelo semáforo">
      <button
        class="traffic-option"
        :class="{ selected: modelValue === 'all' }"
        :aria-pressed="modelValue === 'all'"
        @click="$emit('update:modelValue', 'all')"
      >
        <span>Todos</span><b>{{ number(rows.length) }}</b></button
      ><button
        v-for="(definition, key) in statusDefinitions"
        :key="key"
        class="traffic-option"
        :class="[`traffic-${definition.tone}`, { selected: modelValue === key }]"
        :aria-pressed="modelValue === key"
        :title="definition.description"
        @click="$emit('update:modelValue', key)"
      >
        <span class="status-dot" v-if="key !== 'sem_vinculo' && key !== 'indisponivel'"></span
        ><UiIcon
          v-else
          :name="key === 'indisponivel' ? 'CircleHelp' : 'Circle'"
          :size="13"
        /><span>{{ definition.label }}</span
        ><b>{{ loading ? '—' : number(counts[key]) }}</b>
      </button>
    </div>
  </section>
</template>
