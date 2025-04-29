<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import ChatWindow from './components/ChatWindow.vue'
import ChatInput from './components/ChatInput.vue'
import ErrorMessage from './components/ErrorMessage.vue'
// Import the generated API client and models for Chat
import { DefaultApi, Configuration, ResponseError } from '@/api-client'
import type { ChatMessage, ChatRequest } from '@/api-client' // Use Chat related types

// --- Constants ---
const SESSION_ID_STORAGE_KEY = 'chatSessionId';
const POLLING_INTERVAL_MS = 3000; // Poll for new messages every 3 seconds

// --- API Client Setup ---
const config = new Configuration({ basePath: '' }); // Adjust if your API is served elsewhere
const apiClient = new DefaultApi(config);

// --- Reactive State ---
const messages = ref<ChatMessage[]>([]) // Holds all messages for the current session
const sessionId = ref<string | null>(localStorage.getItem(SESSION_ID_STORAGE_KEY)); // Load session ID from storage
const error = ref<string | null>(null)
const isLoading = ref<boolean>(false); // Loading state for sending messages
const isConnecting = ref<boolean>(false); // Initial connection/loading state
const lastMessageId = ref<number>(0); // Track the ID of the last message received
const pollingTimer = ref<number | null>(null); // Timer ID for polling

// --- DOM Refs ---
const chatWindowRef = ref<InstanceType<typeof ChatWindow> | null>(null); // Ref to scroll chat window

// --- API Interaction Logic ---

// Helper function to extract error messages
async function getErrorMessage(e: unknown, defaultMessage: string): Promise<string> {
  error.value = null; // Clear previous error
  console.error(defaultMessage, e); // Log the error details

  if (e instanceof ResponseError) {
    try {
      const errorBody = await e.response.json();
      if (errorBody.detail) {
        if (Array.isArray(errorBody.detail)) {
          return errorBody.detail.map((d: any) => `${d.loc.join('.')} - ${d.msg}`).join('; ');
        }
        return String(errorBody.detail);
      }
      return `${e.response.status}: ${e.response.statusText || defaultMessage}`;
    } catch (parseError) {
      console.error('Failed to parse error response:', parseError);
      return `${e.response.status}: ${e.response.statusText || defaultMessage}`;
    }
  } else if (e instanceof Error) {
    return e.message;
  }
  return defaultMessage;
}


// Function to send a message
async function handleSendMessage(inputText: string) {
  error.value = null;
  isLoading.value = true;

  // Optimistic UI Update
  const tempUserMessage: ChatMessage = {
      id: Date.now(), // Use timestamp as temporary ID
      sessionId: sessionId.value || 'temp',
      role: 'user',
      content: inputText,
  };
    messages.value.push(tempUserMessage);
    await nextTick();
    chatWindowRef.value?.scrollToBottom();


  const requestBody: ChatRequest = {
    sessionId: sessionId.value,
    content: inputText
  };

  try {
    const response = await apiClient.handleChatApiChatPost({ chatRequest: requestBody });

    if (!sessionId.value && response.sessionId) {
      sessionId.value = response.sessionId;
      localStorage.setItem(SESSION_ID_STORAGE_KEY, response.sessionId);
      console.log('Started new session:', response.sessionId);
      startPolling(); // Start polling only after getting a session ID
    }

    // Backend Confirmed Update - Remove optimistic message
    // We rely on polling to fetch the real messages, including the user's and assistant's
    const tempIndex = messages.value.findIndex(m => m.id === tempUserMessage.id);
    if (tempIndex !== -1) {
        messages.value.splice(tempIndex, 1);
    }
    // Trigger immediate fetch after sending to get confirmation faster
    await fetchMessages();


  } catch (e) {
    // Remove optimistic message on error
      const tempIndex = messages.value.findIndex(m => m.id === tempUserMessage.id);
      if (tempIndex !== -1) {
          messages.value.splice(tempIndex, 1);
      }
    error.value = await getErrorMessage(e, 'Failed to send message.');
    if (error.value?.includes("Session not found")) {
        clearSession(); // Clear invalid session if server indicates it
    }
  } finally {
    isLoading.value = false;
  }
}

// Function to fetch messages
async function fetchMessages() {
  if (!sessionId.value) {
    isConnecting.value = false; // Ensure connecting state is off if no session
    return;
  }

  // Don't show connecting message during regular polling, only initial load
  // isConnecting.value = messages.value.length === 0; // Only set connecting if no messages exist yet

  try {
    const response = await apiClient.getSessionMessagesApiChatSessionIdMessagesGet({
      sessionId: sessionId.value,
      since: lastMessageId.value // Fetch only messages newer than the last one we received
    });

    if (response.messages && response.messages.length > 0) {
      const existingIds = new Set(messages.value.map(m => m.id));
      const newMessages = response.messages.filter(m => !existingIds.has(m.id)); // Avoid duplicates

      if (newMessages.length > 0) {
          messages.value.push(...newMessages);
          // Sort just in case messages arrive out of order (though unlikely with 'since')
          messages.value.sort((a, b) => a.id - b.id);
          lastMessageId.value = messages.value[messages.value.length - 1].id; // Update last message ID
          await nextTick();
          chatWindowRef.value?.scrollToBottom(); // Scroll down after adding new messages
      }
    }
  } catch (e) {
    const fetchError = await getErrorMessage(e, 'Failed to fetch messages.');
      // Only display fetch error if there isn't already an error showing,
      // or if it's specifically a "Session not found" error which requires clearing.
      if (fetchError?.includes("Session not found") || !error.value) {
          error.value = fetchError;
      }
    if (error.value?.includes("Session not found")) {
        clearSession(); // Clear invalid session
    }
  } finally {
    isConnecting.value = false; // Turn off connecting indicator after fetch attempt
  }
}

// --- Polling Logic ---
function startPolling() {
  stopPolling(); // Clear any existing timer
  if (!sessionId.value) return; // Don't poll without a session
  console.log('Starting polling...');
  // Fetch immediately first, then set interval
  fetchMessages();
  pollingTimer.value = window.setInterval(fetchMessages, POLLING_INTERVAL_MS);
}

function stopPolling() {
  if (pollingTimer.value !== null) {
    console.log('Stopping polling.');
    clearInterval(pollingTimer.value);
    pollingTimer.value = null;
  }
}

// --- Session Management ---
function clearSession() {
    console.log('Clearing session.');
    stopPolling();
    sessionId.value = null;
    localStorage.removeItem(SESSION_ID_STORAGE_KEY);
    messages.value = []; // Clear messages array
    lastMessageId.value = 0; // Reset last message ID tracker
    error.value = "Session cleared or expired. Start a new chat by sending a message."; // Inform user
    isConnecting.value = false; // Ensure connecting state is off
}

// --- Lifecycle Hooks ---
onMounted(async () => {
  if (sessionId.value) {
    console.log('Found existing session:', sessionId.value);
    isConnecting.value = true; // Show connecting message on initial load with session
    await fetchMessages(); // Fetch initial messages for the session
    startPolling(); // Start polling for updates
  } else {
    console.log('No existing session found. Send a message to start.');
    isConnecting.value = false; // No connection attempt needed yet
  }
});

onUnmounted(() => {
  stopPolling(); // Clean up timer when component is destroyed
});

// Scroll to bottom when messages change
watch(messages, async () => {
  await nextTick(); // Wait for DOM update
  chatWindowRef.value?.scrollToBottom();
}, { deep: true }); // Watch for changes within the array items

</script>

<template>
  <div class="flex flex-col h-screen bg-gray-100">

    <h1 class="flex-shrink-0 p-4 bg-white text-xl font-semibold text-center text-gray-800">
      Chatty LLM
    </h1>

    <div class="flex flex-col flex-grow overflow-hidden p-4 space-y-4">

        <div v-if="isConnecting && messages.length === 0" class="flex-shrink-0 text-center text-gray-500 p-2">
            Connecting to chat...
        </div>

        <ErrorMessage :message="error" class="flex-shrink-0" />

        <ChatWindow
            ref="chatWindowRef"
            :messages="messages"
            class="flex-grow overflow-y-auto min-h-0"
           />

        <div class="flex-shrink-0 space-y-2">
            <div v-if="isLoading" class="text-center text-gray-500 text-sm p-1">
                Sending...
            </div>

            <ChatInput @send-message="handleSendMessage" :disabled="isLoading || isConnecting" />
        </div>
    </div>

  </div>
</template>

<style>
/* Global styles moved to main.css */
/* Ensure html, body take full height if needed, though h-screen on the root div usually suffices */
html, body {
  height: 100%;
  margin: 0;
}
</style>
