<script setup>
import { ref } from 'vue';
import UiIcon from './UiIcon.vue';
const props = defineProps({ modelValue: String, start: String, end: String });
const emit = defineEmits(['update:modelValue', 'apply']);
const startInput = ref(props.start || '');
const endInput = ref(props.end || '');
const error = ref('');
function apply() {
  error.value = '';
  if (!startInput.value || !endInput.value) {
    error.value = 'Preencha as duas datas para aplicar o período.';
    return;
  }
  if (endInput.value < startInput.value) {
    error.value = 'A data final deve ser igual ou posterior à inicial.';
    return;
  }
  emit('apply', { start: startInput.value, end: endInput.value });
}
</script>
<template>
  <div class="period-control">
    <div class="segmented-control" role="group" aria-label="Período da análise">
      <button
        :class="{ active: modelValue === '30dias' }"
        :aria-pressed="modelValue === '30dias'"
        @click="emit('update:modelValue', '30dias')"
      >
        Últimos 30 dias</button
      ><button
        :class="{ active: modelValue === 'geral' }"
        :aria-pressed="modelValue === 'geral'"
        @click="emit('update:modelValue', 'geral')"
      >
        Geral</button
      ><button
        :class="{ active: modelValue === 'especifico' }"
        :aria-pressed="modelValue === 'especifico'"
        @click="emit('update:modelValue', 'especifico')"
      >
        <UiIcon name="CalendarDays" :size="15" />Personalizado
      </button>
    </div>
    <form v-if="modelValue === 'especifico'" class="date-range" @submit.prevent="apply">
      <label>De<input v-model="startInput" type="date" aria-label="Data inicial" required /></label
      ><span aria-hidden="true">até</span
      ><label>Até<input v-model="endInput" type="date" aria-label="Data final" required /></label
      ><button class="button button-primary" type="submit">Aplicar</button>
    </form>
    <p v-if="error" class="field-error" role="alert">{{ error }}</p>
  </div>
</template>
