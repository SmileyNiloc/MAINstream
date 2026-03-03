<template>
  <h3>Welcome to CompAIr!</h3>
  <p>This is the frontend of the CompAIr project.</p>
  <p>It is built with Vue.js and communicates with the backend API.</p>
  <p>Below is a test component that fetches a message from the backend API:</p>
  <TestView />
</template>

<script setup>
import TestView from "./components/TestView.vue";
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  margin-top: 60px;
}
</style>
