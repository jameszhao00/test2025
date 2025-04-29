<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked' // Import marked
import type {
  ChatMessage,
  TextContent,
  MarkdownContent,
  FormContent,
  SxSContent,
} from '@/api-client'

// Import the new components
import FormMessage from './FormMessage.vue'
import SxsMessage from './SxsMessage.vue'

// Define the augmented type locally (or import if defined globally)
interface ClientChatMessage extends ChatMessage {
  _clientId: string
  _isLoadingPlaceholder?: boolean // Flag for the loading message
  _sendFailed?: boolean // Optional flag for failed user messages
}

// Define props using defineProps generic syntax, expecting the augmented type
const props = defineProps<{
  message: ClientChatMessage // Expects a message object conforming to ClientChatMessage
}>()

// Determine message alignment and styling based on role
const isUser = props.message.role === 'user'

// --- Computed property for parsed Markdown ---
const parsedMarkdown = computed(() => {
  if (props.message.responseType === 'markdown' && props.message.markdownContent) {
    try {
      // Use marked to parse the markdown string into HTML
      return marked.parse(props.message.markdownContent.markdown)
    } catch (e) {
      console.error('Error parsing markdown:', e)
      return "<p class='text-red-500'>Error rendering Markdown.</p>" // Fallback HTML
    }
  }
  return '' // Return empty string if not markdown
})

// --- Helper function to get the relevant content object ---
// This simplifies the template slightly
const relevantContent = computed(() => {
  // Return null if it's the loading placeholder
  if (props.message._isLoadingPlaceholder) {
    return null
  }
  switch (props.message.responseType) {
    case 'text':
      return props.message.textContent
    case 'markdown':
      return props.message.markdownContent
    case 'form':
      return props.message.formContent
    case 'sxs':
      return props.message.sxsContent
    default:
      return null
  }
})
</script>

<template>
  <li class="flex" :class="[isUser ? 'justify-end' : 'justify-start']">
    <div
      class="px-4 py-2 rounded-lg max-w-[85%] sm:max-w-[75%] text-sm shadow-sm flex items-center"
      :class="[
        isUser
          ? 'bg-blue-500 text-white rounded-br-none' /* User: Blue bg, white text, sharp bottom-right */
          : 'bg-gray-200 text-gray-800 rounded-bl-none' /* Assistant: Gray bg, dark text, sharp bottom-left */,
        // Add subtle opacity if the user message failed to send
        isUser && message._sendFailed ? 'opacity-70' : '',
      ]"
    >
      <div v-if="message._isLoadingPlaceholder" class="flex space-x-1.5 items-center h-5">
         <span class="sr-only">Loading...</span> <div class="h-1.5 w-1.5 bg-current rounded-full animate-bounce [animation-delay:-0.3s]"></div>
         <div class="h-1.5 w-1.5 bg-current rounded-full animate-bounce [animation-delay:-0.15s]"></div>
         <div class="h-1.5 w-1.5 bg-current rounded-full animate-bounce"></div>
      </div>

      <template v-else>
        <span
          v-if="message.responseType === 'text' && message.textContent"
          class="whitespace-pre-wrap break-words"
        >
          {{ message.textContent.text }}
        </span>

        <div
          v-else-if="message.responseType === 'markdown' && message.markdownContent"
          class="prose prose-sm max-w-none break-words"
          v-html="parsedMarkdown"
        ></div>

        <FormMessage
          v-else-if="message.responseType === 'form' && message.formContent"
          :content="message.formContent"
          :is-user-message="isUser"
        />

        <SxsMessage
          v-else-if="message.responseType === 'sxs' && message.sxsContent"
          :content="message.sxsContent"
          :is-user-message="isUser"
        />

        <span v-else class="text-red-500 italic">
          <template v-if="isUser && message._sendFailed">
            (Failed to send)
          </template>
          <template v-else>
             Content error for type '{{ message.responseType }}'.
          </template>
        </span>
      </template>

       <svg v-if="isUser && message._sendFailed" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4 ml-2 text-red-300 flex-shrink-0">
        <path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clip-rule="evenodd" />
      </svg>

    </div>
  </li>
</template>

<style>
/* Add bounce animation */
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

/* Prose styles remain the same as before */
.prose {
  color: inherit;
}
.prose h1,
.prose h2,
.prose h3,
.prose h4,
.prose h5,
.prose h6 {
  color: inherit;
  margin-top: 1.25em;
  margin-bottom: 0.5em;
  font-weight: 600;
  line-height: 1.3;
}
.prose h3 {
  font-size: 1.1em;
}
.prose p {
  margin-top: 0.75em;
  margin-bottom: 0.75em;
  line-height: 1.6;
}
.prose strong {
  font-weight: 600;
}
.prose em {
  font-style: italic;
}
.prose ul,
.prose ol {
  margin-left: 1.5em;
  margin-top: 0.75em;
  margin-bottom: 0.75em;
}
.prose li {
  margin-top: 0.25em;
  margin-bottom: 0.25em;
}
.prose li > p {
  margin-top: 0.25em;
  margin-bottom: 0.25em;
}
.prose pre {
  background-color: rgba(0, 0, 0, 0.05);
  color: inherit;
  padding: 0.75em;
  border-radius: 0.375rem;
  overflow-x: auto;
  margin-top: 1em;
  margin-bottom: 1em;
  font-family: monospace;
  font-size: 0.9em;
  line-height: 1.4;
}
.prose code:not(pre *) {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 0.2em 0.4em;
  border-radius: 0.25rem;
  font-size: 0.9em;
  font-family: monospace;
}
.prose blockquote {
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
.prose a {
  color: inherit;
  text-decoration: underline;
  font-weight: 500;
}
.prose a:hover {
  opacity: 0.8;
}
.bg-blue-500 .prose {
  color: white;
}
.bg-blue-500 .prose pre {
  background-color: rgba(255, 255, 255, 0.1);
  color: white;
}
.bg-blue-500 .prose code:not(pre *) {
  background-color: rgba(255, 255, 255, 0.15);
}
.bg-blue-500 .prose blockquote {
  border-left-color: rgba(255, 255, 255, 0.5);
  color: white;
  opacity: 0.9;
}
.bg-blue-500 .prose a {
  color: white;
}
.bg-gray-200 .prose {
  color: #1f2937;
}
.bg-gray-200 .prose pre {
  background-color: #e5e7eb;
}
.bg-gray-200 .prose code:not(pre *) {
  background-color: #e5e7eb;
}
.bg-gray-200 .prose blockquote {
  border-left-color: #9ca3af;
  color: #4b5563;
}
.bg-gray-200 .prose a {
  color: #1d4ed8;
}
.bg-gray-200 .prose a:hover {
  color: #2563eb;
}
</style>
