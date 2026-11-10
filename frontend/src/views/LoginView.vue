<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { post, loadSession, session } from '../lib/api.js';
import BrandMark from '../components/BrandMark.vue';
import UiIcon from '../components/UiIcon.vue';
const router = useRouter();
const email = ref(''),
  password = ref(''),
  visible = ref(false),
  loading = ref(false),
  error = ref('');
async function login() {
  loading.value = true;
  error.value = '';
  try {
    await post('/api/auth/login', { email: email.value, password: password.value });
    await loadSession();
    if (session.user) router.replace('/dados.html');
    else error.value = session.error || 'Não foi possível iniciar a sessão. Tente novamente.';
  } catch (failure) {
    error.value = failure.message;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main id="mainContent" class="login-layout">
    <section class="login-story">
      <a class="brand" href="/login.html" aria-label="Ativa"
        ><BrandMark /><span>ativa<span class="brand-period">.</span></span></a
      >
      <div class="login-story-content">
        <h1>
          Uma visão clara.<br />
          Um próximo passo<br />
          mais preciso.
        </h1>
        <p>
          Campanhas, resultados e avanços.<br />
          O contexto que conecta os números à sua rotina.
        </p>
        <div class="login-signal-board">
          <span>O estado de cada cliente, à vista.</span>
          <div>
            <span class="signal-item"><i class="dot-success"></i>Em dia</span
            ><span class="signal-item"><i class="dot-warning"></i>Atenção</span
            ><span class="signal-item"><i class="dot-danger"></i>Sem avanço</span>
          </div>
        </div>
      </div>
      <footer>Controle de Campanhas<span>Feito para o trabalho da equipe.</span></footer>
    </section>
    <section class="login-form-area">
      <div class="login-form-wrap">
        <span class="login-lock"><UiIcon name="ShieldCheck" :size="23" /></span>
        <h2>Bom ter você por aqui.</h2>
        <p>Entre para acompanhar suas campanhas.</p>
        <form class="login-form" @submit.prevent="login">
          <label for="email"
            >E-mail<input
              id="email"
              v-model="email"
              type="email"
              required
              autocomplete="username"
              maxlength="255"
              placeholder="seu.email@empresa.com" /></label
          ><label for="password"
            >Senha
            <div class="password-input">
              <input
                id="password"
                v-model="password"
                :type="visible ? 'text' : 'password'"
                required
                autocomplete="current-password"
                maxlength="128"
                placeholder="Digite sua senha"
              /><button
                class="icon-button"
                type="button"
                :aria-label="visible ? 'Ocultar senha' : 'Mostrar senha'"
                @click="visible = !visible"
              >
                <UiIcon :name="visible ? 'EyeOff' : 'Eye'" :size="18" />
              </button></div
          ></label>
          <div v-if="error || session.error" class="login-error" role="alert">
            <UiIcon name="TriangleAlert" :size="17" />
            <p>{{ error || session.error }}</p>
          </div>
          <button class="button button-primary login-submit" type="submit" :disabled="loading">
            <UiIcon v-if="loading" name="LoaderCircle" class="spinning" :size="17" />{{
              loading ? 'Entrando…' : 'Entrar'
            }}<UiIcon v-if="!loading" name="ArrowUpRight" :size="17" />
          </button>
        </form>
        <p class="login-help">
          Ainda não tem acesso?<br />Solicite sua conta ao administrador da equipe.
        </p>
      </div>
      <footer class="login-footer">
        <UiIcon name="ShieldCheck" :size="14" />Acesso individual e restrito à equipe.
      </footer>
    </section>
  </main>
</template>
