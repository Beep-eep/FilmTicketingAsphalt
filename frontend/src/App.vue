<script setup>
import NavBar from '@/components/NavBar.vue'
import SiteFooter from '@/components/SiteFooter.vue'
import ToastHost from '@/components/ToastHost.vue'
</script>

<template>
  <a class="skip-link" href="#main">Skip to content</a>
  <NavBar />
  <main id="main" tabindex="-1">
    <RouterView v-slot="{ Component, route }">
      <Transition name="route" mode="out-in">
        <component :is="Component" :key="route.name === 'home' ? 'home' : route.fullPath" />
      </Transition>
    </RouterView>
  </main>
  <SiteFooter />
  <ToastHost />
</template>

<style scoped>
main {
  flex: 1;
  outline: none;
  padding-bottom: 64px;
}

.skip-link {
  position: absolute;
  left: 12px;
  top: -60px;
  z-index: 100;
  padding: 10px 14px;
  border-radius: var(--radius-s);
  background: var(--sodium);
  color: var(--ink);
  font-weight: 700;
}

.skip-link:focus {
  top: 12px;
}
</style>
