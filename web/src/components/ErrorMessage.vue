<script setup lang="ts">
defineProps<{
  message: string | null
}>()
</script>

<template>
  <p v-if="message" class="error-message">
    {{ message }}
  </p>
</template>

<style scoped>
.error-message {
  color: #d9534f;
  background-color: #f2dede;
  border: 1px solid #ebccd1;
  padding: 0.8rem;
  border-radius: 4px;
  margin-bottom: 1rem;
  text-align: center;
}
</style>