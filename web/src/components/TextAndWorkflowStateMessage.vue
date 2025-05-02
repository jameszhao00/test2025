<script setup lang="ts">
import { computed, ref } from 'vue' // Import ref for state
// Import the necessary types from the regenerated API client
import type {
    TextAndWorkflowState,
    WorkflowPhase,
    WorkflowStep,
    WorkflowStatus,
} from '@/api-client'

// Define props
const props = defineProps<{
    content: TextAndWorkflowState // Expects TextAndWorkflowState content
    isUserMessage: boolean // To potentially adjust styling later (though less likely needed here)
}>()

// --- State for Collapsible Phases ---
// Initialize all phases as collapsed by default
const collapsedPhases = ref<Record<number, boolean>>(
    Object.keys(props.content.workflowState).reduce((acc, _, index) => {
        acc[index] = true // Start collapsed
        return acc
    }, {} as Record<number, boolean>)
)

// Function to toggle the collapsed state of a phase
const togglePhase = (phaseIndex: number) => {
    collapsedPhases.value[phaseIndex] = !collapsedPhases.value[phaseIndex]
}


// Helper function to get Tailwind classes based on status
// Provides distinct background, text, and border colors for each status
const getStatusClasses = (status: WorkflowStatus) => {
    switch (status) {
        case 'done':
            // Green theme for completed steps
            return 'bg-green-100 text-green-800 border-green-300 dark:bg-green-900 dark:text-green-200 dark:border-green-700'
        case 'in_progress':
            // Yellow/Amber theme for steps in progress
            return 'bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-900 dark:text-yellow-200 dark:border-yellow-700'
        case 'todo':
        default:
            // Neutral gray theme for steps not yet started
            return 'bg-gray-100 text-gray-700 border-gray-300 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-500'
    }
}

// Helper function to get an SVG icon based on status
// Uses appropriate icons to visually represent the status
const getStatusIcon = (status: WorkflowStatus) => {
    switch (status) {
        case 'done':
            // Checkmark icon SVG for completed steps
            return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4 mr-1.5 flex-shrink-0"><path fill-rule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm3.857-9.809a.75.75 0 0 0-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 1 0-1.06 1.061l2.5 2.5a.75.75 0 0 0 1.137-.089l4-5.5Z" clip-rule="evenodd" /></svg>`
        case 'in_progress':
            // Arrow path icon SVG for steps currently in progress
            return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4 mr-1.5 flex-shrink-0"><path fill-rule="evenodd" d="M2 10a.75.75 0 0 1 .75-.75h12.59l-2.1-1.95a.75.75 0 1 1 1.02-1.1l3.5 3.25a.75.75 0 0 1 0 1.1l-3.5 3.25a.75.75 0 1 1-1.02-1.1l2.1-1.95H2.75A.75.75 0 0 1 2 10Z" clip-rule="evenodd" /></svg>`
        case 'todo':
        default:
            // Circle outline icon SVG for steps yet to be done
            return `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 mr-1.5 flex-shrink-0 text-gray-400 dark:text-gray-500"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" /></svg>`
    }
}

// Helper function to format status text (optional, could be displayed)
const formatStatusText = (status: WorkflowStatus) => {
    switch (status) {
        case 'done':
            return 'Done'
        case 'in_progress':
            return 'In Progress'
        case 'todo':
        default:
            return 'To Do'
    }
}
</script>

<template>
    <div class="space-y-4 w-full text-sm">
        <p class="whitespace-pre-wrap break-words">{{ content.text }}</p>

        <div class="space-y-3 border-t pt-3 mt-3"
            :class="isUserMessage ? 'border-white/30' : 'border-gray-300 dark:border-gray-600'">
            <h4 class="font-semibold text-xs uppercase tracking-wider opacity-80 mb-2">Plan</h4>
            <div v-for="(phase, phaseIndex) in content.workflowState" :key="`phase-${phaseIndex}`"
                class="space-y-1 pl-2">
                <p class="font-medium opacity-95 cursor-pointer flex items-center hover:opacity-100 transition-opacity"
                    @click="togglePhase(phaseIndex)">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"
                        class="w-4 h-4 mr-1 transition-transform duration-200 ease-in-out flex-shrink-0"
                        :class="{ 'rotate-90': !collapsedPhases[phaseIndex] }">

                        <path fill-rule="evenodd"
                            d="M7.21 14.77a.75.75 0 0 1 .02-1.06L11.168 10 7.23 6.29a.75.75 0 1 1 1.04-1.08l4.5 4.25a.75.75 0 0 1 0 1.08l-4.5 4.25a.75.75 0 0 1-1.06-.02Z"
                            clip-rule="evenodd" />

                    </svg>
                    {{ phaseIndex + 1 }}. {{ phase.description }}
                </p>
                <ul v-if="!collapsedPhases[phaseIndex]" class="space-y-1 pl-7 transition-all duration-300 ease-in-out">
                    <li v-for="(step, stepIndex) in phase.steps" :key="`phase-${phaseIndex}-step-${stepIndex}`"
                        class="flex items-center text-xs p-1.5 rounded border" :class="getStatusClasses(step.status)">
                        <span v-html="getStatusIcon(step.status)" class="flex-shrink-0"></span>
                        <span>{{ step.description }}</span>
                    </li>
                </ul>
            </div>
        </div>
    </div>
</template>

<style scoped>
/* Add specific styles if needed, Tailwind classes handle most */

/* Ensure icons align nicely with the text */
li svg,
p svg {
    vertical-align: middle;
    /* Aligns icon vertically */
    display: inline-block;
    /* Ensures proper spacing */
}

/* Improve readability in dark mode if applicable */
.dark .border-white\/30 {
    border-color: rgba(255, 255, 255, 0.3);
}

.dark .opacity-80 {
    opacity: 0.8;
}

.dark .opacity-95 {
    opacity: 0.95;
}

/* Basic transition for the step list appearing/disappearing */
ul {
    overflow: hidden;
    /* Hide overflow during transition */
}
</style>