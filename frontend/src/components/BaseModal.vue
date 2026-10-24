<script setup>
import { onMounted, ref } from 'vue'
import { t } from '@/i18n'

defineProps({ title: { type: String, required: true }, wide: Boolean })
const emit = defineEmits(['close'])
const dialog = ref(null)

onMounted(() => dialog.value.showModal())

function onBackdrop(event) {
  if (event.target === dialog.value) emit('close')
}
</script>

<template>
  <dialog ref="dialog" class="modal" :class="{ wide }" @cancel.prevent="emit('close')" @click="onBackdrop">
    <div class="body">
      <header class="head">
        <h2>{{ title }}</h2>
        <button type="button" class="x" :aria-label="t('common.close')" @click="emit('close')">
          <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5l10 10M15 5 5 15" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></svg>
        </button>
      </header>
      <slot />
    </div>
  </dialog>
</template>

<style scoped>
.modal {
  width: min(92vw, 460px);
  max-height: 88vh;
  padding: 0;
  border: 1px solid var(--asphalt-700);
  border-radius: var(--radius-l);
  background: var(--asphalt-850);
  color: var(--chalk);
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6);
}

.modal.wide {
  width: min(94vw, 880px);
}

.modal::backdrop {
  background: rgba(10, 11, 13, 0.75);
}

.body {
  padding: 22px 24px 24px;
}

.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.head h2 {
  font-size: var(--step-3);
}

.x {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 50%;
  background: var(--asphalt-700);
  cursor: pointer;
  flex-shrink: 0;
}

.x svg {
  width: 18px;
  height: 18px;
}

.x:hover {
  background: var(--asphalt-600);
}
</style>
