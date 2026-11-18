<script setup>
import { computed, nextTick, onMounted, ref } from 'vue';
import { api, post } from '../lib/api.js';
import { notify } from '../lib/notifications.js';
import { dateLabel, number } from '../lib/metrics.js';
import PageHeading from '../components/PageHeading.vue';
import UiIcon from '../components/UiIcon.vue';
import DataNotice from '../components/DataNotice.vue';
const board = ref({}),
  teams = ref([]),
  trash = ref('Excluídos'),
  loading = ref(true),
  error = ref(''),
  search = ref(''),
  dragging = ref(null),
  over = ref(''),
  confirming = ref(''),
  busy = ref('');
const boardRef = ref(null);
const columns = computed(() => [...teams.value, trash.value]);
const term = computed(() => search.value.trim().toLowerCase());
function visible(column) {
  const items = board.value[column] || [];
  return term.value
    ? items.filter((item) =>
        `${item.cliente} ${item.contas.join(' ')}`.toLowerCase().includes(term.value),
      )
    : items;
}
async function load() {
  loading.value = true;
  error.value = '';
  try {
    const result = await api('/api/kanban');
    board.value = result.colunas;
    teams.value = result.equipes;
    trash.value = result.excluidos;
  } catch (failure) {
    error.value = failure.message;
  } finally {
    loading.value = false;
  }
}
function find(cliente) {
  for (const column of columns.value) {
    const item = (board.value[column] || []).find((entry) => entry.cliente === cliente);
    if (item) return { item, column };
  }
  return null;
}
async function change(cliente, path, target, message) {
  const found = find(cliente);
  if (!found || busy.value) return;
  busy.value = cliente;
  const snapshot = JSON.stringify(board.value);
  if (target) {
    board.value[found.column] = board.value[found.column].filter((entry) => entry !== found.item);
    board.value[target] = [...(board.value[target] || []), found.item].sort((a, b) =>
      a.cliente.localeCompare(b.cliente, 'pt-BR'),
    );
  }
  try {
    const body = { contas: found.item.contas };
    if (path === 'mover') body.squad = target;
    await post(`/api/kanban/${path}`, body);
    notify(message);
    if (path === 'restaurar') await load();
  } catch (failure) {
    board.value = JSON.parse(snapshot);
    notify(failure.message, 'error');
  } finally {
    busy.value = '';
    confirming.value = '';
    // O cartão sai do lugar: devolve o foco ao quadro para não perdê-lo no teclado.
    await nextTick();
    boardRef.value?.focus();
  }
}
function exclude(cliente) {
  return change(
    cliente,
    'excluir',
    trash.value,
    `${cliente} excluído do painel. Dá para restaurar na coluna ${trash.value}.`,
  );
}
function restore(cliente) {
  return change(cliente, 'restaurar', null, `${cliente} restaurado.`);
}
function move(cliente, team) {
  const found = find(cliente);
  if (!found || found.column === team) return;
  if (team === trash.value) return exclude(cliente);
  return change(cliente, 'mover', team, `${cliente} movido para ${team}.`);
}
function onDrop(column) {
  const cliente = dragging.value;
  dragging.value = null;
  over.value = '';
  if (cliente) move(cliente, column);
}
function endDrag() {
  dragging.value = null;
  over.value = '';
}
onMounted(load);
</script>

<template>
  <div class="page-stack">
    <PageHeading
      title="Quadro de equipes"
      subtitle="Arraste os clientes entre as equipes. Excluir só oculta do painel e dá para restaurar."
    >
      <label class="search-field"
        ><UiIcon name="Search" :size="15" /><input
          v-model="search"
          type="search"
          placeholder="Buscar cliente ou conta"
          aria-label="Buscar cliente ou conta"
      /></label>
      <button class="button button-secondary" :disabled="loading" @click="load">
        <UiIcon name="RefreshCw" :size="16" />Atualizar
      </button>
    </PageHeading>
    <DataNotice :error="error" @retry="load" />
    <div
      v-if="!error"
      ref="boardRef"
      class="kanban-board"
      role="list"
      aria-label="Equipes"
      tabindex="-1"
    >
      <section
        v-for="column in columns"
        :key="column"
        class="kanban-column"
        :class="{ 'kanban-trash': column === trash, 'kanban-over': over === column }"
        role="listitem"
        :aria-label="`${column}, ${visible(column).length} clientes`"
        @dragover.prevent="over = column"
        @dragleave="over = over === column ? '' : over"
        @drop.prevent="onDrop(column)"
      >
        <header>
          <h2>{{ column }}</h2>
          <span class="count-label">{{ visible(column).length }}</span>
        </header>
        <ul class="kanban-list">
          <li
            v-for="item in visible(column)"
            :key="item.cliente"
            class="kanban-card"
            :class="{ 'kanban-dragging': dragging === item.cliente }"
            :draggable="busy === ''"
            @dragstart="dragging = item.cliente"
            @dragend="endDrag"
          >
            <div class="kanban-card-head">
              <UiIcon name="GripVertical" :size="14" class="kanban-grip" />
              <strong :title="item.contas.join(', ')">{{ item.cliente }}</strong>
            </div>
            <p>
              {{ item.contas.length }} {{ item.contas.length === 1 ? 'conta' : 'contas' }} ·
              {{ item.campanhas }} {{ item.campanhas === 1 ? 'campanha' : 'campanhas' }} ·
              {{ number(item.emailsSent) }} enviados
            </p>
            <p class="kanban-meta">Última coleta {{ dateLabel(item.ultimaColeta) }}</p>
            <div class="kanban-actions">
              <template v-if="column === trash">
                <button
                  class="button button-secondary"
                  :disabled="busy !== ''"
                  :aria-label="`Restaurar ${item.cliente}`"
                  @click="restore(item.cliente)"
                >
                  <UiIcon name="Undo2" :size="14" />Restaurar
                </button>
              </template>
              <template v-else>
                <select
                  :aria-label="`Mover ${item.cliente} para outra equipe`"
                  :value="column"
                  :disabled="busy !== ''"
                  @change="move(item.cliente, $event.target.value)"
                >
                  <option v-for="team in teams" :key="team" :value="team">{{ team }}</option>
                </select>
                <button
                  v-if="confirming !== item.cliente"
                  class="icon-button kanban-delete"
                  :disabled="busy !== ''"
                  :aria-label="`Excluir ${item.cliente}`"
                  title="Excluir do painel"
                  @click="confirming = item.cliente"
                >
                  <UiIcon name="Trash2" :size="15" />
                </button>
                <span v-else class="kanban-confirm">
                  <button
                    class="button kanban-danger"
                    :aria-label="`Confirmar exclusão de ${item.cliente}`"
                    @click="exclude(item.cliente)"
                  >
                    Confirmar exclusão
                  </button>
                  <button
                    class="button button-quiet"
                    :aria-label="`Cancelar exclusão de ${item.cliente}`"
                    @click="confirming = ''"
                  >
                    Cancelar
                  </button>
                </span>
              </template>
            </div>
          </li>
        </ul>
        <p v-if="!visible(column).length && !loading" class="kanban-empty">
          {{ column === trash ? 'Nenhum cliente excluído.' : 'Nenhum cliente nesta equipe.' }}
        </p>
      </section>
    </div>
  </div>
</template>
