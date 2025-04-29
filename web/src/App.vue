<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { v4 as uuidv4 } from 'uuid' // Import uuid
import ChatWindow from './components/ChatWindow.vue'
import ChatInput from './components/ChatInput.vue'
import ErrorMessage from './components/ErrorMessage.vue'
import { useChatStore } from '@/stores/chat'
// Import the augmented type if defined in the store, or handle locally
// Assuming ClientChatMessage is defined/used within the store for simplicity here
import type { ChatMessage, TextContent } from '@/api-client'

// Define the augmented type here if not exported from store
interface ClientChatMessage extends ChatMessage {
  _clientId: string
}

// --- Store Setup ---
const chatStore = useChatStore()
// Need to cast messages from store if using augmented type internally
const { messages, error, isLoading, isConnecting, hasSession } = storeToRefs(chatStore)
const { sendMessage, initializeChat, clearSession } = chatStore

// --- DOM Refs ---
const chatWindowRef = ref<InstanceType<typeof ChatWindow> | null>(null)

// --- Component Logic ---

async function handleSendMessage(inputText: string) {
  // --- Add User Message Immediately with Client ID ---
  const clientUserMessage: ClientChatMessage = {
    // id: undefined, // No server ID
    _clientId: uuidv4(), // Generate client-side unique key
    sessionId: chatStore.sessionId || 'temp',
    role: 'user',
    responseType: 'text',
    textContent: { text: inputText },
    markdownContent: null,
    formContent: null,
    sxsContent: null,
  }
  // Add the message with the client ID to the store's array
  // We push directly for simplicity, assuming store allows it.
  // Alternatively, create a store action `addUserMessage`.
  messages.value.push(clientUserMessage)
  console.log(`[App.vue] Added user message with client ID: ${clientUserMessage._clientId}`)
  await nextTick()
  chatWindowRef.value?.scrollToBottom()
  // --- End Add User Message ---

  // Call store action to send message and add reply
  // Pass the clientUserMessage so the store can update its session ID if needed
  const success = await sendMessage(clientUserMessage)

  // --- NO REMOVAL NEEDED ---
  // The user message persists. The store adds the assistant reply.

  if (!success) {
    console.error('[App.vue] sendMessage failed, error should be displayed.')
    // Optionally, add a visual indicator to the failed message
    // Find the message and add a property like `_sendFailed: true`
    const failedMsgIndex = messages.value.findIndex(
      (m) => m._clientId === clientUserMessage._clientId,
    )
    if (failedMsgIndex !== -1) {
      // This requires ClientChatMessage to allow extra properties or define _sendFailed
      // (messages.value[failedMsgIndex] as any)._sendFailed = true;
    }
  }
  // isLoading state is managed by the store
}

// --- Lifecycle Hooks ---
onMounted(() => {
  initializeChat()
})

onUnmounted(() => {
  // No cleanup needed for polling
})

// Scroll to bottom when messages change
// No sorting needed as order is append-only + full refresh
watch(
  messages,
  async () => {
    // console.log("[App.vue] Watcher triggered on messages.");
    await nextTick()
    chatWindowRef.value?.scrollToBottom()
  },
  { deep: true },
)
</script>

<template>
  <div class="flex flex-col h-screen bg-gray-100">
    <h1
      class="flex-shrink-0 p-4 bg-white text-xl font-semibold text-center text-gray-800 shadow-sm"
    >
      Chatty LLM (No IDs)
    </h1>

    <div class="flex flex-col flex-grow overflow-hidden p-4 space-y-4">
      <div
        v-if="isConnecting && messages.length === 0"
        class="flex-shrink-0 text-center text-gray-500 p-2"
      >
        Loading chat history...
      </div>

      <ErrorMessage :message="error" class="flex-shrink-0" />

      <ChatWindow
        ref="chatWindowRef"
        :messages="messages"
        class="flex-grow overflow-y-auto min-h-0"
      />

      <div class="flex-shrink-0 space-y-2">
        <div v-if="isLoading" class="text-center text-gray-500 text-sm p-1">Sending...</div>

        <ChatInput @send-message="handleSendMessage" :disabled="isLoading || isConnecting" />
      </div>
    </div>
  </div>
</template>

<style>
/* Styles remain the same */
html,
body {
  height: 100%;
  margin: 0;
  font-family: 'Inter', sans-serif;
}
::-webkit-scrollbar {
  width: 8px;
}
::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 10px;
}
::-webkit-scrollbar-thumb {
  background: #c5c5c5;
  border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>
