<script setup lang="ts">
import { FileValueSchema } from "../../schemas"

const props = defineProps<{
  content: Parameters<typeof FileValueSchema.parse>[0]
}>()
const parsed = FileValueSchema.parse(props.content)
</script>

<template>
  <td>
    <a :href="parsed.value.download_url" target="_blank">{{
      parsed.value.filename
    }}</a>
  </td>
</template>
