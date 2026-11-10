<script setup>
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter, RouterView, RouterLink } from 'vue-router';
import { session, post } from './lib/api.js';
import { notifications, notify } from './lib/notifications.js';
import { dateLabel } from './lib/metrics.js';
import BrandMark from './components/BrandMark.vue';
import NavLinks from './components/NavLinks.vue';
import UiIcon from './components/UiIcon.vue';
const route = useRoute(),
  router = useRouter();
const mobileMenu = ref(null);
const initials = computed(() => (session.user?.email || 'AT').slice(0, 2).toUpperCase());
watch(
  () => route.fullPath,
  () => mobileMenu.value?.close(),
);
async function logout() {
  try {
    await post('/api/auth/logout');
    session.user = null;
    router.replace('/login.html');
  } catch (error) {
    notify(error.message, 'error');
  }
}
function dismiss(id) {
  notifications.value = notifications.value.filter((item) => item.id !== id);
}
</script>

<template>
  <a href="#mainContent" class="skip-link">Pular para o conteúdo</a
  ><template v-if="route.meta.public"><RouterView /></template>
  <div v-else class="application-shell">
    <aside class="sidebar">
      <RouterLink class="brand" to="/dados.html" aria-label="Ativa, visão geral"
        ><BrandMark /><span>ativa<span class="brand-period">.</span></span></RouterLink
      >
      <p class="product-name">Controle de Campanhas</p>
      <NavLinks />
      <div class="sidebar-guide">
        <UiIcon name="ChartLine" :size="17" />
        <p>Uma boa leitura.<br /><strong>O próximo passo certo.</strong></p>
      </div>
      <div class="sidebar-account">
        <span class="avatar">{{ initials }}</span>
        <div>
          <strong :title="session.user?.email">{{ session.user?.email }}</strong
          ><span>{{ session.user?.role === 'admin' ? 'Administrador' : 'Consulta' }}</span>
        </div>
        <button class="sidebar-logout" aria-label="Sair" title="Sair da conta" @click="logout">
          <UiIcon name="LogOut" :size="17" />
        </button>
      </div>
    </aside>
    <div class="workspace">
      <header class="workspace-bar">
        <button
          class="icon-button mobile-menu-trigger"
          aria-label="Abrir navegação"
          @click="mobileMenu.showModal()"
        >
          <UiIcon name="Menu" />
        </button>
        <div class="breadcrumb">
          <span>{{ route.meta.section }}</span
          ><UiIcon name="ChevronRight" :size="13" /><strong>{{ route.meta.title }}</strong>
        </div>
        <span class="workspace-date"
          ><UiIcon name="CalendarDays" :size="15" />{{
            dateLabel(new Date().toISOString(), { year: 'numeric' })
          }}</span
        >
      </header>
      <main id="mainContent" class="main-content" tabindex="-1"><RouterView /></main>
      <footer class="workspace-footer">
        <span>Ativa · Controle de Campanhas</span><span>Horário de São Paulo</span>
      </footer>
    </div>
  </div>
  <dialog ref="mobileMenu" class="mobile-navigation">
    <div class="mobile-navigation-heading">
      <RouterLink class="brand" to="/dados.html"><BrandMark /><span>ativa.</span></RouterLink
      ><button class="sidebar-logout" aria-label="Fechar navegação" @click="mobileMenu.close()">
        <UiIcon name="X" />
      </button>
    </div>
    <NavLinks @navigate="mobileMenu.close()" /><button class="mobile-logout" @click="logout">
      <UiIcon name="LogOut" />Sair da conta
    </button>
  </dialog>
  <Teleport to="body"
    ><div class="toast-stack" aria-live="polite" aria-atomic="false">
      <div
        v-for="item in notifications"
        :key="item.id"
        class="toast"
        :class="`toast-${item.tone}`"
        role="status"
      >
        <UiIcon :name="item.tone === 'error' ? 'TriangleAlert' : 'CircleCheck'" /><span>{{
          item.message
        }}</span
        ><button class="icon-button" aria-label="Fechar aviso" @click="dismiss(item.id)">
          <UiIcon name="X" :size="15" />
        </button>
      </div></div
  ></Teleport>
</template>
