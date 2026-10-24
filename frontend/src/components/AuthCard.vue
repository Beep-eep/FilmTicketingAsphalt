<script setup>
defineProps({ title: { type: String, required: true }, lead: { type: String, default: '' } })
</script>

<template>
  <div class="page auth-wrap">
    <section class="card">
      <div class="lane" aria-hidden="true"></div>
      <h1>{{ title }}</h1>
      <p v-if="lead" class="lead">{{ lead }}</p>
      <slot />
    </section>
  </div>
</template>

<style scoped>
.auth-wrap {
  display: grid;
  place-items: start center;
  padding-top: clamp(32px, 8vh, 80px);
}

.card {
  display: grid;
  gap: 16px;
  width: min(100%, 440px);
  padding: 28px clamp(20px, 5vw, 36px) 32px;
  border: 1px solid var(--asphalt-700);
  border-radius: var(--radius-l);
  background: var(--asphalt-900);
  box-shadow: 0 30px 70px rgba(0, 0, 0, 0.45);
}

.lane {
  width: 70px;
  height: 4px;
  border-radius: 2px;
  background: repeating-linear-gradient(90deg, var(--sodium) 0 16px, transparent 16px 26px);
}

h1 {
  font-size: var(--step-5);
}

.lead {
  margin-top: -6px;
  color: var(--asphalt-300);
}

.card :deep(form) {
  display: grid;
  gap: 16px;
}

.card :deep(.alt) {
  color: var(--asphalt-300);
  font-size: var(--step--1);
  text-align: center;
}
</style>
