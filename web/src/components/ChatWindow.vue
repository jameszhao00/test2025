<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue';
import MessageItem from './MessageItem.vue';
import type { ChatMessage } from '@/api-client';

// Props definition
defineProps<{
  messages: ChatMessage[]
}>();

// Ref for the scrollable element
const messageListRef = ref<HTMLElement | null>(null);

// Function to scroll to the bottom
const scrollToBottom = async () => {
  await nextTick(); // Wait for DOM updates before scrolling
  const el = messageListRef.value;
  if (el) {
    el.scrollTop = el.scrollHeight; // Set scroll position to the very bottom
  }
};

// Expose the function so the parent component (App.vue) can call it
defineExpose({
  scrollToBottom
});

// Scroll initially when the component mounts
onMounted(() => {
  scrollToBottom();
});

</script>

<template>
  <div ref="messageListRef" class="flex-grow overflow-y-auto bg-white p-4 rounded-lg">
    <ul v-if="messages.length > 0" class="space-y-3">
      <MessageItem
        v-for="message in messages"
        :key="message.id"
        :message="message"
      />
    </ul>
    <p v-else class="text-center text-gray-500 italic py-4">
      No messages yet. Send one below!
    </p>
  </div>
</template>

<style scoped>
/* No scoped styles needed as Tailwind classes handle the styling. */
/* Scrollbar styling is handled globally in main.css or App.vue */
</style>
