<script setup lang="ts">
import { ref, onMounted } from 'vue'
import TodoForm from './components/TodoForm.vue'
import TodoList from './components/TodoList.vue'
import ErrorMessage from './components/ErrorMessage.vue' // Optional error component

// Define the structure of a Todo item
export interface Todo {
  id: number
  text: string
  done: boolean
}

// Reactive state
const todos = ref<Todo[]>([])
const error = ref<string | null>(null)

// --- API Interaction Logic (Remains in the main component) ---

async function fetchTodos() {
  error.value = null
  try {
    const response = await fetch('/api/todos')
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    todos.value = await response.json()
  } catch (e) {
    console.error('Failed to fetch todos:', e)
    error.value = 'Failed to load todos. Is the backend running?'
  }
}

// Triggered by event from TodoForm
async function handleAddTodo(text: string) {
  error.value = null
  try {
    const response = await fetch('/api/todos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    const newTodo = await response.json()
    todos.value.push(newTodo)
  } catch (e) {
    console.error('Failed to add todo:', e)
    error.value = 'Failed to add todo.'
  }
}

// Triggered by event from TodoList/TodoItem
async function handleToggleTodo(todoId: number) {
  error.value = null
  try {
    const response = await fetch(`/api/todos/${todoId}/toggle`, { method: 'PUT' })
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    const updatedTodo = await response.json()
    const index = todos.value.findIndex(t => t.id === todoId)
    if (index !== -1) {
      todos.value[index].done = updatedTodo.done
    }
  } catch (e) {
    console.error('Failed to toggle todo:', e)
    error.value = 'Failed to update todo status.'
  }
}

// Triggered by event from TodoList/TodoItem
async function handleDeleteTodo(todoId: number) {
  error.value = null
  try {
    const response = await fetch(`/api/todos/${todoId}`, { method: 'DELETE' })
    if (!response.ok && response.status !== 204) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    todos.value = todos.value.filter(t => t.id !== todoId)
  } catch (e) {
    console.error('Failed to delete todo:', e)
    error.value = 'Failed to delete todo.'
  }
}

// --- Lifecycle Hook ---
onMounted(fetchTodos)
</script>

<template>
  <div class="todo-app">
    <h1>My ToDo List</h1>

    <TodoForm @add-todo="handleAddTodo" />

    <ErrorMessage :message="error" />

    <TodoList
      :todos="todos"
      @toggle-todo="handleToggleTodo"
      @delete-todo="handleDeleteTodo"
    />

    <p v-if="todos.length === 0 && !error">No todos yet!</p>
  </div>
</template>

<style scoped>
/* Styles specific to App.vue layout */
.todo-app {
  max-width: 600px;
  margin: 2rem auto;
  padding: 2rem;
  font-family: sans-serif;
  background-color: #f4f4f4;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

h1 {
  text-align: center;
  color: #333;
  margin-bottom: 1.5rem;
}

/* Styles for form, list items etc. are moved to their respective components */
</style>