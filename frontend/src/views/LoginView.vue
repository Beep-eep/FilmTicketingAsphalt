<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'
import { api } from '@/api'
import { errorCode, errorMessage } from '@/api/client'
import { useI18n } from '@/i18n'
import { toast } from '@/composables/useToast'
import AuthCard from '@/components/AuthCard.vue'

const { t } = useI18n()
const store = useStore()
const route = useRoute()
const router = useRouter()

const login = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')
const unverified = ref(false)
const next = computed(() => (typeof route.query.next === 'string' && route.query.next.startsWith('/') ? route.query.next : '/'))

async function submit() {
  busy.value = true
  error.value = ''
  unverified.value = false
  try {
    const user = await store.dispatch('auth/login', { login: login.value.trim(), password: password.value })
    toast(t('auth.signedIn', { name: user.username }), 'success')
    router.replace(next.value)
  } catch (err) {
    error.value = errorMessage(err)
    unverified.value = errorCode(err) === 'email_not_verified'
  } finally {
    busy.value = false
  }
}

async function resend() {
  if (!login.value.includes('@')) {
    router.push({ name: 'register', query: { resend: '1' } })
    return
  }
  try {
    const result = await api.resendVerification(login.value.trim())
    toast(result.detail)
  } catch (err) {
    toast(errorMessage(err), 'error')
  }
}
</script>

<template>
  <AuthCard :title="t('auth.signInTitle')" :lead="t('auth.signInLead')">
    <p v-if="route.query.expired" class="notice">{{ t('auth.sessionExpired') }}</p>
    <form novalidate @submit.prevent="submit">
      <div class="field">
        <label for="login">{{ t('auth.login') }}</label>
        <input id="login" v-model="login" class="input" autocomplete="username" required autofocus />
      </div>
      <div class="field">
        <label for="password">{{ t('auth.password') }}</label>
        <input id="password" v-model="password" class="input" type="password" autocomplete="current-password" required />
      </div>
      <div v-if="error" class="notice notice-danger" role="alert">
        <p>{{ error }}</p>
        <button v-if="unverified" type="button" class="btn-link" @click="resend">{{ t('auth.resend') }}</button>
      </div>
      <button type="submit" class="btn btn-primary btn-block" :disabled="busy || !login || !password">
        {{ t('auth.submitSignIn') }}
      </button>
    </form>
    <RouterLink :to="{ name: 'forgot-password' }" class="alt">{{ t('auth.forgot') }}</RouterLink>
    <p class="alt">
      {{ t('auth.noAccount') }}
      <RouterLink :to="{ name: 'register', query: route.query.next ? { next: route.query.next } : {} }">
        {{ t('auth.createOne') }}
      </RouterLink>
    </p>
  </AuthCard>
</template>
