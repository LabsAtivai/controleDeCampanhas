<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue';
import { api, post } from '../lib/api.js';
import { notify } from '../lib/notifications.js';
import { dateLabel, number, todaySP } from '../lib/metrics.js';
import PageHeading from '../components/PageHeading.vue';
import UiIcon from '../components/UiIcon.vue';
import DataNotice from '../components/DataNotice.vue';
import EmptyState from '../components/EmptyState.vue';
const status = ref({}),
  jobs = ref([]),
  integrations = ref([]),
  loading = ref(true),
  error = ref('');
const busy = ref(''),
  actionMode = ref('routine'),
  start = ref(todaySP(-1)),
  end = ref(todaySP(-1));
const logs = ref([]),
  cursor = ref(0),
  paused = ref(false),
  logJob = ref(''),
  expanded = ref(null);
const clients = ref([]),
  clientSearch = ref(''),
  selected = ref([]),
  selecting = ref(false),
  clientLoading = ref(false),
  clientError = ref('');
const labels = {
  queued: 'Na fila',
  running: 'Executando',
  completed: 'Concluído',
  partial: 'Parcial',
  failed: 'Falhou',
  interrupted: 'Interrompido',
};
const actions = {
  campanhas: 'Sincronização de campanhas',
  'dia-anterior': 'Coleta do dia anterior',
  custom: 'Coleta por período',
  planilhas: 'Atualização de planilhas',
  diario: 'Rotina diária',
};
const filteredClients = computed(() =>
  clients.value.filter((client) =>
    `${client.email} ${client.emailSnovio}`
      .toLowerCase()
      .includes(clientSearch.value.toLowerCase()),
  ),
);
const running = computed(() => jobs.value.filter((job) => job.status === 'running').length);
const queued = computed(() => jobs.value.filter((job) => job.status === 'queued').length);
let interval,
  polling = false;
async function poll() {
  if (polling || document.hidden) return;
  polling = true;
  try {
    const [current, history, configuration] = await Promise.all([
      api('/api/status'),
      api('/api/jobs'),
      api('/api/config/status'),
    ]);
    status.value = current;
    jobs.value = history;
    integrations.value = configuration.integrations;
    if (!paused.value) {
      const data = await api(
        `/api/logs?since=${cursor.value}${logJob.value ? '&job_id=' + encodeURIComponent(logJob.value) : ''}`,
      );
      logs.value = [...(data.reset ? [] : logs.value), ...(data.lines || [])].slice(-2000);
      cursor.value = data.cursor;
    }
    error.value = '';
  } catch (failure) {
    error.value = failure.message;
  } finally {
    polling = false;
    loading.value = false;
  }
}
async function run(action, body) {
  busy.value = action;
  try {
    await post(`/api/run/${action}`, body);
    notify('Execução adicionada à fila. Acompanhe o histórico abaixo.');
    await poll();
  } catch (failure) {
    notify(failure.message, 'error');
  } finally {
    busy.value = '';
  }
}
async function custom() {
  if (!start.value || !end.value) {
    notify('Preencha as duas datas.', 'error');
    return;
  }
  if (end.value < start.value) {
    notify('A data final deve ser igual ou posterior à inicial.', 'error');
    return;
  }
  await run('custom', { inicio: start.value, fim: end.value });
}
async function retry(job) {
  busy.value = job.id;
  try {
    await post(`/api/jobs/${encodeURIComponent(job.id)}/retry`);
    notify('Reprocessamento adicionado à fila.');
    await poll();
  } catch (failure) {
    notify(failure.message, 'error');
  } finally {
    busy.value = '';
  }
}
async function showClients() {
  selecting.value = !selecting.value;
  if (!selecting.value || clients.value.length) return;
  clientLoading.value = true;
  clientError.value = '';
  try {
    clients.value = await api('/api/clientes');
  } catch (failure) {
    clientError.value = failure.message;
  } finally {
    clientLoading.value = false;
  }
}
async function runSelected() {
  if (!selected.value.length) return;
  await run('campanhas-selecionadas', { ids: selected.value });
}
function changeLog() {
  logs.value = [];
  cursor.value = 0;
  poll();
}
onMounted(() => {
  poll();
  interval = setInterval(poll, 4000);
});
onBeforeUnmount(() => clearInterval(interval));
</script>

<template>
  <div class="page-stack">
    <PageHeading
      title="Operação de dados"
      subtitle="Coletas, publicações e histórico. Tudo em um só lugar."
      ><button class="button button-secondary" :disabled="loading" @click="poll">
        <UiIcon name="RefreshCw" :size="16" />Atualizar
      </button></PageHeading
    ><DataNotice :error="error" @retry="poll" />
    <section class="operation-status" aria-label="Estado das execuções">
      <div class="worker-state">
        <span
          class="status-dot"
          :class="status.worker_online ? 'dot-success' : 'dot-danger'"
        ></span>
        <div>
          <strong>{{
            status.worker_online
              ? 'Executor conectado'
              : loading
                ? 'Consultando executor…'
                : 'Executor indisponível'
          }}</strong>
          <p>
            {{
              status.worker_online
                ? 'Pronto para processar as execuções da equipe.'
                : 'Os trabalhos permanecem na fila até a conexão ser restabelecida.'
            }}
          </p>
        </div>
      </div>
      <dl>
        <div>
          <dt>Em execução</dt>
          <dd>{{ number(running) }}</dd>
        </div>
        <div>
          <dt>Na fila</dt>
          <dd>{{ number(queued) }}</dd>
        </div>
      </dl>
    </section>
    <div class="operations-layout">
      <section class="action-panel">
        <div class="section-toolbar">
          <div>
            <h2>Executar rotina</h2>
            <p>As solicitações entram na fila compartilhada.</p>
          </div>
        </div>
        <div class="segmented-control action-tabs" role="group" aria-label="Tipo de execução">
          <button
            :class="{ active: actionMode === 'routine' }"
            :aria-pressed="actionMode === 'routine'"
            @click="actionMode = 'routine'"
          >
            Rotinas</button
          ><button
            :class="{ active: actionMode === 'custom' }"
            :aria-pressed="actionMode === 'custom'"
            @click="actionMode = 'custom'"
          >
            Período personalizado
          </button>
        </div>
        <div v-if="actionMode === 'routine'" class="routine-list">
          <div>
            <span class="routine-icon"><UiIcon name="CalendarDays" /></span>
            <div>
              <h3>Dia anterior</h3>
              <p>Coletar o último dia fechado.</p>
            </div>
            <button
              class="button button-secondary"
              :disabled="Boolean(busy)"
              @click="run('dia-anterior')"
            >
              <UiIcon
                :name="busy === 'dia-anterior' ? 'LoaderCircle' : 'Play'"
                :class="{ spinning: busy === 'dia-anterior' }"
                :size="14"
              /><span>Extrair dia anterior</span>
            </button>
          </div>
          <div>
            <span class="routine-icon"><UiIcon name="RefreshCw" /></span>
            <div>
              <h3>Campanhas</h3>
              <p>Sincronizar o cadastro das contas ativas.</p>
            </div>
            <button
              class="button button-secondary"
              :disabled="Boolean(busy)"
              @click="run('campanhas')"
            >
              <UiIcon
                :name="busy === 'campanhas' ? 'LoaderCircle' : 'Play'"
                :class="{ spinning: busy === 'campanhas' }"
                :size="14"
              /><span>Extrair campanhas</span>
            </button>
          </div>
          <div>
            <span class="routine-icon"><UiIcon name="Workflow" /></span>
            <div>
              <h3>Planilhas de controle</h3>
              <p>Publicar os dados já coletados.</p>
            </div>
            <button
              class="button button-secondary"
              :disabled="Boolean(busy)"
              @click="run('planilhas')"
            >
              <UiIcon
                :name="busy === 'planilhas' ? 'LoaderCircle' : 'Play'"
                :class="{ spinning: busy === 'planilhas' }"
                :size="14"
              /><span>Atualizar planilhas</span>
            </button>
          </div>
        </div>
        <form v-else class="custom-run-form" @submit.prevent="custom">
          <div class="form-grid">
            <label
              >Data inicial<input v-model="start" type="date" :max="todaySP(-1)" required /></label
            ><label
              >Data final<input v-model="end" type="date" :min="start" :max="todaySP(-1)" required
            /></label>
          </div>
          <p class="field-hint">Até 31 dias, incluindo as duas datas. Somente dias fechados.</p>
          <button class="button button-primary" :disabled="Boolean(busy)" type="submit">
            <UiIcon name="Play" :size="15" />Enfileirar coleta do período
          </button>
        </form>
        <div class="selected-run">
          <button class="text-button" :aria-expanded="selecting" @click="showClients">
            <UiIcon name="Users" :size="15" />{{
              selecting ? 'Fechar seleção de contas' : 'Sincronizar contas selecionadas'
            }}<UiIcon name="ChevronDown" :size="13" />
          </button>
          <div v-if="selecting" class="client-picker">
            <label class="search-field"
              ><UiIcon name="Search" :size="16" /><input
                v-model="clientSearch"
                type="search"
                aria-label="Buscar contas para sincronizar"
                placeholder="Buscar conta" /></label
            ><DataNotice
              :error="clientError"
              @retry="
                clients = [];
                selecting = false;
                showClients();
              "
            />
            <p v-if="clientLoading" class="subtle-text">Carregando contas…</p>
            <div class="client-picker-list">
              <label v-for="client in filteredClients" :key="client.id"
                ><input v-model="selected" type="checkbox" :value="client.id" /><span
                  ><strong>{{ client.email }}</strong
                  ><small>{{ client.emailSnovio }}</small></span
                ></label
              >
            </div>
            <p v-if="!clientLoading && !clients.length" class="field-hint">
              Sincronize todas as campanhas primeiro para atualizar o cadastro de contas.
            </p>
            <button
              class="button button-primary"
              :disabled="!selected.length || Boolean(busy)"
              @click="runSelected"
            >
              Sincronizar {{ selected.length }} conta{{ selected.length === 1 ? '' : 's' }}
            </button>
          </div>
        </div>
      </section>
      <section class="integration-panel">
        <div class="section-toolbar">
          <div>
            <h2>Integrações</h2>
            <p>Configuração dos serviços conectados.</p>
          </div>
        </div>
        <div class="integration-list">
          <details v-for="item in integrations" :key="item.name">
            <summary>
              <UiIcon
                :name="item.configured ? 'CircleCheck' : 'CircleHelp'"
                :class="item.configured ? 'text-success' : 'text-muted'"
                :size="17"
              /><strong>{{ item.name }}</strong
              ><span :class="item.configured ? 'text-success' : 'text-muted'">{{
                item.configured ? 'Configurado' : 'Pendente'
              }}</span
              ><UiIcon name="ChevronDown" :size="13" />
            </summary>
            <p>{{ item.message }}</p>
          </details>
        </div>
      </section>
    </div>
    <section class="client-section">
      <div class="section-toolbar">
        <div>
          <h2>
            Histórico de execuções<span class="count-label">{{ number(jobs.length) }}</span>
          </h2>
          <p>Resultados, responsáveis e reprocessamento das solicitações.</p>
        </div>
        <span class="live-label"><span class="fresh-dot"></span>Atualização a cada 4 s</span>
      </div>
      <div id="jobHistory" class="data-panel">
        <div class="table-scroll">
          <table class="data-table jobs-table">
            <thead>
              <tr>
                <th scope="col">Execução</th>
                <th scope="col">Situação</th>
                <th scope="col">Responsável</th>
                <th scope="col">Solicitada em</th>
                <th scope="col">Ações</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="job in jobs" :key="job.id"
                ><tr>
                  <td>
                    <button
                      class="job-title"
                      :aria-expanded="expanded === job.id"
                      @click="expanded = expanded === job.id ? null : job.id"
                    >
                      <UiIcon
                        :name="expanded === job.id ? 'ChevronDown' : 'ChevronRight'"
                        :size="15"
                      />{{ actions[job.action] || job.action }}
                    </button>
                  </td>
                  <td>
                    <span class="job-status" :class="`job-${job.status}`"
                      ><span class="status-dot"></span>{{ labels[job.status] || job.status }}</span
                    >
                  </td>
                  <td>{{ job.actor }}</td>
                  <td class="date-cell">
                    {{ dateLabel(job.created_at, { hour: '2-digit', minute: '2-digit' }) }}
                  </td>
                  <td>
                    <button
                      v-if="['partial', 'failed', 'interrupted'].includes(job.status)"
                      class="text-button"
                      :disabled="Boolean(busy)"
                      @click="retry(job)"
                    >
                      <UiIcon name="RefreshCw" :size="13" />Reprocessar</button
                    ><span v-else class="subtle-text">—</span>
                  </td>
                </tr>
                <tr v-if="expanded === job.id" class="job-detail-row">
                  <td colspan="5">
                    <div class="job-detail">
                      <dl>
                        <div>
                          <dt>Início</dt>
                          <dd>
                            {{ dateLabel(job.started_at, { hour: '2-digit', minute: '2-digit' }) }}
                          </dd>
                        </div>
                        <div>
                          <dt>Conclusão</dt>
                          <dd>
                            {{ dateLabel(job.finished_at, { hour: '2-digit', minute: '2-digit' }) }}
                          </dd>
                        </div>
                      </dl>
                      <p v-if="job.error" class="field-error">{{ job.error }}</p>
                      <details v-if="job.result">
                        <summary>Ver resultado completo</summary>
                        <pre>{{ JSON.stringify(job.result, null, 2) }}</pre>
                      </details>
                      <p v-else class="subtle-text">
                        {{
                          job.status === 'queued'
                            ? 'Aguardando o executor.'
                            : 'O resultado será registrado ao final da execução.'
                        }}
                      </p>
                    </div>
                  </td>
                </tr></template
              >
            </tbody>
          </table>
        </div>
        <EmptyState
          v-if="!jobs.length && !loading"
          title="Nenhuma execução registrada"
          description="Escolha uma rotina acima para iniciar a primeira coleta."
          icon="Workflow"
        />
      </div>
    </section>
    <section class="log-panel">
      <div class="section-toolbar">
        <div>
          <h2>Log de execução</h2>
          <p>Mensagens registradas pelo executor, em ordem de chegada.</p>
        </div>
        <div class="log-tools">
          <select v-model="logJob" aria-label="Filtrar logs por execução" @change="changeLog">
            <option value="">Todas as execuções</option>
            <option v-for="job in jobs" :key="job.id" :value="job.id">
              {{ actions[job.action] || job.action }} ·
              {{ dateLabel(job.created_at, { hour: '2-digit', minute: '2-digit' }) }}
            </option></select
          ><button class="button button-secondary" :aria-pressed="paused" @click="paused = !paused">
            <UiIcon :name="paused ? 'Play' : 'Pause'" :size="14" />{{
              paused ? 'Retomar' : 'Pausar'
            }}
          </button>
        </div>
      </div>
      <pre class="log-output" tabindex="0" aria-label="Mensagens do executor">{{
        logs.length ? logs.join('\n') : 'As mensagens aparecerão aqui quando uma execução começar.'
      }}</pre>
    </section>
  </div>
</template>
