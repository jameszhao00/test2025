<script setup lang="ts">
// Import the Todo type from the generated api-client models
import type { Todo } from '@/api-client'; // Using '@' alias for src

// Define props received from parent (TodoList.vue) - uses the generated Todo type
defineProps<{
  todo: Todo
}>()

// Define events emitted up to parent (TodoList.vue)
// No need to pass data, the parent (TodoList) knows the ID
const emit = defineEmits(['toggle', 'delete'])

</script>

<template>
  <li :class="{ done: todo.done }" class="todo-item">
    <input
      type="checkbox"
      :checked="todo.done"
      @change="emit('toggle')"
      class="todo-checkbox"
      :aria-label="'Mark ' + todo.text + ' as ' + (todo.done ? 'not done' : 'done')"
    />
    <span class="todo-text" @click="emit('toggle')">{{ todo.text }}</span>
    <button @click="emit('delete')" class="delete-button" :aria-label="'Delete ' + todo.text">❌</button>
  </li>
</template>

<style scoped>
.todo-item {
  display: flex;
  align-items: center;
  background-color: #fff;
  padding: 0.8rem 1rem;
  border-bottom: 1px solid #eee;
  transition: background-color 0.2s ease;
}

.todo-item:last-child {
  border-bottom: none;
}

.todo-item.done {
  background-color: #e8f5e9; /* Light green background for done items */
}

.todo-item.done .todo-text {
  text-decoration: line-through;
  color: #888;
}

.todo-checkbox {
  margin-right: 0.8rem;
  cursor: pointer;
  width: 18px; /* Make checkbox slightly larger */
  height: 18px;
}

.todo-text {
  flex-grow: 1;
  cursor: pointer; /* Allow clicking text to toggle */
  color: #333;
  font-size: 1rem;
  /* Prevent text selection on rapid clicks */
  user-select: none;
}

.delete-button {
  background: none;
  border: none;
  color: #d9534f; /* Red color for delete */
  cursor: pointer;
  font-size: 1rem; /* Adjust size if needed */
  padding: 0 0 0 0.5rem; /* Add some space */
  opacity: 0.6;
  transition: opacity 0.2s ease;
}

.delete-button:hover {
  opacity: 1;
}
</style>