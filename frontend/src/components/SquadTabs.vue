<script setup>
import { number } from '../lib/metrics.js';
defineProps({ squads: Object, modelValue: String, scope: { type: String, default: 'dashboard' } });
defineEmits(['update:modelValue']);
</script>
<template>
  <nav class="squad-tabs" aria-label="Filtrar por squad">
    <button
      v-for="(rows, name) in squads"
      :key="name"
      class="squad-tab"
      :class="{ active: modelValue === name }"
      :aria-pressed="modelValue === name"
      :aria-label="scope === 'dashboard' ? name : `Squad ${name}`"
      :data-squad-choice="name"
      @click="$emit('update:modelValue', name)"
    >
      {{ name === 'SDR REMOTO' ? 'SDR Remoto' : name }}<span>{{ number(rows.length) }}</span>
    </button>
  </nav>
</template>
