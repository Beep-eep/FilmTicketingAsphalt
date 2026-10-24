<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api'
import { errorMessage, fieldErrors } from '@/api/client'
import { useI18n } from '@/i18n'
import { toast } from '@/composables/useToast'
import AuthCard from '@/components/AuthCard.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const password = ref('')
const confirm = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  if (password.value !== confirm.value) {
    error.value = t('auth.passwordsDiffer')
    return
  }
  busy.value = true
  try {
    await api.resetPassword(String(route.query.uid || ''), String(route.query.token || ''), password.value)
    toast(t('auth.passwordSaved'), 'success')
    router.replace({ name: 'login' })
  } catch (err) {
    error.value = fieldErrors(err).new_password || errorMessage(err)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AuthCard :title="t('auth.resetTitle')">
    <form @submit.prevent="submit">
      <div class="field">
        <label for="password">{{ t('auth.newPassword') }}</label>
        <input id="password" v-model="password" class="input" type="password" autocomplete="new-password" minlength="8" required />
        <p class="field-hint">{{ t('auth.passwordHint') }}</p>
      </div>
      <div class="field">
        <label for="confirm">{{ t('auth.confirmPassword') }}</label>
        <input id="confirm" v-model="confirm" class="input" type="password" autocomplete="new-password" required />
      </div>
      <p v-if="error" class="notice notice-danger" role="alert">{{ error }}</p>
      <button type="submit" class="btn btn-primary btn-block" :disabled="busy || password.length < 8">{{ t('auth.savePassword') }}</button>
    </form>
  </AuthCard>
</template>
