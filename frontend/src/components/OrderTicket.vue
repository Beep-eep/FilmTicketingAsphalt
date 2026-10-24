<script setup>
import { computed } from 'vue'
import { useI18n } from '@/i18n'
import { config } from '@/composables/useConfig'
import { formatDate, formatMoney, formatTime } from '@/composables/format'
import { useCountdown } from '@/composables/useCountdown'
import PosterArt from '@/components/PosterArt.vue'
import QrCode from '@/components/QrCode.vue'

const props = defineProps({ order: { type: Object, required: true }, highlight: Boolean, readonly: Boolean })
const emit = defineEmits(['pay', 'cancel', 'refund', 'expired'])
const { t, filmTitle } = useI18n()

const film = computed(() => props.order.showtime.film)
const active = computed(() => props.order.tickets.filter((x) => ['paid', 'held'].includes(x.status)))
const shown = computed(() => (active.value.length ? active.value : props.order.tickets))
const seats = computed(() => shown.value.map((x) => x.seat_label).join(', '))
const paid = computed(() => ['paid', 'partially_refunded'].includes(props.order.status))
const qrValue = computed(() => `ASPHALT|${props.order.code}|${active.value.map((x) => x.seat_label).join(',')}`)
const { label: holdLeft } = useCountdown(
  () => (props.order.status === 'pending' ? props.order.hold_expires_at : null),
  () => emit('expired'),
)
</script>

<template>
  <article class="ticket" :class="[order.status, { highlight }]" :id="`order-${order.code}`">
    <div class="main">
      <PosterArt class="thumb" :film="film" />
      <div class="details">
        <p class="status">
          <span class="dot" aria-hidden="true"></span>
          {{ t(`tickets.status.${order.status}`) }}
          <span v-if="order.status === 'pending'" class="hold">{{ t('checkout.holdEnds') }} {{ holdLeft }}</span>
        </p>
        <h3>
          <RouterLink :to="{ name: 'film', params: { id: film.id } }">{{ filmTitle(film) }}</RouterLink>
        </h3>
        <p class="when">{{ formatDate(order.showtime.begin_time) }}, {{ formatTime(order.showtime.begin_time) }}</p>
        <dl class="facts">
          <div><dt>{{ t('tickets.room') }}</dt><dd>{{ order.showtime.room }}</dd></div>
          <div><dt>{{ t('tickets.seats') }}</dt><dd>{{ seats }}</dd></div>
          <div>
            <dt>{{ t('tickets.total') }}</dt>
            <dd>
              {{ formatMoney(order.amount_total, order.currency) }}
              <span v-if="Number(order.amount_refunded)" class="refunded">
                {{ t('tickets.refunded', { amount: formatMoney(order.amount_refunded, order.currency) }) }}
              </span>
            </dd>
          </div>
        </dl>
        <p v-if="order.note" class="note muted">{{ order.note }}</p>
        <div v-if="!readonly" class="actions">
          <button v-if="order.can_pay" type="button" class="btn btn-primary" @click="emit('pay', order)">
            {{ t('tickets.payNow') }}
          </button>
          <button v-if="order.can_cancel" type="button" class="btn btn-ghost" @click="emit('cancel', order)">
            {{ t('tickets.cancel') }}
          </button>
          <button v-if="order.can_refund" type="button" class="btn btn-danger" @click="emit('refund', order)">
            {{ t('tickets.refund') }}
          </button>
        </div>
      </div>
    </div>

    <div class="stub">
      <template v-if="paid && active.length">
        <QrCode :value="qrValue" :size="116" />
        <p class="door">{{ t('tickets.showAtDoor') }}</p>
      </template>
      <p class="code-label">{{ t('checkout.order') }}</p>
      <p class="code">{{ order.code }}</p>
      <p class="method muted">{{ t(`tickets.paidWith.${order.payment_provider}`) }}<template v-if="order.payment_provider === 'stripe' && config.stripe_mode === 'test'"> (test)</template></p>
    </div>
  </article>
</template>

<style scoped>
.ticket {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 190px;
  border-radius: var(--radius-m);
  background: var(--asphalt-850);
  border: 1px solid var(--asphalt-700);
  overflow: hidden;
}

.ticket.highlight {
  border-color: var(--sodium);
  box-shadow: 0 0 0 1px var(--sodium);
}

.ticket.cancelled,
.ticket.expired,
.ticket.refunded {
  opacity: 0.72;
}

.main {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 18px;
  padding: 18px;
}

.details {
  display: grid;
  gap: 6px;
  align-content: start;
}

.status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: var(--step--1);
  font-weight: 700;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--asphalt-500);
}

.paid .dot,
.partially_refunded .dot {
  background: var(--teal);
}

.pending .dot {
  background: var(--sodium);
}

.hold {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(240, 168, 48, 0.15);
  color: var(--sodium-bright);
  font-variant-numeric: tabular-nums;
}

h3 {
  font-size: var(--step-3);
  text-transform: uppercase;
}

h3 a {
  text-decoration: none;
}

h3 a:hover {
  text-decoration: underline;
}

.when {
  font-weight: 600;
}

.facts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 28px;
  margin: 6px 0 0;
}

.facts dt {
  color: var(--asphalt-300);
  font-size: var(--step--1);
}

.facts dd {
  margin: 0;
  font-weight: 700;
}

.refunded {
  display: block;
  color: var(--asphalt-300);
  font-weight: 500;
  font-size: var(--step--1);
}

.note {
  font-size: var(--step--1);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

/* the tear-off stub */
.stub {
  position: relative;
  display: grid;
  justify-items: center;
  align-content: center;
  gap: 4px;
  padding: 18px 14px;
  background: var(--marquee);
  color: var(--ink);
  text-align: center;
}

.stub::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  border-left: 2px dashed #b9bbb3;
}

.door {
  font-size: 0.72rem;
  color: #55585f;
}

.code-label {
  margin-top: 6px;
  font-size: 0.72rem;
  color: #55585f;
}

.code {
  font-family: var(--font-display);
  font-size: var(--step-2);
  font-weight: 800;
  letter-spacing: 0.04em;
  line-height: 1;
}

.method {
  font-size: 0.72rem;
  color: #55585f !important;
}

@media (max-width: 640px) {
  .ticket {
    grid-template-columns: 1fr;
  }

  .main {
    grid-template-columns: 64px minmax(0, 1fr);
  }

  .stub::before {
    left: 10px;
    right: 10px;
    top: 0;
    bottom: auto;
    border-left: 0;
    border-top: 2px dashed #b9bbb3;
  }
}
</style>
