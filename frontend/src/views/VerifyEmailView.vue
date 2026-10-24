<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'
import { api } from '@/api'
import { errorMessage } from '@/api/client'
import { useI18n } from '@/i18n'
import { toast } from '@/composables/useToast'
import AuthCard from '@/components/AuthCard.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useStore()

const state = ref('working') // working | already | failed
const message = ref('')
const email = ref('')

onMounted(async () => {
  try {
    const result = await api.verifyEmail(String(route.query.uid || ''), String(route.query.token || ''))
    await store.dispatch('auth/adopt', result)
    toast(t('auth.verified'), 'success')
    router.replace('/')
  } catch (err) {
    if (err.response?.status === 409) state.value = 'already'
    else {
      state.value = 'failed'
      message.value = errorMessage(err)
    }
  }
})

async function resend() {
  try {
    const result = await api.resendVerification(email.value.trim())
    toast(result.detail)
  } catch (err) {
    toast(errorMessage(err), 'error')
  }
}
</script>

<template>
  <AuthCard v-if="state === 'working'" :title="t('auth.verifying')" />
  <AuthCard v-else-if="state === 'already'" :title="t('auth.alreadyVerified')">
    <RouterLink :to="{ name: 'login' }" class="btn btn-primary btn-block">{{ t('auth.signInTitle') }}</RouterLink>
  </AuthCard>
  <AuthCard v-else :title="t('auth.verifyFailed')" :lead="message">
    <form @submit.prevent="resend">
      <div class="field">
        <label for="email">{{ t('auth.email') }}</label>
        <input id="email" v-model="email" class="input" type="email" autocomplete="email" required />
      </div>
      <button type="submit" class="btn btn-primary btn-block" :disabled="!email">{{ t('auth.resend') }}</button>
    </form>
  </AuthCard>
</template>
