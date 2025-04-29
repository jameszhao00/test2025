<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked' // Import marked
// Import the base ChatMessage and the specific content types if needed for casting
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

// Define props using defineProps generic syntax
const props = defineProps<{
  message: ChatMessage // Expects a message object conforming to ChatMessage type
}>()

// Determine message alignment and styling based on role
const isUser = props.message.role === 'user'

// --- Computed property for parsed Markdown ---
// Access markdownContent directly after checking responseType
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
      class="px-4 py-2 rounded-lg max-w-[85%] sm:max-w-[75%] text-sm shadow-sm"
      :class="[
        isUser
          ? 'bg-blue-500 text-white rounded-br-none' /* User: Blue bg, white text, sharp bottom-right */
          : 'bg-gray-200 text-gray-800 rounded-bl-none' /* Assistant: Gray bg, dark text, sharp bottom-left */,
      ]"
    >
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
        Content error for type '{{ message.responseType }}'.
      </span>
    </div>
  </li>
</template>

<style>
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
