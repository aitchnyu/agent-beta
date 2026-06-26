<script setup lang="ts">
import { CharValueSchema } from "../../schemas"

const props = defineProps<{
  content: Parameters<typeof CharValueSchema.parse>[0]
}>()
const parsed = CharValueSchema.parse(props.content)
</script>

<template>
  <td>{{ parsed.value }}</td>
</template>
