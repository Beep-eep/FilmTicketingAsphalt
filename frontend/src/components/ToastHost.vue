<script setup>
import { dismiss, toasts } from '@/composables/useToast'
</script>

<template>
  <div class="toasts" role="status" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="item in toasts" :key="item.id" class="toast" :class="item.kind" @click="dismiss(item.id)">
        {{ item.message }}
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toasts {
  position: fixed;
  left: 50%;
  bottom: 24px;
  z-index: 90;
  display: grid;
  gap: 8px;
  width: min(92vw, 440px);
  transform: translateX(-50%);
  pointer-events: none;
}

.toast {
  padding: 12px 16px;
  border-left: 4px solid var(--sodium);
  border-radius: var(--radius-s);
  background: var(--marquee);
  color: var(--ink);
  font-weight: 600;
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.5);
  pointer-events: auto;
  cursor: pointer;
}

.toast.error {
  border-left-color: var(--velvet-bright);
}

.toast.success {
  border-left-color: var(--teal-deep);
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s, transform 0.2s var(--ease-out);
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
</style>
