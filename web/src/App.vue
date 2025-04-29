<script setup lang="ts">
import { ref, onMounted } from 'vue'
import TodoForm from './components/TodoForm.vue'
import TodoList from './components/TodoList.vue'
import ErrorMessage from './components/ErrorMessage.vue'
// Import the generated API client and models
import { DefaultApi, Configuration, ResponseError } from '@/api-client' // Using '@' alias for src
import type { Todo, CreateTodo } from '@/api-client' // Using 'import type' for types

// --- API Client Setup ---
// Configure the base path if needed, otherwise it defaults to http://localhost
// If your API is served from the same origin as the frontend (e.g., /api),
// you might set basePath to '' or '/'. For this example, we assume relative paths work.
const config = new Configuration({ basePath: '' }); // Adjust basePath if necessary
const apiClient = new DefaultApi(config);

// Reactive state - uses the imported Todo type from the api-client
const todos = ref<Todo[]>([])
const error = ref<string | null>(null)

// --- API Interaction Logic (Using the generated client) ---

async function fetchTodos() {
  error.value = null
  try {
    // Use the generated client method
    const fetchedTodos = await apiClient.getTodosApiTodosGet();
    todos.value = fetchedTodos;
  } catch (e) {
    console.error('Failed to fetch todos:', e)
    error.value = await getErrorMessage(e, 'Failed to load todos. Is the backend running?');
  }
}

// Triggered by event from TodoForm
async function handleAddTodo(text: string) {
  error.value = null
  try {
    // Prepare the request body according to the CreateTodo model
    const todoToAdd: CreateTodo = { text };
    // Use the generated client method
    const newTodo = await apiClient.createTodoApiTodosPost({ createTodo: todoToAdd });
    todos.value.push(newTodo);
  } catch (e) {
    console.error('Failed to add todo:', e)
    error.value = await getErrorMessage(e, 'Failed to add todo.');
  }
}

// Triggered by event from TodoList/TodoItem
async function handleToggleTodo(todoId: number) {
  error.value = null
  try {
    // Use the generated client method
    const updatedTodo = await apiClient.toggleTodoDoneApiTodosTodoIdTogglePut({ todoId });
    const index = todos.value.findIndex(t => t.id === todoId)
    if (index !== -1) {
      // Update the local state with the response
      // It's safer to replace the whole object or update all relevant fields
      todos.value[index] = updatedTodo;
      // Or specifically update if only 'done' changes:
      // todos.value[index].done = updatedTodo.done
    }
  } catch (e) {
    console.error('Failed to toggle todo:', e)
    error.value = await getErrorMessage(e, 'Failed to update todo status.');
  }
}

// Triggered by event from TodoList/TodoItem
async function handleDeleteTodo(todoId: number) {
  error.value = null
  try {
    // Use the generated client method (returns void on success)
    await apiClient.deleteTodoApiTodosTodoIdDelete({ todoId });
    // Update local state on success
    todos.value = todos.value.filter(t => t.id !== todoId)
  } catch (e) {
    console.error('Failed to delete todo:', e)
    error.value = await getErrorMessage(e, 'Failed to delete todo.');
  }
}

// Helper function to extract error messages
async function getErrorMessage(error: unknown, defaultMessage: string): Promise<string> {
  if (error instanceof ResponseError) {
    try {
      // Attempt to parse the response body as JSON for detailed errors (like HTTPValidationError)
      const errorBody = await error.response.json();
      // FastAPI validation errors often have a 'detail' field
      if (errorBody.detail) {
        // If detail is an array (like from HTTPValidationError), format it
        if (Array.isArray(errorBody.detail)) {
          return errorBody.detail.map((d: any) => `${d.loc.join('.')} - ${d.msg}`).join('; ');
        }
        // If detail is a string
        return String(errorBody.detail);
      }
    } catch (parseError) {
      // If parsing fails, fall back to status text or default message
      return `${error.response.status}: ${error.response.statusText || defaultMessage}`;
    }
    // Fallback if parsing succeeded but no 'detail' field found
    return `${error.response.status}: ${error.response.statusText || defaultMessage}`;
  } else if (error instanceof Error) {
    return error.message;
  }
  return defaultMessage;
}


// --- Lifecycle Hook ---
onMounted(fetchTodos)
</script>

<template>
  <div class="todo-app">
    <h1>My ToDo List</h1>

    <TodoForm @add-todo="handleAddTodo" />

    <ErrorMessage :message="error" />

    <TodoList :todos="todos" @toggle-todo="handleToggleTodo" @delete-todo="handleDeleteTodo" />

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