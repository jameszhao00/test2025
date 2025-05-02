<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked' // For Markdown rendering
import type {
  ChatMessage,
  TextContent,
  TextAndWorkflowState, // Import the new type
} from '@/api-client'

// Import the components used to render different message types
import TextAndWorkflowStateMessage from './TextAndWorkflowStateMessage.vue' // Import the new component

// Define the augmented ClientChatMessage type locally
// This adds client-side properties (_clientId, _isLoadingPlaceholder, _sendFailed)
// and makes all content types optional to handle different response types.
interface ClientChatMessage extends ChatMessage {
  _clientId: string
  _isLoadingPlaceholder?: boolean // Flag for the loading message placeholder
  _sendFailed?: boolean // Optional flag for user messages that failed to send
  // Ensure all possible content types from the API are optional here
  textContent?: TextContent | null
  textAndWorkflowStateContent?: TextAndWorkflowState | null // Optional Text+Workflow content
}

// Define props using defineProps generic syntax, expecting the augmented type
const props = defineProps<{
  message: ClientChatMessage // Expects a message object conforming to ClientChatMessage
}>()

// Determine if the message is from the user for styling/alignment
const isUser = props.message.role === 'user'

// --- Helper function to get the relevant content object based on responseType ---
// This simplifies accessing the correct content field in the template
const relevantContent = computed(() => {
  // Return null if it's the loading placeholder message
  if (props.message._isLoadingPlaceholder) {
    return null
  }
  // Return the appropriate content object based on the message's responseType
  switch (props.message.responseType) {
    case 'text':
      return props.message.textContent
    case 'text_and_workflow_state': // Handle the new response type
        return props.message.textAndWorkflowStateContent
    default:
      // Log a warning for unknown types and return null
      console.warn(`Unknown response type in MessageItem: ${props.message.responseType}`)
      return null
  }
})
</script>

<template>
  <li class="flex" :class="[isUser ? 'justify-end' : 'justify-start']">
    <div
      class="px-4 py-2 rounded-lg max-w-[85%] sm:max-w-[75%] text-sm shadow-sm flex items-start"
      :class="[
        isUser
          ? 'bg-blue-500 text-white rounded-br-none dark:bg-blue-600' /* User message styling */
          : 'bg-gray-200 text-gray-800 rounded-bl-none dark:bg-gray-700 dark:text-gray-200', /* Assistant message styling */
        // Add subtle opacity if the user message failed to send
        isUser && message._sendFailed ? 'opacity-70' : '',
      ]"
    >
      <div v-if="message._isLoadingPlaceholder" class="flex space-x-1.5 items-center h-5 text-current"> <span class="sr-only">Loading...</span>
          <div class="h-1.5 w-1.5 bg-current rounded-full animate-bounce [animation-delay:-0.3s]"></div>
          <div class="h-1.5 w-1.5 bg-current rounded-full animate-bounce [animation-delay:-0.15s]"></div>
          <div class="h-1.5 w-1.5 bg-current rounded-full animate-bounce"></div>
      </div>

      <template v-else>
        <span
          v-if="message.responseType === 'text' && relevantContent"
          class="whitespace-pre-wrap break-words"
        >
          {{ (relevantContent as TextContent).text }}
        </span>

        <TextAndWorkflowStateMessage
          v-else-if="message.responseType === 'text_and_workflow_state' && relevantContent"
          :content="relevantContent as TextAndWorkflowState"
          :is-user-message="isUser"
        />

        <span v-else class="italic" :class="isUser ? 'text-blue-100' : 'text-red-600 dark:text-red-400'">
          <template v-if="isUser && message._sendFailed">
            (Failed to send)
          </template>
          <template v-else>
            Content error or unknown type '{{ message.responseType }}'.
          </template>
        </span>
      </template>

      <svg v-if="isUser && message._sendFailed" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4 ml-2 text-red-300 flex-shrink-0 self-center"> <path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clip-rule="evenodd" />
      </svg>

    </div>
  </li>
</template>

<style>
/* Global bounce animation definition */
@keyframes bounce {
  0%, 100% {
    transform: translateY(-25%);
    animation-timing-function: cubic-bezier(0.8,0,1,1);
  }
  50% {
    transform: none;
    animation-timing-function: cubic-bezier(0,0,0.2,1);
  }
}
.animate-bounce {
  animation: bounce 1s infinite;
}

/* Base prose styles (apply regardless of theme) */
.prose {
  color: inherit; /* Inherit color from parent bubble */
  line-height: 1.6; /* Improve readability */
}
.prose :where(h1,h2,h3,h4,h5,h6) { /* Target headings */
  color: inherit;
  margin-top: 1.25em;
  margin-bottom: 0.5em;
  font-weight: 600;
  line-height: 1.3;
}
.prose :where(h3) { font-size: 1.1em; } /* Slightly larger H3 */
.prose :where(p) { margin-top: 0.75em; margin-bottom: 0.75em; }
.prose :where(strong) { font-weight: 600; }
.prose :where(em) { font-style: italic; }
.prose :where(ul, ol) { margin-left: 1.5em; margin-top: 0.75em; margin-bottom: 0.75em; }
.prose :where(li) { margin-top: 0.25em; margin-bottom: 0.25em; }
.prose :where(li > p) { margin-top: 0.25em; margin-bottom: 0.25em; } /* Paragraphs inside list items */
.prose :where(pre) {
  background-color: rgba(0, 0, 0, 0.05); /* Default light background */
  color: inherit;
  padding: 0.75em;
  border-radius: 0.375rem; /* 6px */
  overflow-x: auto;
  margin-top: 1em;
  margin-bottom: 1em;
  font-family: monospace;
  font-size: 0.9em;
  line-height: 1.4;
}
.prose :where(code):not(:where(pre *)) { /* Inline code */
  background-color: rgba(0, 0, 0, 0.05);
  padding: 0.2em 0.4em;
  border-radius: 0.25rem; /* 4px */
  font-size: 0.9em;
  font-family: monospace;
  word-break: break-all; /* Prevent long code words from overflowing */
}
.prose :where(blockquote) {
  border-left: 4px solid rgba(0, 0, 0, 0.1);
  padding-left: 1em;
  margin-left: 0;
  margin-right: 0;
  margin-top: 1em;
  margin-bottom: 1em;
  font-style: italic;
  color: inherit;
  opacity: 0.85;
}
.prose :where(a) {
  color: inherit;
  text-decoration: underline;
  font-weight: 500;
}
.prose :where(a:hover) { opacity: 0.8; }

/* --- Theme-Specific Prose Styles --- */

/* Styles for prose inside the user's blue bubble */
.prose-invert-blue { color: white; }
.prose-invert-blue :where(pre) { background-color: rgba(255, 255, 255, 0.1); color: white; }
.prose-invert-blue :where(code):not(:where(pre *)) { background-color: rgba(255, 255, 255, 0.15); }
.prose-invert-blue :where(blockquote) { border-left-color: rgba(255, 255, 255, 0.5); color: white; opacity: 0.9; }
.prose-invert-blue :where(a) { color: white; }

/* Styles for prose inside the assistant's gray bubble */
.prose-gray { color: #1f2937; } /* text-gray-800 */
.prose-gray :where(pre) { background-color: #e5e7eb; } /* bg-gray-200 */
.prose-gray :where(code):not(:where(pre *)) { background-color: #e5e7eb; } /* bg-gray-200 */
.prose-gray :where(blockquote) { border-left-color: #9ca3af; color: #4b5563; } /* border-gray-400, text-gray-600 */
.prose-gray :where(a) { color: #1d4ed8; } /* text-blue-700 */
.prose-gray :where(a:hover) { color: #2563eb; } /* text-blue-600 */

/* Dark mode adjustments for gray prose */
.dark .prose-gray { color: #d1d5db; } /* text-gray-300 */
.dark .prose-gray :where(pre) { background-color: #4b5563; } /* bg-gray-600 */
.dark .prose-gray :where(code):not(:where(pre *)) { background-color: #4b5563; } /* bg-gray-600 */
.dark .prose-gray :where(blockquote) { border-left-color: #6b7280; color: #9ca3af; } /* border-gray-500, text-gray-400 */
.dark .prose-gray :where(a) { color: #60a5fa; } /* text-blue-400 */
.dark .prose-gray :where(a:hover) { color: #93c5fd; } /* text-blue-300 */

</style>