<script setup>
import { computed } from 'vue'
import { useI18n } from '@/i18n'
import { upcomingDays } from '@/composables/format'

const props = defineProps({
  modelValue: { type: String, default: '' },
  days: { type: Number, default: 7 },
  allowAny: Boolean,
  available: { type: Array, default: null }, // dates that have screenings; others look dimmed
})
const emit = defineEmits(['update:modelValue'])
const { t, locale } = useI18n()

const list = computed(() => {
  void locale.value // re-render labels when the language changes
  return upcomingDays(props.days)
})
</script>

<template>
  <div class="strip" role="group">
    <button
      v-if="allowAny"
      type="button"
      class="day any"
      :aria-pressed="modelValue === ''"
      @click="emit('update:modelValue', '')"
    >
      <span class="label">{{ t('home.anyDay') }}</span>
    </button>
    <button
      v-for="d in list"
      :key="d.key"
      type="button"
      class="day"
      :class="{ empty: available && !available.includes(d.key) }"
      :aria-pressed="modelValue === d.key"
      @click="emit('update:modelValue', d.key)"
    >
      <span class="label">{{ d.label }}</span>
      <span class="num">{{ d.day }}</span>
      <span class="month">{{ d.month }}</span>
    </button>
  </div>
</template>

<style scoped>
.strip {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 4px 2px 8px;
  scrollbar-width: thin;
}

.day {
  display: grid;
  justify-items: center;
  align-content: center;
  min-width: 68px;
  min-height: 76px;
  padding: 8px 10px;
  border: 1px solid var(--asphalt-700);
  border-radius: var(--radius-m);
  background: var(--asphalt-900);
  color: var(--asphalt-300);
  cursor: pointer;
  flex-shrink: 0;
  transition: background-color 0.15s, color 0.15s, border-color 0.15s;
}

.day:hover {
  border-color: var(--asphalt-500);
  color: var(--chalk);
}

.day[aria-pressed='true'] {
  border-color: var(--sodium);
  background: var(--sodium);
  color: var(--ink);
}

.day.empty:not([aria-pressed='true']) {
  opacity: 0.45;
}

.label {
  font-size: var(--step--1);
  font-weight: 600;
  white-space: nowrap;
}

.num {
  font-family: var(--font-display);
  font-size: var(--step-3);
  font-weight: 800;
  line-height: 1;
}

.month {
  font-size: 0.72rem;
  font-weight: 600;
}

.any {
  min-width: 92px;
}
</style>
