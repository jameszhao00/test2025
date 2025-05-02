<script setup lang="ts">
import { computed } from 'vue' // Removed ref and watch as toggle logic is removed
// Import the necessary types from the API client
import type {
    WorkflowPhase,
    WorkflowStep,
    WorkflowStatus,
} from '@/api-client'

// Define props
const props = defineProps<{
    workflowState: WorkflowPhase[] | null // Expects an array of WorkflowPhase or null
}>()

// --- State for Collapsible Phases REMOVED ---
// No longer needed as phases are always expanded and the icon is gone.

// --- Helper Functions for Styling and Icons ---

// Helper function to get Tailwind classes based on status (Light theme only)
const getStatusClasses = (status: WorkflowStatus | string) => { // Accept string for safety
    switch (status) {
        case 'done':
            // Subtle green for completed
            return 'bg-green-50 text-green-700'
        case 'in_progress':
            // Brighter yellow/amber and slight animation for active steps
            return 'bg-yellow-100 text-yellow-800 font-medium animate-pulse-subtle'
        case 'todo':
        default:
            // Very subtle gray for pending steps
            return 'text-gray-600'
    }
}

// Helper function to get an SVG icon based on status (Light theme only)
const getStatusIcon = (status: WorkflowStatus | string) => { // Accept string for safety
    switch (status) {
        case 'done':
            return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5 mr-1.5 flex-shrink-0 text-green-500"><path fill-rule="evenodd" d="M8 15A7 7 0 1 0 8 1a7 7 0 0 0 0 14Zm3.857-9.809a.75.75 0 0 0-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 1 0-1.06 1.061l2.5 2.5a.75.75 0 0 0 1.137-.089l4-5.5Z" clip-rule="evenodd" /></svg>`
        case 'in_progress':
            // Animated spinner
            return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5 mr-1.5 flex-shrink-0 text-yellow-600 animate-spin-slow"><path d="M8 1.5a6.5 6.5 0 1 0 5.134 10.866l-1.41-.47a5 5 0 1 1-3.724-8.896V4A.5.5 0 0 1 8.5 4v1.504a6.5 6.5 0 0 0-.5-.004Z"/></svg>`
        case 'todo':
        default:
            // Circle outline
            return `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" stroke-width="1.5" stroke="currentColor" class="w-3.5 h-3.5 mr-1.5 flex-shrink-0 text-gray-400"><path stroke-linecap="round" stroke-linejoin="round" d="M14 8A6 6 0 1 1 2 8a6 6 0 0 1 12 0Z" /></svg>`
    }
}

// Check if a phase contains any 'in_progress' step for highlighting the phase title
const isPhaseActive = (phase: WorkflowPhase): boolean => {
    return phase.steps.some(step => step.status === 'in_progress');
}

</script>

<template>
    <div v-if="workflowState"
        class="w-128 bg-white p-3  overflow-y-auto custom-scrollbar">
        <h3 class="text-base font-semibold mb-3 text-gray-700 pb-1 text-center">
            Current Plan
        </h3>
        <div v-if="workflowState && workflowState.length > 0" class="space-y-3">
            <div v-for="(phase, phaseIndex) in workflowState" :key="`phase-${phaseIndex}`" class="space-y-1">
                <p class="font-medium text-lg text-gray-600 flex items-center text-center select-none py-1.5 px-2 rounded w-full bg-gray-50"
                    :class="{ 'text-yellow-700 font-semibold !bg-yellow-100': isPhaseActive(phase) }"> <span
                        class="flex-grow">{{ phaseIndex + 1 }}. {{ phase.description }}</span>
                </p>
                <div class="space-y-1.5">
                    <div v-for="(step, stepIndex) in phase.steps" :key="`phase-${phaseIndex}-step-${stepIndex}`"
                        class="flex items-center text-sm p-1.5 rounded w-full" :class="getStatusClasses(step.status)">
                        <span v-html="getStatusIcon(step.status)" class="flex-shrink-0"></span>
                        <span class="flex-grow leading-snug">{{ step.description }}</span>
                    </div>
                </div>
            </div>
        </div>
        <div v-else class="text-sm text-gray-500 italic mt-2">
            No plan details available.
        </div>
    </div>
    <div v-else class="w-128 bg-white p-3">
        <h3 class="text-base font-semibold mb-3 text-gray-700 pb-1 text-center">
            Current Plan
        </h3>
        <p class="text-sm text-gray-500 italic">No plan generated yet.</p>
    </div>
</template>

<style scoped>
/* Scoped styles for fine-tuning */

/* Center icons vertically */
li svg {
    display: inline-block;
}

/* Ensure list has no extra padding */
ul {
    padding-left: 0;
    /* Reset default padding */
    /* overflow: hidden; */
    /* No longer needed without transitions */
}

/* Minimalist Scrollbar (Light theme only) */
.custom-scrollbar::-webkit-scrollbar {
    width: 5px;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
    background: #e5e7eb;
    /* Even lighter gray */
    border-radius: 10px;
}

/* Animations defined in tailwind.config.js */
/* Ensure these classes are available or define them here if not using config */
/*
@keyframes pulse-subtle { ... }
.animate-pulse-subtle { ... }
@keyframes spin-slow { ... }
.animate-spin-slow { ... }
*/
</style>
