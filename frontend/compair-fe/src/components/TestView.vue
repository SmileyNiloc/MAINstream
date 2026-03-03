<template>
  <h3>{{ msg }}</h3>
</template>

<script setup>
import api from "@/api";
import { ref, onMounted } from "vue";
const msg = ref("Waiting for response...");

onMounted(async () => {
  try {
    const response = await api.get("/api/hello");
    if(response.data) {
      msg.value = response.data.message;
    }
  } catch (error) {
    msg.value = "Error fetching response";
  }
});
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
h3 {
  margin: 40px 0 0;
}
</style>
