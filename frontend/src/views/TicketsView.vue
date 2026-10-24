<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api'
import { errorMessage } from '@/api/client'
import { useI18n } from '@/i18n'
import { formatDateTime, formatMoney } from '@/composables/format'
import { toast } from '@/composables/useToast'
import BaseModal from '@/components/BaseModal.vue'
import OrderTicket from '@/components/OrderTicket.vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()

const orders = ref([])
const loading = ref(true)
const error = ref('')
const tab = ref('upcoming')
const refunding = ref(null)
const refundIds = ref([])
const busy = ref(false)

async function load() {
  try {
    orders.value = await api.orders()
    error.value = ''
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (route.query.cancelled) toast(t('tickets.signedOutCancelled'))
  await load()
  const code = route.query.order || route.query.cancelled
  if (code) {
    const target = orders.value.find((o) => o.code === code)
    if (target && !isUpcoming(target)) tab.value = 'past'
    await nextTick()
    document.getElementById(`order-${code}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
})

function isUpcoming(order) {
  const live = ['pending', 'paid', 'partially_refunded'].includes(order.status)
  return live && new Date(order.showtime.end_time) > new Date()
}

const upcoming = computed(() =>
  orders.value
    .filter(isUpcoming)
    .sort((a, b) => new Date(a.showtime.begin_time) - new Date(b.showtime.begin_time)),
)
const past = computed(() => orders.value.filter((o) => !isUpcoming(o)))
const list = computed(() => (tab.value === 'upcoming' ? upcoming.value : past.value))

async function pay(order) {
  busy.value = true
  try {
    const { checkout_url: url } = await api.checkout(order.code, locale.value)
    const target = new URL(url, window.location.origin)
    if (target.origin === window.location.origin) router.push(target.pathname + target.search)
    else window.location.assign(url)
  } catch (err) {
    toast(errorMessage(err), 'error')
    busy.value = false
    load()
  }
}

async function cancel(order) {
  try {
    await api.cancelOrder(order.code)
    toast(t('tickets.cancelled'))
    load()
  } catch (err) {
    toast(errorMessage(err), 'error')
  }
}

function openRefund(order) {
  refunding.value = order
  refundIds.value = order.tickets.filter((x) => x.status === 'paid').map((x) => x.id)
}

const refundAmount = computed(() => {
  if (!refunding.value) return 0
  return refunding.value.tickets
    .filter((x) => refundIds.value.includes(x.id))
    .reduce((sum, x) => sum + Number(x.price), 0)
})

async function confirmRefund() {
  busy.value = true
  try {
    const result = await api.refund(refunding.value.code, refundIds.value)
    toast(t('tickets.refunded', { amount: formatMoney(result.refunded, refunding.value.currency) }), 'success')
    refunding.value = null
    await load()
  } catch (err) {
    toast(errorMessage(err), 'error')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page tickets-page">
    <h1>{{ t('tickets.title') }}</h1>

    <div class="tabs" role="tablist">
      <button type="button" role="tab" :aria-selected="tab === 'upcoming'" @click="tab = 'upcoming'">
        {{ t('tickets.upcoming') }} <span class="n">{{ upcoming.length }}</span>
      </button>
      <button type="button" role="tab" :aria-selected="tab === 'past'" @click="tab = 'past'">
        {{ t('tickets.past') }} <span class="n">{{ past.length }}</span>
      </button>
    </div>

    <p v-if="error" class="notice notice-danger">{{ error }}</p>
    <div v-else-if="loading" class="list">
      <div v-for="n in 2" :key="n" class="skeleton" style="height: 190px"></div>
    </div>
    <div v-else-if="!list.length" class="empty">
      <p>{{ t('tickets.empty') }}</p>
      <RouterLink to="/" class="btn btn-primary">{{ t('tickets.emptyCta') }}</RouterLink>
    </div>
    <TransitionGroup v-else tag="div" name="list" class="list">
      <OrderTicket
        v-for="order in list"
        :key="order.code"
        :order="order"
        :highlight="order.code === route.query.order"
        @pay="pay"
        @cancel="cancel"
        @refund="openRefund"
        @expired="load"
      />
    </TransitionGroup>

    <BaseModal v-if="refunding" :title="t('tickets.refundTitle')" @close="refunding = null">
      <div class="refund">
        <p class="muted">{{ t('tickets.refundExplain', { time: formatDateTime(refunding.refund_deadline) }) }}</p>
        <p v-if="refunding.payment_provider !== 'stripe'" class="notice">{{ t('tickets.refundDemo') }}</p>
        <fieldset>
          <legend>{{ t('tickets.refundChoose') }}</legend>
          <label v-for="ticket in refunding.tickets.filter((x) => x.status === 'paid')" :key="ticket.id" class="pick">
            <input v-model="refundIds" type="checkbox" :value="ticket.id" />
            <span class="seat">{{ ticket.seat_label }}</span>
            <span>{{ formatMoney(ticket.price, refunding.currency) }}</span>
          </label>
        </fieldset>
        <div class="refund-actions">
          <button type="button" class="btn btn-ghost" @click="refunding = null">{{ t('common.cancel') }}</button>
          <button type="button" class="btn btn-danger" :disabled="!refundIds.length || busy" @click="confirmRefund">
            {{ t('tickets.refundConfirm', { amount: formatMoney(refundAmount, refunding.currency) }) }}
          </button>
        </div>
      </div>
    </BaseModal>
  </div>
</template>

<style scoped>
.tickets-page {
  display: grid;
  gap: 20px;
  padding-top: 32px;
}

h1 {
  font-size: var(--step-5);
}

.tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--asphalt-700);
}

.tabs button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 0 14px;
  border: 0;
  border-bottom: 3px solid transparent;
  background: none;
  color: var(--asphalt-300);
  font-weight: 700;
  cursor: pointer;
}

.tabs button[aria-selected='true'] {
  border-bottom-color: var(--sodium);
  color: var(--chalk);
}

.n {
  min-width: 22px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--asphalt-700);
  font-size: var(--step--1);
}

.list {
  display: grid;
  gap: 16px;
}

.list-move,
.list-enter-active,
.list-leave-active {
  transition: opacity 0.25s, transform 0.25s var(--ease-out);
}

.list-enter-from,
.list-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.empty {
  display: grid;
  justify-items: start;
  gap: 14px;
  padding: 32px 0;
}

.refund {
  display: grid;
  gap: 16px;
}

fieldset {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  border: 0;
}

legend {
  margin-bottom: 8px;
  font-weight: 700;
}

.pick {
  display: grid;
  grid-template-columns: auto 60px 1fr;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--asphalt-700);
  border-radius: var(--radius-s);
  cursor: pointer;
}

.pick input {
  width: 18px;
  height: 18px;
  accent-color: var(--sodium);
}

.seat {
  font-family: var(--font-display);
  font-size: var(--step-2);
  font-weight: 800;
}

.refund-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
