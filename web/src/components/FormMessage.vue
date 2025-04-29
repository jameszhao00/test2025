<script setup lang="ts">
import { ref, computed } from 'vue'
// Import the necessary types from the regenerated API client
import type {
  FormContent,
  TextField,
  DropdownField,
  FormFieldWrapper, // Import the new wrapper type
} from '@/api-client'

// Define props
const props = defineProps<{
  content: FormContent // Expects FormContent where content.fields is Array<FormFieldWrapper>
  isUserMessage: boolean // To potentially adjust styling later
}>()

// Reactive state to hold form values, keyed by fieldId
const formValues = ref<Record<string, string>>({})

// --- Initialization Logic ---
// Iterate through the FormFieldWrapper array in the content prop
props.content.fields.forEach((wrapper: FormFieldWrapper) => {
  // Check if it's a text field
  if (wrapper.textField) {
    const field = wrapper.textField // Get the actual TextField object
    // Use the fieldId from the TextField object as the key
    // Initialize with initialValue or default to an empty string
    formValues.value[field.fieldId] = field.initialValue ?? ''
  }
  // Check if it's a dropdown field
  else if (wrapper.dropdownField) {
    const field = wrapper.dropdownField // Get the actual DropdownField object
    // Use the fieldId from the DropdownField object as the key
    // Use defaultOption if provided and valid, otherwise use the first option,
    // or fallback to an empty string if no options exist.
    formValues.value[field.fieldId] =
      field.defaultOption ?? field.options?.[0] ?? ''
  }
  // Handle unexpected empty wrapper (shouldn't happen due to backend validation)
  else {
     console.warn("Encountered an empty FormFieldWrapper:", wrapper);
  }
})

// Handle form submission (placeholder - remains unchanged)
function handleSubmit() {
  console.log('Form submitted (not implemented):', formValues.value)
  // In a real app, you would emit an event or call an API here
  alert('Form submission is not implemented in this example.')
}
</script>

<template>
  <div class="space-y-3 w-full">
    <h4 class="font-semibold text-base mb-2">{{ content.title }}</h4>

    <form @submit.prevent="handleSubmit" class="space-y-3">
      <div v-for="wrapper in content.fields" :key="wrapper.textField?.fieldId || wrapper.dropdownField?.fieldId || Math.random()">

        <template v-if="wrapper.textField">
          <label :for="wrapper.textField.fieldId" class="block text-xs font-medium mb-1 opacity-90">
            {{ wrapper.textField.label }}
          </label>
          <input
            :id="wrapper.textField.fieldId"
            :name="wrapper.textField.fieldId"
            type="text"
            :placeholder="wrapper.textField.placeholder ?? ''"
            v-model="formValues[wrapper.textField.fieldId]"
            class="w-full p-1.5 border rounded-md text-sm focus:ring-blue-400 focus:border-blue-400 shadow-sm"
            :class="
              isUserMessage
                ? 'bg-white text-gray-800 border-gray-300 placeholder-gray-400'
                : 'bg-gray-100 text-gray-800 border-gray-300 placeholder-gray-400'
            "
          />
        </template>

        <template v-else-if="wrapper.dropdownField">
           <label :for="wrapper.dropdownField.fieldId" class="block text-xs font-medium mb-1 opacity-90">
            {{ wrapper.dropdownField.label }}
          </label>
          <select
            :id="wrapper.dropdownField.fieldId"
            :name="wrapper.dropdownField.fieldId"
            v-model="formValues[wrapper.dropdownField.fieldId]"
            class="w-full p-1.5 border rounded-md text-sm focus:ring-blue-400 focus:border-blue-400 appearance-none shadow-sm"
            :class="
              isUserMessage
                ? 'bg-white text-gray-800 border-gray-300'
                : 'bg-gray-100 text-gray-800 border-gray-300'
            "
          >
            <option v-for="option in wrapper.dropdownField.options" :key="option" :value="option">
              {{ option }}
            </option>
          </select>
        </template>

         <div v-else class="text-xs italic text-red-500">
            (Invalid form field data received)
        </div>
      </div>

      <button
        type="submit"
        class="w-full px-3 py-1.5 text-sm font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-1 transition-colors duration-150"
        :class="[
          isUserMessage
            ? 'bg-white text-blue-600 hover:bg-gray-50 focus:ring-blue-500 border border-blue-300' // Style for user messages
            : 'bg-blue-500 text-white hover:bg-blue-600 focus:ring-blue-400', // Style for assistant messages
        ]"
      >
        {{ content.submitButtonText || 'Submit' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
/* Scoped styles remain the same */
select {
  /* Add dropdown arrow using background SVG */
  background-image: url('data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2020%2020%22%20fill%3D%22%236b7280%22%3E%3Cpath%20fill-rule%3D%22evenodd%22%20d%3D%22M5.293%207.293a1%201%200%20011.414%200L10%2010.586l3.293-3.293a1%201%200%20111.414%201.414l-4%204a1%201%200%2001-1.414%200l-4-4a1%201%200%20010-1.414z%22%20clip-rule%3D%22evenodd%22%2F%3E%3C%2Fsvg%3E');
  background-repeat: no-repeat;
  background-position: right 0.5rem center;
  background-size: 1.2em 1.2em;
  padding-right: 2.5rem; /* Make space for the arrow */
}
/* Adjust arrow color for selects within user messages */
.bg-white select {
  background-image: url('data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2020%2020%22%20fill%3D%22%23374151%22%3E%3Cpath%20fill-rule%3D%22evenodd%22%20d%3D%22M5.293%207.293a1%201%200%20011.414%200L10%2010.586l3.293-3.293a1%201%200%20111.414%201.414l-4%204a1%201%200%2001-1.414%200l-4-4a1%201%200%20010-1.414z%22%20clip-rule%3D%22evenodd%22%2F%3E%3C%2Fsvg%3E');
}
</style>
```
This updated `FormMessage.vue` component now correctly handles the `FormFieldWrapper` structure provided by your regenerated API client. It checks for the presence of `textField` or `dropdownField` within each wrapper and accesses the necessary properties according