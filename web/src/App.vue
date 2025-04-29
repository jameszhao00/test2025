<script setup>
import { ref } from 'vue'
import axios from 'axios'

const message = ref('')

const fetchMessage = async () => {
  try {
    const response = await axios.get('/api/hello')
    message.value = response.data.message
  } catch (error) {
    message.value = 'Error fetching message'
  }
}
</script>

<template>
  <div class="app">
    <h1>Vue + FastAPI Demo</h1>
    <button @click="fetchMessage">Get Message from API</button>
    <p v-if="message">{{ message }}</p>
  </div>
</template>

<style scoped>
.app {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  text-align: center;
}

button {
  background-color: #42b883;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  margin: 20px 0;
}

button:hover {
  background-color: #3aa876;
}
</style>
