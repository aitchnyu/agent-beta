<script setup lang="ts">
import { NullValueSchema } from "../../schemas"

const props = defineProps<{
  content: Parameters<typeof NullValueSchema.parse>[0]
}>()
NullValueSchema.parse(props.content)
</script>

<template>
  <td><span class="text-muted">—</span></td>
</template>
