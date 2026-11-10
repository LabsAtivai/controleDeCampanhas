<script setup>
import { RouterLink } from 'vue-router';
import { session } from '../lib/api.js';
import UiIcon from './UiIcon.vue';
defineEmits(['navigate']);
</script>
<template>
  <nav class="main-navigation" aria-label="Navegação principal">
    <span class="nav-group-label">Acompanhamento</span
    ><RouterLink to="/dados.html" @click="$emit('navigate')"
      ><UiIcon name="LayoutDashboard" /><span>Visão geral</span></RouterLink
    ><RouterLink to="/analise.html" @click="$emit('navigate')"
      ><UiIcon name="ChartLine" /><span>Análise por cliente</span></RouterLink
    ><template v-if="session.user?.role === 'admin'"
      ><span class="nav-group-label nav-group-admin">Administração</span
      ><RouterLink to="/index.html" @click="$emit('navigate')"
        ><UiIcon name="Workflow" /><span>Operação de dados</span></RouterLink
      ><RouterLink to="/equipe.html" @click="$emit('navigate')"
        ><UiIcon name="Users" /><span>Equipe e acessos</span></RouterLink
      ></template
    >
  </nav>
</template>
