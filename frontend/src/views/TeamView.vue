<script setup>
import { onMounted, reactive, ref } from 'vue';
import { api, post } from '../lib/api.js';
import { notify } from '../lib/notifications.js';
import { dateLabel } from '../lib/metrics.js';
import PageHeading from '../components/PageHeading.vue';
import UiIcon from '../components/UiIcon.vue';
import DataNotice from '../components/DataNotice.vue';
import EmptyState from '../components/EmptyState.vue';
const users = ref([]),
  audit = ref([]),
  error = ref(''),
  loading = ref(true),
  saving = ref(false),
  editing = ref(false),
  visiblePassword = ref(false);
const form = reactive({ email: '', password: '', role: 'viewer', active: true });
const eventLabels = {
  'auth.login': 'Entrou no sistema',
  'auth.logout': 'Saiu do sistema',
  'job.queued': 'Adicionou uma execução à fila',
  'user.saved': 'Salvou um acesso',
  'user.updated': 'Atualizou um acesso',
};
async function load() {
  loading.value = true;
  error.value = '';
  try {
    [users.value, audit.value] = await Promise.all([api('/api/users'), api('/api/audit')]);
  } catch (failure) {
    error.value = failure.message;
  } finally {
    loading.value = false;
  }
}
function edit(user) {
  form.email = user.email;
  form.password = '';
  form.role = user.role;
  form.active = user.active;
  editing.value = true;
  document.getElementById('userEmail')?.focus();
}
function reset() {
  Object.assign(form, { email: '', password: '', role: 'viewer', active: true });
  editing.value = false;
  visiblePassword.value = false;
}
async function save() {
  saving.value = true;
  try {
    await post('/api/users', { ...form });
    notify('Acesso salvo. As sessões anteriores dessa conta foram encerradas.');
    reset();
    await load();
  } catch (failure) {
    notify(failure.message, 'error');
  } finally {
    saving.value = false;
  }
}
onMounted(load);
</script>

<template>
  <div class="page-stack">
    <PageHeading
      title="Equipe e acessos"
      subtitle="As pessoas certas, com o acesso certo ao trabalho."
      ><button class="button button-secondary" :disabled="loading" @click="load">
        <UiIcon name="RefreshCw" :size="16" />Atualizar
      </button></PageHeading
    ><DataNotice :error="error" @retry="load" />
    <div class="team-layout">
      <section class="client-section">
        <div class="section-toolbar">
          <div>
            <h2>
              Pessoas da equipe<span class="count-label">{{ users.length }}</span>
            </h2>
            <p>Administradores operam o sistema. Consultas acompanham os dados.</p>
          </div>
        </div>
        <div class="data-panel">
          <div class="table-scroll">
            <table class="data-table team-table">
              <thead>
                <tr>
                  <th scope="col">Pessoa</th>
                  <th scope="col">Permissão</th>
                  <th scope="col">Situação</th>
                  <th scope="col"><span class="sr-only">Editar acesso</span></th>
                </tr>
              </thead>
              <tbody id="users">
                <tr v-for="user in users" :key="user.id">
                  <td>
                    <div class="client-cell">
                      <span class="client-monogram" aria-hidden="true">{{
                        user.email.slice(0, 2).toUpperCase()
                      }}</span
                      ><span class="user-email">{{ user.email }}</span>
                    </div>
                  </td>
                  <td>
                    <span class="role-label"
                      ><UiIcon :name="user.role === 'admin' ? 'ShieldCheck' : 'Eye'" :size="14" />{{
                        user.role === 'admin' ? 'Administrador' : 'Consulta'
                      }}</span
                    >
                  </td>
                  <td>
                    <span
                      class="status-badge"
                      :class="user.active ? 'tone-success' : 'tone-neutral'"
                      ><span class="status-dot"></span
                      >{{ user.active ? 'Ativo' : 'Desativado' }}</span
                    >
                  </td>
                  <td>
                    <button
                      class="text-button"
                      :aria-label="`Editar acesso de ${user.email}`"
                      @click="edit(user)"
                    >
                      Editar
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <EmptyState
            v-if="!users.length && !loading"
            title="Nenhum acesso encontrado"
            description="Cadastre uma pessoa usando o formulário ao lado."
            icon="Users"
          />
        </div>
      </section>
      <section class="user-form-panel">
        <div class="section-toolbar">
          <div>
            <h2>{{ editing ? 'Editar acesso' : 'Adicionar pessoa' }}</h2>
            <p>
              {{
                editing
                  ? 'As alterações encerram as sessões anteriores.'
                  : 'Crie um acesso individual para alguém da equipe.'
              }}
            </p>
          </div>
        </div>
        <form class="user-form" @submit.prevent="save">
          <label for="userEmail"
            >E-mail<input
              id="userEmail"
              v-model="form.email"
              type="email"
              required
              maxlength="255"
              autocomplete="off"
              placeholder="pessoa@empresa.com" /></label
          ><label for="userPassword"
            >{{ editing ? 'Nova senha' : 'Senha inicial' }}
            <div class="password-input">
              <input
                id="userPassword"
                v-model="form.password"
                :type="visiblePassword ? 'text' : 'password'"
                required
                minlength="12"
                maxlength="128"
                autocomplete="new-password"
                placeholder="Mínimo de 12 caracteres"
              /><button
                type="button"
                class="icon-button"
                :aria-label="visiblePassword ? 'Ocultar senha' : 'Mostrar senha'"
                @click="visiblePassword = !visiblePassword"
              >
                <UiIcon :name="visiblePassword ? 'EyeOff' : 'Eye'" :size="17" />
              </button></div></label
          ><label for="userRole"
            >Permissão<select id="userRole" v-model="form.role">
              <option value="viewer">Consulta</option>
              <option value="admin">Administrador</option>
            </select></label
          ><label for="userActive"
            >Situação<select id="userActive" v-model="form.active">
              <option :value="true">Ativo</option>
              <option :value="false">Desativado</option>
            </select></label
          >
          <p class="field-hint">
            Consulta permite acessar métricas e análises. Administrador também gerencia rotinas e
            pessoas.
          </p>
          <button class="button button-primary" type="submit" :disabled="saving">
            <UiIcon
              :name="saving ? 'LoaderCircle' : 'Check'"
              :class="{ spinning: saving }"
              :size="16"
            />{{ saving ? 'Salvando…' : 'Salvar acesso' }}</button
          ><button v-if="editing" class="button button-quiet" type="button" @click="reset">
            Cancelar edição
          </button>
        </form>
      </section>
    </div>
    <section class="audit-panel">
      <div class="section-toolbar">
        <div>
          <h2>Atividade recente</h2>
          <p>Um registro das ações realizadas no sistema.</p>
        </div>
      </div>
      <ol class="audit-list">
        <li v-for="event in audit.slice(0, 50)" :key="event.id">
          <span class="audit-marker"
            ><UiIcon
              :name="
                event.action.startsWith('auth.')
                  ? 'ShieldCheck'
                  : event.action.startsWith('job.')
                    ? 'Workflow'
                    : 'Users'
              "
              :size="15"
          /></span>
          <div>
            <strong>{{ eventLabels[event.action] || event.action }}</strong
            ><span>{{ event.actor }}</span>
          </div>
          <time>{{ dateLabel(event.createdAt, { hour: '2-digit', minute: '2-digit' }) }}</time>
        </li>
      </ol>
      <EmptyState
        v-if="!audit.length && !loading"
        title="Sem atividades registradas"
        description="As ações da equipe serão exibidas aqui."
        icon="Activity"
      />
    </section>
  </div>
</template>
