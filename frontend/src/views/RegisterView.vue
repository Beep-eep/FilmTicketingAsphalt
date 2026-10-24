<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'
import { api } from '@/api'
import { errorMessage, fieldErrors } from '@/api/client'
import { useI18n } from '@/i18n'
import { config } from '@/composables/useConfig'
import { toast } from '@/composables/useToast'
import AuthCard from '@/components/AuthCard.vue'

const { t } = useI18n()
const store = useStore()
const route = useRoute()
const router = useRouter()

const form = ref({ username: '', email: '', password: '', confirm: '' })
const errors = ref({})
const error = ref('')
const busy = ref(false)
const sentTo = ref(route.query.resend ? '' : null) // null = form, string = "check your inbox"
const emailSent = ref(true)
const cooldown = ref(0)
let timer = null
onBeforeUnmount(() => clearInterval(timer))

const strength = computed(() => {
  const p = form.value.password
  if (p.length < 8) return 0
  let score = 1
  if (p.length >= 12) score++
  if (/[A-Z]/.test(p) && /[a-z]/.test(p) && /\d/.test(p)) score++
  if (/[^A-Za-z0-9]/.test(p)) score++
  return Math.min(score, 3)
})
const mismatch = computed(() => form.value.confirm && form.value.confirm !== form.value.password)

function startCooldown() {
  cooldown.value = 60
  clearInterval(timer)
  timer = setInterval(() => {
    cooldown.value -= 1
    if (cooldown.value <= 0) clearInterval(timer)
  }, 1000)
}

async function submit() {
  errors.value = {}
  error.value = ''
  if (mismatch.value) {
    errors.value = { confirm: t('auth.passwordsDiffer') }
    return
  }
  busy.value = true
  try {
    const result = await api.register({
      username: form.value.username.trim(),
      email: form.value.email.trim(),
      password: form.value.password,
    })
    if (result.email_verification_required) {
      sentTo.value = result.email
      emailSent.value = result.email_sent
      startCooldown()
    } else {
      store.dispatch('auth/adopt', result)
      toast(t('auth.signedIn', { name: result.user.username }), 'success')
      router.replace(typeof route.query.next === 'string' ? route.query.next : '/')
    }
  } catch (err) {
    errors.value = fieldErrors(err)
    if (!Object.keys(errors.value).length) error.value = errorMessage(err)
  } finally {
    busy.value = false
  }
}

const resendEmail = ref('')
async function resend() {
  const email = sentTo.value || resendEmail.value.trim()
  if (!email) return
  try {
    const result = await api.resendVerification(email)
    toast(result.detail)
    sentTo.value = email
    startCooldown()
  } catch (err) {
    toast(errorMessage(err), 'error')
  }
}
</script>

<template>
  <AuthCard v-if="sentTo === null" :title="t('auth.registerTitle')" :lead="t('auth.registerLead')">
    <form novalidate @submit.prevent="submit">
      <div class="field">
        <label for="username">{{ t('auth.username') }}</label>
        <input
          id="username"
          v-model="form.username"
          class="input"
          autocomplete="username"
          required
          minlength="3"
          :aria-invalid="Boolean(errors.username)"
          aria-describedby="username-hint"
        />
        <p v-if="errors.username" class="field-error">{{ errors.username }}</p>
        <p v-else id="username-hint" class="field-hint">{{ t('auth.usernameHint') }}</p>
      </div>
      <div class="field">
        <label for="email">{{ t('auth.email') }}</label>
        <input
          id="email"
          v-model="form.email"
          class="input"
          type="email"
          autocomplete="email"
          required
          :aria-invalid="Boolean(errors.email)"
          aria-describedby="email-hint"
        />
        <p v-if="errors.email" class="field-error">{{ errors.email }}</p>
        <p v-else id="email-hint" class="field-hint">{{ t('auth.emailHint') }}</p>
      </div>
      <div class="field">
        <label for="password">{{ t('auth.newPassword') }}</label>
        <input
          id="password"
          v-model="form.password"
          class="input"
          type="password"
          autocomplete="new-password"
          required
          minlength="8"
          :aria-invalid="Boolean(errors.password || errors.non_field_errors)"
          aria-describedby="password-hint"
        />
        <div class="meter" :data-level="strength" aria-hidden="true"><span></span><span></span><span></span></div>
        <p v-if="errors.password || errors.non_field_errors" class="field-error">
          {{ errors.password || errors.non_field_errors }}
        </p>
        <p v-else id="password-hint" class="field-hint">
          {{ form.password ? t('auth.strength')[strength] : t('auth.passwordHint') }}
        </p>
      </div>
      <div class="field">
        <label for="confirm">{{ t('auth.confirmPassword') }}</label>
        <input
          id="confirm"
          v-model="form.confirm"
          class="input"
          type="password"
          autocomplete="new-password"
          required
          :aria-invalid="Boolean(mismatch || errors.confirm)"
        />
        <p v-if="mismatch || errors.confirm" class="field-error">{{ t('auth.passwordsDiffer') }}</p>
      </div>
      <p v-if="error" class="notice notice-danger" role="alert">{{ error }}</p>
      <button
        type="submit"
        class="btn btn-primary btn-block"
        :disabled="busy || !form.username || !form.email || form.password.length < 8 || mismatch"
      >
        {{ t('auth.submitRegister') }}
      </button>
    </form>
    <p class="alt">
      {{ t('auth.haveAccount') }}
      <RouterLink :to="{ name: 'login', query: route.query.next ? { next: route.query.next } : {} }">{{ t('auth.signInTitle') }}</RouterLink>
    </p>
  </AuthCard>

  <AuthCard v-else :title="t('auth.checkInbox')">
    <div class="inbox" aria-hidden="true">
      <svg viewBox="0 0 64 48"><rect x="2" y="2" width="60" height="44" rx="6" /><path d="M4 6l28 22L60 6" /></svg>
    </div>
    <template v-if="sentTo">
      <p v-if="emailSent">{{ t('auth.checkInboxBody', { email: sentTo }) }}</p>
      <p v-else class="notice notice-danger">{{ t('auth.emailFailed') }}</p>
      <p v-if="config.email_delivery === 'console'" class="notice">{{ t('auth.consoleHint') }}</p>
    </template>
    <div v-else class="field">
      <label for="resend-email">{{ t('auth.email') }}</label>
      <input id="resend-email" v-model="resendEmail" class="input" type="email" autocomplete="email" />
    </div>
    <button type="button" class="btn btn-ghost btn-block" :disabled="cooldown > 0" @click="resend">
      {{ cooldown > 0 ? t('auth.resendIn', { s: cooldown }) : t('auth.resend') }}
    </button>
    <p class="alt"><RouterLink :to="{ name: 'login' }">{{ t('auth.signInTitle') }}</RouterLink></p>
  </AuthCard>
</template>

<style scoped>
.meter {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
}

.meter span {
  height: 4px;
  border-radius: 2px;
  background: var(--asphalt-700);
  transition: background-color 0.2s;
}

.meter[data-level='1'] span:nth-child(-n + 1),
.meter[data-level='2'] span:nth-child(-n + 2),
.meter[data-level='3'] span {
  background: var(--sodium);
}

.meter[data-level='3'] span {
  background: var(--teal);
}

.inbox svg {
  width: 72px;
  height: 54px;
  fill: none;
  stroke: var(--sodium);
  stroke-width: 3;
  stroke-linejoin: round;
}
</style>
