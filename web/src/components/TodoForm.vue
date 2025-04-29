<script setup lang="ts">
import { ref } from 'vue'

// Define the event(s) this component emits
const emit = defineEmits(['add-todo'])

const newTodoText = ref('')

function handleSubmit() {
  const text = newTodoText.value.trim()
  if (text) {
    emit('add-todo', text) // Emit the event with the text
    newTodoText.value = '' // Clear input
  }
}
</script>

<template>
  <form @submit.prevent="handleSubmit" class="add-todo-form">
    <input
      type="text"
      v-model="newTodoText"
      placeholder="What needs to be done?"
      required
    />
    <button type="submit">Add ToDo</button>
  </form>
</template>

<style scoped>
.add-todo-form {
  display: flex;
  margin-bottom: 1.5rem;
}

.add-todo-form input[type="text"] {
  flex-grow: 1;
  padding: 0.8rem;
  border: 1px solid #ccc;
  border-radius: 4px 0 0 4px;
  font-size: 1rem;
}

.add-todo-form button {
  padding: 0.8rem 1.2rem;
  background-color: #5cb85c;
  color: white;
  border: none;
  border-radius: 0 4px 4px 0;
  cursor: pointer;
  font-size: 1rem;
  transition: background-color 0.2s ease;
}

.add-todo-form button:hover {
  background-color: #4cae4c;
}
</style>