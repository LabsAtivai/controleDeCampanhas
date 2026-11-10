<script setup>
import UiIcon from './UiIcon.vue';
defineProps({ warnings: { type: Array, default: () => [] }, error: String });
defineEmits(['retry']);
</script>
<template>
  <div v-if="error" class="notice notice-error" role="alert">
    <UiIcon name="TriangleAlert" />
    <div>
      <strong>Não foi possível carregar os dados</strong>
      <p>{{ error }}</p>
    </div>
    <button class="button button-quiet" @click="$emit('retry')">Tentar novamente</button>
  </div>
  <details v-else-if="warnings.length" class="notice notice-warning">
    <summary>
      <UiIcon name="Info" /><span>Confira o contexto destes dados</span
      ><span class="notice-count">{{ warnings.length }}</span
      ><UiIcon name="ChevronDown" class="notice-chevron" />
    </summary>
    <ul>
      <li v-for="message in [...new Set(warnings)]" :key="message">{{ message }}</li>
    </ul>
  </details>
</template>
