<script setup lang="ts">
import type { SxSContent } from '@/api-client'

// Define props
defineProps<{
  content: SxSContent
  isUserMessage: boolean // To potentially adjust styling later
}>()
</script>

<template>
  <div class="w-full overflow-x-auto">
    <h4 class="font-semibold text-base mb-2">{{ content.title }}</h4>
    <table class="min-w-full border-collapse text-xs sm:text-sm">
      <thead :class="isUserMessage ? 'bg-blue-600' : 'bg-gray-300'">
        <tr>
          <th class="border p-1.5 sm:p-2 text-left font-medium">Metric</th>
          <th class="border p-1.5 sm:p-2 text-left font-medium">
            {{ content.modelALabel || 'Model A' }}
          </th>
          <th class="border p-1.5 sm:p-2 text-left font-medium">
            {{ content.modelBLabel || 'Model B' }}
          </th>
        </tr>
      </thead>
      <tbody :class="isUserMessage ? 'bg-blue-500' : 'bg-gray-200'">
        <tr
          v-for="row in content.rows"
          :key="row.key"
          class="hover:bg-opacity-80 transition-colors duration-100"
          :class="isUserMessage ? 'hover:bg-blue-400' : 'hover:bg-gray-300'"
        >
          <td class="border p-1.5 sm:p-2 font-medium">{{ row.label }}</td>
          <td class="border p-1.5 sm:p-2">{{ row.valueModelA }}</td>
          <td class="border p-1.5 sm:p-2">{{ row.valueModelB }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
/* Ensure table borders have the correct color based on background */
.bg-blue-600 th,
.bg-blue-500 td {
  border-color: rgba(255, 255, 255, 0.3); /* Lighter blue/transparent white for borders */
}
.bg-gray-300 th,
.bg-gray-200 td {
  border-color: #d1d5db; /* gray-300 for borders */
}
/* Improve contrast for table header text */
.bg-blue-600 th {
  color: white;
}
.bg-gray-300 th {
  color: #1f2937; /* gray-800 */
}
/* Ensure table cells have consistent padding and alignment */
th,
td {
  vertical-align: top; /* Align content to top */
}
</style>
