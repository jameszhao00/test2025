<script setup lang="ts">
// Define props using defineProps generic syntax
defineProps<{
  message: string | null // Expects a message string or null
}>()
</script>

<template>
  <p v-if="message" class="bg-red-100 text-red-700 px-4 py-3 rounded-md text-sm text-center">
    {{ message }}
  </p>
</template>

<style scoped>
/* No scoped styles needed as Tailwind classes handle all styling. */
</style>
