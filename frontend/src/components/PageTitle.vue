<script setup lang="ts">
import { onMounted, watch } from "vue"

const props = withDefaults(defineProps<{ value?: string }>(), {
  value: "App",
})

function setTitle() {
  document.title = props.value
}

onMounted(setTitle)
watch(() => props.value, setTitle)
</script>

<template></template>
