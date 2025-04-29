<script setup lang="ts">
import type { ChatMessage } from '@/api-client';

// Define props using defineProps generic syntax
const props = defineProps<{
  message: ChatMessage // Expects a message object conforming to ChatMessage type
}>();

// Determine message alignment and styling based on role
const isUser = props.message.role === 'user';
</script>

<template>
  <li class="flex" :class="[isUser ? 'justify-end' : 'justify-start']">
    <div
      class="px-4 py-2 rounded-lg max-w-[75%] text-sm"
      :class="[
        isUser
          ? 'bg-blue-500 text-white rounded-br-none' /* User: Blue bg, white text, sharp bottom-right */
          : 'bg-gray-200 text-gray-800 rounded-bl-none' /* Assistant: Gray bg, dark text, sharp bottom-left */
      ]"
    >
      <span class="whitespace-pre-wrap">{{ message.content }}</span>
    </div>
  </li>
</template>

<style scoped>
/* No scoped styles needed as Tailwind classes handle all styling. */
</style>
