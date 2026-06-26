<script setup lang="ts">
import { DateTimeValueSchema } from "../../schemas"

const props = defineProps<{
  content: Parameters<typeof DateTimeValueSchema.parse>[0]
}>()
const parsed = DateTimeValueSchema.parse(props.content)
</script>

<template>
  <td>
    {{ new Date(parsed.value).toLocaleDateString() }}
    {{ new Date(parsed.value).toLocaleTimeString() }}
  </td>
</template>
