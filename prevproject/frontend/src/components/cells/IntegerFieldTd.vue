<script setup lang="ts">
import { IntegerValueSchema } from "../../schemas"

const props = defineProps<{
  content: Parameters<typeof IntegerValueSchema.parse>[0]
}>()
const parsed = IntegerValueSchema.parse(props.content)
const isChoice = typeof parsed.value === "string"
</script>

<template>
  <td :class="{ 'text-end': !isChoice }">{{ parsed.value }}</td>
</template>
