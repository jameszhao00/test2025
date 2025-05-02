<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import MessageItem from './MessageItem.vue'
// Import the augmented type if defined/exported by store, or define locally
// import type { ClientChatMessage } from '@/stores/chat'; // If exported
import type { ChatMessage } from '@/api-client' // Base type

// Define the augmented type locally if not exported from store
interface ClientChatMessage extends ChatMessage {
  _clientId: string
}

// Props definition using the augmented type
defineProps<{
  messages: ClientChatMessage[] // Expect messages with _clientId
}>()

// Ref for the scrollable element
const messageListRef = ref<HTMLElement | null>(null)

// Function to scroll to the bottom
const scrollToBottom = async () => {
  await nextTick() // Wait for DOM updates before scrolling
  const el = messageListRef.value
  if (el) {
    el.scrollTop = el.scrollHeight // Set scroll position to the very bottom
  }
}

// Expose the function so the parent component (App.vue) can call it
defineExpose({
  scrollToBottom,
})

// Scroll initially when the component mounts
onMounted(() => {
  scrollToBottom()
})
</script>

<template>
  <div ref="messageListRef" class="flex-grow overflow-y-auto bg-transparent p-2 rounded-lg">
    <ul v-if="messages.length > 0" class="space-y-3">
      <MessageItem v-for="message in messages" :key="message._clientId" :message="message" />
    </ul>
    <p v-else class="text-center text-gray-500 dark:text-gray-400 italic py-4">No messages yet. Send one below!</p>
  </div>
</template>

<style scoped>
/* No scoped styles needed as Tailwind classes handle styling. */
/* Scrollbar is styled globally in App.vue */
</style>
