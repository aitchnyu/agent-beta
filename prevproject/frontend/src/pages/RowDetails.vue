<script setup lang="ts">
import RowDetailsContent from "../components/RowDetailsContent.vue"

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- Inertia props are untyped
const { props } = defineProps<{ props: Record<string, any> }>()
</script>

<template>
  <RowDetailsContent :props="props" />
</template>
