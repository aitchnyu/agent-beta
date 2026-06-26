<script setup lang="ts">
import { DecimalValueSchema } from "../../schemas"

const props = defineProps<{
  content: Parameters<typeof DecimalValueSchema.parse>[0]
}>()
const parsed = DecimalValueSchema.parse(props.content)
</script>

<template>
  <td class="text-end">{{ parsed.value }}</td>
</template>
