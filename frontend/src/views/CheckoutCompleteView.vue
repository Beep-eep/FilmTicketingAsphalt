<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api'
import { errorMessage } from '@/api/client'
import { useI18n } from '@/i18n'
import BookedPanel from '@/components/BookedPanel.vue'

// Stripe sends the customer here after paying: /checkout/complete?session_id=cs_...
const { t } = useI18n()
const route = useRoute()

const order = ref(null)
const state = ref('confirming') // confirming | paid | pending | failed
const error = ref('')
let attempts = 0
let timer = null

async function confirm() {
  attempts++
  try {
    order.value = await api.confirmStripe(String(route.query.session_id || ''))
    if (['paid', 'partially_refunded'].includes(order.value.status)) {
      state.value = 'paid'
      return
    }
    state.value = 'pending'
  } catch (err) {
    error.value = errorMessage(err)
    state.value = 'failed'
    return
  }
  if (attempts < 15) timer = setTimeout(confirm, 2000)
}

onMounted(confirm)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <div class="page complete">
    <BookedPanel v-if="state === 'paid'" :order="order" />
    <div v-else class="waiting">
      <h1 v-if="state === 'confirming'">{{ t('checkout.confirming') }}</h1>
      <template v-else-if="state === 'pending'">
        <h1>{{ t('checkout.confirming') }}</h1>
        <p class="muted">{{ t('checkout.stillPending') }}</p>
      </template>
      <template v-else>
        <p class="notice notice-danger">{{ error || t('checkout.failed') }}</p>
        <p class="muted">{{ t('checkout.failed') }}</p>
      </template>
      <RouterLink to="/tickets" class="btn btn-ghost">{{ t('checkout.viewTickets') }}</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.complete {
  max-width: 760px;
  padding-top: 40px;
}

.waiting {
  display: grid;
  justify-items: start;
  gap: 14px;
}

h1 {
  font-size: var(--step-4);
}
</style>
