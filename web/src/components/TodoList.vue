<script setup lang="ts">
import TodoItem from './TodoItem.vue'
// Import the Todo type from the generated api-client models
import type { Todo } from '@/api-client'; // Using '@' alias for src

// Define props received from parent (App.vue) - uses the generated Todo type
defineProps<{
  todos: Todo[]
}>()

// Define events emitted up to parent (App.vue)
// These events are just passed through from TodoItem
const emit = defineEmits(['toggle-todo', 'delete-todo'])

// Emit the ID of the todo to be toggled/deleted
function handleToggle(id: number) {
    emit('toggle-todo', id)
}

function handleDelete(id: number) {
    emit('delete-todo', id)
}

</script>

<template>
  <ul class="todo-list">
    <TodoItem
      v-for="todo in todos"
      :key="todo.id"
      :todo="todo"
      @toggle="handleToggle(todo.id)"
      @delete="handleDelete(todo.id)"
    />
  </ul>
</template>

<style scoped>
.todo-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
</style>