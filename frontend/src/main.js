import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import '@fontsource-variable/public-sans';
import App from './App.vue';
import './styles.css';
import { loadSession, session } from './lib/api.js';
import DashboardView from './views/DashboardView.vue';
import AnalysisView from './views/AnalysisView.vue';
import OperationsView from './views/OperationsView.vue';
import TeamView from './views/TeamView.vue';
import LoginView from './views/LoginView.vue';

localStorage.removeItem('painel_api_token');
localStorage.removeItem('painel_api_url');
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dados.html' },
    {
      path: '/dados.html',
      component: DashboardView,
      meta: { title: 'Visão geral', section: 'Acompanhamento' },
    },
    {
      path: '/analise.html',
      component: AnalysisView,
      meta: { title: 'Análise por cliente', section: 'Acompanhamento' },
    },
    {
      path: '/index.html',
      component: OperationsView,
      meta: { title: 'Operação de dados', section: 'Administração', admin: true },
    },
    {
      path: '/equipe.html',
      component: TeamView,
      meta: { title: 'Equipe e acessos', section: 'Administração', admin: true },
    },
    { path: '/login.html', component: LoginView, meta: { title: 'Entrar', public: true } },
    { path: '/:pathMatch(.*)*', redirect: '/dados.html' },
  ],
});
let initialized = false;
router.beforeEach(async (to) => {
  if (!initialized) {
    await loadSession();
    initialized = true;
  }
  if (!to.meta.public && !session.user) return '/login.html';
  if (to.meta.public && session.user) return '/dados.html';
  if (to.meta.admin && session.user?.role !== 'admin') return '/dados.html';
  document.title = `${to.meta.title} · Ativa`;
});
window.addEventListener('ativa:session-expired', () => router.replace('/login.html'));
router.afterEach(() => {
  window.scrollTo({ top: 0, behavior: 'instant' });
});
createApp(App).use(router).mount('#app');
