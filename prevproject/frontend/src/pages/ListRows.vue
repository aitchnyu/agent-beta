<script setup lang="ts">
import ListRowsContent from "../components/ListRowsContent.vue"

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- Inertia props are untyped
const { props } = defineProps<{ props: Record<string, any> }>()
</script>

<template>
  <ListRowsContent :props="props" />
</template>
