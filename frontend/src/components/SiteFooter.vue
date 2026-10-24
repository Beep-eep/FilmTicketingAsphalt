<script setup>
import { useI18n } from '@/i18n'
import { config } from '@/composables/useConfig'

const { t } = useI18n()
</script>

<template>
  <footer class="footer">
    <div class="page inner">
      <p class="tagline">{{ t('footer.tagline') }}</p>
      <p v-if="config.payment_provider === 'demo'" class="muted">{{ t('footer.demoPayments') }}</p>
      <p v-else-if="config.stripe_mode === 'test'" class="muted">{{ t('footer.testPayments') }}</p>
      <p v-if="config.uses_tmdb" class="muted tmdb" lang="en">{{ t('footer.tmdb') }}</p>
      <p class="links">
        <a href="/admin/">{{ t('footer.admin') }}</a>
        <a href="/api/docs/">{{ t('footer.api') }}</a>
      </p>
    </div>
  </footer>
</template>

<style scoped>
.footer {
  border-top: 1px solid var(--asphalt-800);
  background: var(--asphalt-950);
  font-size: var(--step--1);
}

.inner {
  display: grid;
  gap: 6px;
  padding-top: 28px;
  padding-bottom: 36px;
}

.tagline {
  color: var(--chalk);
}

.links {
  display: flex;
  gap: 18px;
  margin-top: 6px;
}

.links a {
  color: var(--asphalt-300);
}

.links a:hover {
  color: var(--chalk);
}
</style>
