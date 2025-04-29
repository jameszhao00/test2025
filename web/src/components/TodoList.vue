<script setup lang="ts">
import TodoItem from './TodoItem.vue'
import type { Todo } from '../App.vue'; // Import the Todo type from App.vue

// Define props received from parent (App.vue)
defineProps<{
  todos: Todo[]
}>()

// Define events emitted up to parent (App.vue)
// These events are just passed through from TodoItem
const emit = defineEmits(['toggle-todo', 'delete-todo'])

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