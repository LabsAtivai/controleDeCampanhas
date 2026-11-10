<script setup>
import UiIcon from './UiIcon.vue';
defineProps({
  title: { type: String, default: 'Nenhum cliente encontrado' },
  description: {
    type: String,
    default: 'Experimente outro nome ou ajuste os filtros para ampliar a consulta.',
  },
  icon: { type: String, default: 'Search' },
});
</script>
<template>
  <div class="empty-state">
    <UiIcon :name="icon" :size="28" />
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
    <slot />
  </div>
</template>
