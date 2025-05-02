<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch, computed } from 'vue' // Import computed
import { storeToRefs } from 'pinia'
import { v4 as uuidv4 } from 'uuid'
import ChatWindow from './components/ChatWindow.vue'
import ChatInput from './components/ChatInput.vue'
import ErrorMessage from './components/ErrorMessage.vue'
import PlanPanel from './components/PlanPanel.vue' // Import the new PlanPanel component
import { useChatStore } from '@/stores/chat'
import type { ChatMessage, TextAndWorkflowState, WorkflowPhase } from '@/api-client' // Import WorkflowPhase
import type { Ref } from 'vue'

// Define the augmented type here if not exported from store
interface ClientChatMessage extends ChatMessage {
  _clientId: string
  _isLoadingPlaceholder?: boolean
  _sendFailed?: boolean
  // Ensure content types are potentially null/undefined
  textContent?: { text: string } | null
  textAndWorkflowStateContent?: TextAndWorkflowState | null
}

// --- Store Setup ---
const chatStore = useChatStore()
const { messages, error, isLoading, isConnecting, hasSession } = storeToRefs(chatStore) as {
  messages: Ref<ClientChatMessage[]>
  error: Ref<string | null>
  isLoading: Ref<boolean>
  isConnecting: Ref<boolean>
  hasSession: Ref<boolean>
}
const { sendMessage, initializeChat, clearSession } = chatStore

// --- DOM Refs ---
const chatWindowRef = ref<InstanceType<typeof ChatWindow> | null>(null)

// --- Component Logic ---
const placeholderMessageId = ref<string | null>(null)

// --- Computed Property for Latest Plan ---
const latestWorkflowState = computed<WorkflowPhase[] | null>(() => {
  // Iterate backwards through messages to find the most recent plan
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i]
    if (
      msg.responseType === 'text_and_workflow_state' &&
      msg.textAndWorkflowStateContent?.workflowState
    ) {
      // Return the workflowState of the first matching message found
      return msg.textAndWorkflowStateContent.workflowState
    }
  }
  // Return null if no message with a plan is found
  return null
})

async function handleSendMessage(inputText: string) {
  // 1. --- Add User Message Immediately ---
  const clientUserMessage: ClientChatMessage = {
    _clientId: uuidv4(),
    sessionId: chatStore.sessionId || 'temp',
    role: 'user',
    responseType: 'text',
    textContent: { text: inputText },
  }
  messages.value.push(clientUserMessage)
  console.log(`[App.vue] Added user message with client ID: ${clientUserMessage._clientId}`)
  await nextTick()
  chatWindowRef.value?.scrollToBottom()

  // 2. --- Add Placeholder Assistant Message ---
  placeholderMessageId.value = uuidv4()
  const placeholderMessage: ClientChatMessage = {
    _clientId: placeholderMessageId.value,
    sessionId: chatStore.sessionId || 'temp',
    role: 'assistant',
    responseType: 'text',
    textContent: null,
    _isLoadingPlaceholder: true,
  }
  messages.value.push(placeholderMessage)
  console.log(`[App.vue] Added placeholder message with client ID: ${placeholderMessageId.value}`)
  await nextTick()
  chatWindowRef.value?.scrollToBottom()

  // 3. --- Send Message and Handle Response ---
  let success = false
  try {
    success = await sendMessage(clientUserMessage)
  } catch (err) {
    console.error('[App.vue] Error calling sendMessage:', err)
    success = false
  } finally {
    // 4. --- Remove Placeholder Message ---
    if (placeholderMessageId.value) {
      const placeholderIndex = messages.value.findIndex(
        (m) => m._clientId === placeholderMessageId.value,
      )
      if (placeholderIndex !== -1) {
        messages.value.splice(placeholderIndex, 1)
        console.log(`[App.vue] Removed placeholder message with client ID: ${placeholderMessageId.value}`)
      }
      placeholderMessageId.value = null
    }

    // 5. --- Handle Send Failure ---
    if (!success) {
      console.error('[App.vue] sendMessage failed, error should be displayed.')
      const failedMsgIndex = messages.value.findIndex(
        (m) => m._clientId === clientUserMessage._clientId,
      )
      if (failedMsgIndex !== -1) {
        messages.value[failedMsgIndex]._sendFailed = true
        console.log(`[App.vue] Marked user message ${clientUserMessage._clientId} as failed.`)
      }
    }
    await nextTick()
    chatWindowRef.value?.scrollToBottom()
  }
}

// --- Lifecycle Hooks ---
onMounted(() => {
  initializeChat()
})

onUnmounted(() => {
  // Clean up placeholder if component is unmounted unexpectedly
  if (placeholderMessageId.value) {
     const placeholderIndex = messages.value.findIndex(
       (m) => m._clientId === placeholderMessageId.value,
     )
     if (placeholderIndex !== -1) {
       messages.value.splice(placeholderIndex, 1)
     }
  }
})

// Scroll chat window to bottom when messages change
watch(
  messages,
  async () => {
    await nextTick()
    chatWindowRef.value?.scrollToBottom()
  },
  { deep: true, immediate: false },
)

// Scroll chat window when loading state changes (placeholder added/removed)
watch(isLoading, async (newVal, oldVal) => {
  if (newVal !== oldVal) {
    await nextTick();
    chatWindowRef.value?.scrollToBottom();
  }
});

</script>

<template>
  <div class="flex flex-col h-screen bg-gray-50 relative">
    <h1
      class="flex-shrink-0 p-4 bg-white text-xl font-semibold text-center text-gray-800 z-20 border-b border-gray-100"
    >
      AIFlow Agent
    </h1>

    <div class="flex flex-grow overflow-hidden relative">
      <PlanPanel
        :workflow-state="latestWorkflowState"
        class="absolute top-0 left-0 z-10"
        />

      <div class="flex flex-col flex-grow overflow-hidden p-4 space-y-4 lg:ml-130">
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
          class="flex-grow overflow-y-auto min-h-0 custom-scrollbar"
        />

        <div class="flex-shrink-0 space-y-2">
          <ChatInput @send-message="handleSendMessage" :disabled="isLoading || isConnecting" />
        </div>
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
  background-color: #f9fafb; /* bg-gray-50 - Ensure light background */
}

/* Minimalist Scrollbar styling (Light theme only) */
.custom-scrollbar::-webkit-scrollbar {
  width: 5px; /* Thinner scrollbar */
  height: 5px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent; /* Invisible track */
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #d1d5db; /* Light gray thumb */
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #9ca3af; /* Slightly darker on hover */
}

</style>
