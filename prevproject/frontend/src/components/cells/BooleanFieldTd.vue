<script setup lang="ts">
import { BooleanValueSchema } from "../../schemas"

const props = defineProps<{
  content: Parameters<typeof BooleanValueSchema.parse>[0]
}>()
const parsed = BooleanValueSchema.parse(props.content)
</script>

<template>
  <td>{{ parsed.value ? "Yes" : "No" }}</td>
</template>
