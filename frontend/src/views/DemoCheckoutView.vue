<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { errorMessage } from '@/api/client'
import { useI18n } from '@/i18n'
import { formatDate, formatMoney, formatTime } from '@/composables/format'
import { useCountdown } from '@/composables/useCountdown'
import { toast } from '@/composables/useToast'
import BookedPanel from '@/components/BookedPanel.vue'

const props = defineProps({ code: { type: String, required: true } })
const { t, filmTitle } = useI18n()
const router = useRouter()

const order = ref(null)
const error = ref('')
const busy = ref(false)

onMounted(async () => {
  try {
    order.value = await api.order(props.code)
  } catch (err) {
    error.value = errorMessage(err)
  }
})

const { label: holdLeft, seconds } = useCountdown(() => order.value?.hold_expires_at)
const seats = computed(() => order.value?.tickets.filter((x) => x.status === 'held').map((x) => x.seat_label).join(', '))

async function pay(outcome) {
  busy.value = true
  try {
    order.value = await api.demoPay(props.code, outcome)
  } catch (err) {
    toast(errorMessage(err), 'error')
    if (err.response?.status === 409) router.push({ name: 'seats', params: { id: order.value.showtime.id } })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page checkout">
    <p v-if="error" class="notice notice-danger">{{ error }}</p>

    <BookedPanel v-else-if="order && order.status === 'paid'" :order="order" />

    <template v-else-if="order">
      <div v-if="order.status !== 'pending' || !seconds" class="notice notice-danger">
        <p>{{ t('checkout.expired') }}</p>
        <RouterLink :to="{ name: 'seats', params: { id: order.showtime.id } }" class="btn btn-ghost">
          {{ t('seats.pick') }}
        </RouterLink>
      </div>

      <div v-else class="pay-box">
        <h1>{{ t('checkout.demoTitle') }}</h1>
        <p class="notice">{{ t('checkout.demoExplain') }}</p>

        <dl class="summary">
          <div><dt>{{ t('checkout.order') }}</dt><dd>{{ order.code }}</dd></div>
          <div><dt>{{ t('checkout.film') }}</dt><dd>{{ filmTitle(order.showtime.film) }}</dd></div>
          <div><dt>{{ t('checkout.when') }}</dt><dd>{{ formatDate(order.showtime.begin_time) }}, {{ formatTime(order.showtime.begin_time) }}, {{ order.showtime.room }}</dd></div>
          <div><dt>{{ t('tickets.seats') }}</dt><dd>{{ seats }}</dd></div>
          <div class="total"><dt>{{ t('seats.total') }}</dt><dd>{{ formatMoney(order.amount_total, order.currency) }}</dd></div>
        </dl>

        <p class="hold">{{ t('checkout.holdEnds') }} <strong>{{ holdLeft }}</strong></p>

        <button type="button" class="btn btn-primary btn-block" :disabled="busy" @click="pay('success')">
          {{ t('checkout.pay', { amount: formatMoney(order.amount_total, order.currency) }) }}
        </button>
        <button type="button" class="btn btn-ghost btn-block" :disabled="busy" @click="pay('decline')">
          {{ t('checkout.decline') }}
        </button>
      </div>
    </template>

    <div v-else class="skeleton" style="height: 360px"></div>
  </div>
</template>

<style scoped>
.checkout {
  max-width: 760px;
  padding-top: 40px;
}

.pay-box {
  display: grid;
  gap: 16px;
  max-width: 520px;
}

h1 {
  font-size: var(--step-5);
}

.summary {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 18px;
  border-radius: var(--radius-m);
  background: var(--asphalt-850);
  border: 1px solid var(--asphalt-700);
}

.summary div {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 12px;
}

.summary dt {
  color: var(--asphalt-300);
}

.summary dd {
  margin: 0;
  font-weight: 600;
}

.summary .total {
  padding-top: 10px;
  border-top: 1px solid var(--asphalt-700);
}

.summary .total dd {
  font-family: var(--font-display);
  font-size: var(--step-3);
  font-weight: 800;
  line-height: 1;
}

.hold strong {
  color: var(--sodium-bright);
  font-variant-numeric: tabular-nums;
}
</style>
