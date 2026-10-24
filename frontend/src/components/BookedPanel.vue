<script setup>
import { computed } from 'vue'
import { useStore } from 'vuex'
import { useI18n } from '@/i18n'
import OrderTicket from '@/components/OrderTicket.vue'

defineProps({ order: { type: Object, required: true } })
const { t } = useI18n()
const store = useStore()
const email = computed(() => store.state.auth.user?.email || '')
</script>

<template>
  <section class="booked" aria-live="polite">
    <h1>{{ t('checkout.paidTitle') }}</h1>
    <p class="lead">{{ t('checkout.paidBody', { email }) }}</p>
    <!-- the ticket feeds out of the slot, like a box-office printer -->
    <div class="slot" aria-hidden="true"></div>
    <div class="printed">
      <OrderTicket :order="order" readonly />
    </div>
    <RouterLink :to="{ name: 'tickets', query: { order: order.code } }" class="btn btn-primary">
      {{ t('checkout.viewTickets') }}
    </RouterLink>
  </section>
</template>

<style scoped>
.booked {
  display: grid;
  justify-items: start;
  gap: 14px;
}

h1 {
  font-size: var(--step-5);
}

.lead {
  font-size: var(--step-1);
  color: var(--asphalt-300);
}

.slot {
  width: 100%;
  height: 10px;
  margin-top: 10px;
  border-radius: 999px;
  background: #0d0e10;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.8), 0 1px 0 var(--asphalt-700);
}

.printed {
  width: 100%;
  margin-top: -12px;
  overflow: hidden;
}

.printed :deep(.ticket) {
  animation: feed 1.1s var(--ease-out) both;
}

@keyframes feed {
  from {
    transform: translateY(-100%);
  }
  to {
    transform: none;
  }
}
</style>
