<script setup>
import { useI18n } from '@/i18n'
import MarqueeBoard from '@/components/MarqueeBoard.vue'

const { t } = useI18n()
</script>

<template>
  <div class="page nf">
    <MarqueeBoard text="404" small class="board" />
    <h1>{{ t('common.notFoundTitle') }}</h1>
    <p class="muted">{{ t('common.notFoundBody') }}</p>
    <RouterLink to="/" class="btn btn-primary">{{ t('common.home') }}</RouterLink>
  </div>
</template>

<style scoped>
.nf {
  display: grid;
  justify-items: start;
  gap: 14px;
  padding-top: 60px;
}

.board {
  width: 200px;
}

h1 {
  font-size: var(--step-4);
}
</style>
