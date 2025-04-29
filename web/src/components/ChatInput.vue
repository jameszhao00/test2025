<script setup lang="ts">
import { ref, nextTick } from 'vue'

// Define props
const props = defineProps<{
  disabled?: boolean // Optional boolean prop to disable the input and button
}>()

// Define emits
const emit = defineEmits(['send-message']) // Emits 'send-message' event with the text

// Input state
const inputText = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null) // Ref for the textarea element

// Function to adjust textarea height based on content
const adjustTextareaHeight = async () => {
  await nextTick() // Wait for DOM update
  const textarea = textareaRef.value
  if (textarea) {
    textarea.style.height = 'auto' // Reset height to auto to calculate new scrollHeight
    // Set height based on scroll height, but clamp between min/max defined by Tailwind classes
    const newHeight = Math.min(Math.max(textarea.scrollHeight, 40), 120) // Corresponds to min-h-[40px] and max-h-[120px]
    textarea.style.height = `${newHeight}px`
  }
}

// Handle form submission
function handleSubmit() {
  const text = inputText.value.trim()
  if (text && !props.disabled) {
    emit('send-message', text)
    inputText.value = '' // Clear input after sending
    adjustTextareaHeight() // Reset height after clearing
  }
}

// Handle Enter key (Shift+Enter for newline)
function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault() // Prevent default newline insertion
    handleSubmit() // Submit the form
  }
}

// Handle input changes to resize textarea
function handleInput() {
  adjustTextareaHeight()
}
</script>

<template>
  <form @submit.prevent="handleSubmit" class="flex items-start space-x-2 pt-2">
    <textarea
      ref="textareaRef"
      v-model="inputText"
      placeholder="Type your message..."
      :disabled="disabled"
      required
      rows="1"
      @keydown="handleKeydown"
      @input="handleInput"
      class="flex-grow p-2 text-sm bg-white rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:bg-gray-100 disabled:cursor-not-allowed min-h-[40px] max-h-[120px] overflow-y-auto"
    ></textarea>
    <button
      type="submit"
      :disabled="disabled || inputText.trim() === ''"
      class="flex-shrink-0 px-4 py-2 text-sm font-medium text-white bg-blue-500 rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-opacity-50 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors duration-150 h-[40px]"
    >
      Send
    </button>
  </form>
</template>

<style scoped>
/* Scoped styles are no longer needed as Tailwind handles styling */
/* Textarea overflow is handled inline via class and in main.css */
</style>
