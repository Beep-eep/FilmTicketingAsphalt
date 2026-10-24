<script setup>
import { ref } from 'vue'
import { api } from '@/api'
import { errorMessage } from '@/api/client'
import { useI18n } from '@/i18n'
import { config } from '@/composables/useConfig'
import AuthCard from '@/components/AuthCard.vue'

const { t } = useI18n()
const email = ref('')
const sent = ref(false)
const error = ref('')
const busy = ref(false)

async function submit() {
  busy.value = true
  error.value = ''
  try {
    await api.requestPasswordReset(email.value.trim())
    sent.value = true
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AuthCard :title="t('auth.forgotTitle')" :lead="sent ? '' : t('auth.forgotLead')">
    <template v-if="sent">
      <p>{{ t('auth.resetSent') }}</p>
      <p v-if="config.email_delivery === 'console'" class="notice">{{ t('auth.consoleHint') }}</p>
    </template>
    <form v-else @submit.prevent="submit">
      <div class="field">
        <label for="email">{{ t('auth.email') }}</label>
        <input id="email" v-model="email" class="input" type="email" autocomplete="email" required autofocus />
      </div>
      <p v-if="error" class="notice notice-danger" role="alert">{{ error }}</p>
      <button type="submit" class="btn btn-primary btn-block" :disabled="busy || !email">{{ t('auth.sendReset') }}</button>
    </form>
    <p class="alt"><RouterLink :to="{ name: 'login' }">{{ t('auth.signInTitle') }}</RouterLink></p>
  </AuthCard>
</template>
