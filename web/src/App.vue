<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { v4 as uuidv4 } from 'uuid' // Import uuid
import ChatWindow from './components/ChatWindow.vue'
import ChatInput from './components/ChatInput.vue'
import ErrorMessage from './components/ErrorMessage.vue'
import { useChatStore } from '@/stores/chat'
import type { ChatMessage, TextContent } from '@/api-client'
import type { Ref } from 'vue'; // Explicitly import Ref

// Define the augmented type here if not exported from store
// Add _isLoadingPlaceholder property
interface ClientChatMessage extends ChatMessage {
  _clientId: string
  _isLoadingPlaceholder?: boolean // Flag for the loading message
  _sendFailed?: boolean // Optional flag for failed user messages
}

// --- Store Setup ---
const chatStore = useChatStore()
// Use the augmented type for messages ref
const { messages, error, isLoading, isConnecting, hasSession } = storeToRefs(chatStore) as {
  messages: Ref<ClientChatMessage[]> // Cast here
  error: Ref<string | null>
  isLoading: Ref<boolean>
  isConnecting: Ref<boolean>
  hasSession: Ref<boolean>
}
const { sendMessage, initializeChat, clearSession } = chatStore

// --- DOM Refs ---
const chatWindowRef = ref<InstanceType<typeof ChatWindow> | null>(null)

// --- Component Logic ---
const placeholderMessageId = ref<string | null>(null) // To track the temporary message

async function handleSendMessage(inputText: string) {
  // 1. --- Add User Message Immediately ---
  const clientUserMessage: ClientChatMessage = {
    _clientId: uuidv4(),
    sessionId: chatStore.sessionId || 'temp', // Will be updated if new session
    role: 'user',
    responseType: 'text',
    textContent: { text: inputText },
    markdownContent: null,
    formContent: null,
    sxsContent: null,
  }
  messages.value.push(clientUserMessage)
  console.log(`[App.vue] Added user message with client ID: ${clientUserMessage._clientId}`)
  await nextTick()
  chatWindowRef.value?.scrollToBottom()

  // 2. --- Add Placeholder Assistant Message ---
  placeholderMessageId.value = uuidv4() // Generate ID for placeholder
  const placeholderMessage: ClientChatMessage = {
    _clientId: placeholderMessageId.value,
    sessionId: chatStore.sessionId || 'temp', // Use current or temp session ID
    role: 'assistant',
    responseType: 'text', // Placeholder type, content doesn't matter
    textContent: null, // No actual content needed
    markdownContent: null,
    formContent: null,
    sxsContent: null,
    _isLoadingPlaceholder: true, // Mark this as the placeholder
  }
  messages.value.push(placeholderMessage)
  console.log(`[App.vue] Added placeholder message with client ID: ${placeholderMessageId.value}`)
  await nextTick()
  chatWindowRef.value?.scrollToBottom()

  // 3. --- Send Message and Handle Response ---
  let success = false
  try {
    // Pass the original user message object (clientUserMessage)
    success = await sendMessage(clientUserMessage)
  } catch (err) {
    console.error('[App.vue] Error calling sendMessage:', err)
    success = false
    // Error ref should be set by the store's catch block
  } finally {
    // 4. --- Remove Placeholder Message ---
    if (placeholderMessageId.value) {
      const placeholderIndex = messages.value.findIndex(
        (m) => m._clientId === placeholderMessageId.value,
      )
      if (placeholderIndex !== -1) {
        messages.value.splice(placeholderIndex, 1) // Remove the placeholder
        console.log(`[App.vue] Removed placeholder message with client ID: ${placeholderMessageId.value}`)
      }
      placeholderMessageId.value = null // Reset placeholder tracker
    }

    // 5. --- Handle Send Failure (Optional: Mark User Message) ---
    if (!success) {
      console.error('[App.vue] sendMessage failed, error should be displayed.')
      // Find the original user message and mark it as failed
      const failedMsgIndex = messages.value.findIndex(
        (m) => m._clientId === clientUserMessage._clientId,
      )
      if (failedMsgIndex !== -1) {
        // Ensure the message object allows adding this property
        messages.value[failedMsgIndex]._sendFailed = true
        console.log(`[App.vue] Marked user message ${clientUserMessage._clientId} as failed.`)
      }
    }
    // isLoading state is managed by the store and should be false now
    await nextTick() // Ensure DOM updates after removing placeholder
    chatWindowRef.value?.scrollToBottom() // Scroll again after potential removal/addition
  }
}

// --- Lifecycle Hooks ---
onMounted(() => {
  initializeChat()
})

onUnmounted(() => {
  // Cleanup if component is destroyed while loading
  if (placeholderMessageId.value) {
     const placeholderIndex = messages.value.findIndex(
        (m) => m._clientId === placeholderMessageId.value,
      )
      if (placeholderIndex !== -1) {
        messages.value.splice(placeholderIndex, 1)
      }
  }
})

// Scroll to bottom when messages change
watch(
  messages,
  async () => {
    await nextTick()
    chatWindowRef.value?.scrollToBottom()
  },
  { deep: true, immediate: false }, // Don't run immediately on setup
)

// Watch for isLoading changes specifically to scroll when placeholder is added/removed
watch(isLoading, async (newVal, oldVal) => {
  if (newVal !== oldVal) { // Only trigger on change
    await nextTick();
    chatWindowRef.value?.scrollToBottom();
  }
});

</script>

<template>
  <div class="flex flex-col h-screen bg-gray-100">
    <h1
      class="flex-shrink-0 p-4 bg-white text-xl font-semibold text-center text-gray-800 shadow-sm"
    >
      Chatty LLM (No IDs) - Inline Loading
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
        <ChatInput @send-message="handleSendMessage" :disabled="isLoading || isConnecting" />
      </div>
    </div>
  </div>
</template>

<style>
/* Global styles */
html,
body {
  height: 100%;
  margin: 0;
  font-family: 'Inter', sans-serif;
  overflow: hidden; /* Prevent body scrollbars */
}

/* Scrollbar styling */
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
