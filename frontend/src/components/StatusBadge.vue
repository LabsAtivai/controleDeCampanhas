<script setup>
import { computed } from 'vue';
import { statusDefinitions } from '../lib/metrics.js';
import UiIcon from './UiIcon.vue';
const props = defineProps({ status: String, label: String, small: Boolean });
const definition = computed(
  () =>
    statusDefinitions[props.status] || {
      label: 'Não informado',
      tone: 'neutral',
      description: 'Estado não informado.',
    },
);
</script>

<template>
  <span
    class="status-badge"
    :class="[`tone-${definition.tone}`, { 'status-small': small }]"
    :title="definition.description"
    ><span class="status-dot" v-if="status !== 'indisponivel' && status !== 'sem_vinculo'"></span
    ><UiIcon v-else :name="status === 'indisponivel' ? 'CircleHelp' : 'Circle'" :size="12" />{{
      label || definition.label
    }}</span
  >
</template>
