<script setup>
import { ref, watchEffect } from 'vue'
import QRCode from 'qrcode'

const props = defineProps({ value: { type: String, required: true }, size: { type: Number, default: 132 } })
const src = ref('')

watchEffect(async () => {
  src.value = await QRCode.toDataURL(props.value, {
    margin: 1,
    width: props.size * 2,
    color: { dark: '#1d1f23', light: '#f3f4ef' },
    errorCorrectionLevel: 'M',
  })
})
</script>

<template>
  <img v-if="src" :src="src" :width="size" :height="size" alt="" class="qr" />
</template>

<style scoped>
.qr {
  image-rendering: pixelated;
  border-radius: 4px;
}
</style>
