import { createRouter, createWebHistory } from 'vue-router'
import store from '@/store'
import { t } from '@/i18n'

import HomeView from '@/views/HomeView.vue'

const routes = [
  { path: '/', name: 'home', component: HomeView },
  { path: '/films/:id(\\d+)', name: 'film', component: () => import('@/views/FilmView.vue'), props: true },
  {
    path: '/showtimes/:id(\\d+)',
    name: 'seats',
    component: () => import('@/views/SeatView.vue'),
    props: true,
    meta: { titleKey: 'seats.pick' },
  },
  {
    path: '/tickets',
    name: 'tickets',
    component: () => import('@/views/TicketsView.vue'),
    meta: { requiresAuth: true, titleKey: 'tickets.title' },
  },
  {
    path: '/checkout/complete',
    name: 'checkout-complete',
    component: () => import('@/views/CheckoutCompleteView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/checkout/demo/:code',
    name: 'checkout-demo',
    component: () => import('@/views/DemoCheckoutView.vue'),
    props: true,
    meta: { requiresAuth: true, titleKey: 'checkout.demoTitle' },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { guestOnly: true, titleKey: 'auth.signInTitle' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { guestOnly: true, titleKey: 'auth.registerTitle' },
  },
  { path: '/verify-email', name: 'verify-email', component: () => import('@/views/VerifyEmailView.vue') },
  {
    path: '/forgot-password',
    name: 'forgot-password',
    component: () => import('@/views/ForgotPasswordView.vue'),
    meta: { titleKey: 'auth.forgotTitle' },
  },
  {
    path: '/reset-password',
    name: 'reset-password',
    component: () => import('@/views/ResetPasswordView.vue'),
    meta: { titleKey: 'auth.resetTitle' },
  },
  // Old address from the first version of the site
  { path: '/SeatChoosing/:id', redirect: (to) => ({ name: 'seats', params: { id: to.params.id } }) },
  { path: '/dashboard', redirect: '/' },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFoundView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, saved) {
    if (saved) return saved
    if (to.hash) return { el: to.hash, top: 80 }
    if (to.name === from.name && to.name === 'home') return false
    return { top: 0 }
  },
})

router.beforeEach((to) => {
  const loggedIn = store.getters['auth/loggedIn']
  if (to.meta.requiresAuth && !loggedIn) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.meta.guestOnly && loggedIn) {
    return to.query.next ? String(to.query.next) : { name: 'home' }
  }
  return true
})

router.afterEach((to) => {
  if (to.meta.titleKey) document.title = `${t(to.meta.titleKey)} | Asphalt Cinema`
  else if (!['film'].includes(to.name)) document.title = 'Asphalt Cinema'
})

export default router
