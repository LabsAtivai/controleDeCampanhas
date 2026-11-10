<script setup>
defineProps({ title: String, subtitle: String });
</script>
<template>
  <header class="page-heading">
    <div>
      <h1>{{ title }}</h1>
      <p v-if="subtitle">{{ subtitle }}</p>
      <slot name="meta" />
    </div>
    <div class="heading-actions"><slot /></div>
  </header>
</template>
