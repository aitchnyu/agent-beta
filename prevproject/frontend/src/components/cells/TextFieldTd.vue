<script setup lang="ts">
import { TextValueSchema } from "../../schemas"
import ExpandableCell from "../ExpandableCell.vue"

const props = defineProps<{
  content: Parameters<typeof TextValueSchema.parse>[0]
}>()
const parsed = TextValueSchema.parse(props.content)
const flatText = String(parsed.value)
</script>

<template>
  <td>
    <ExpandableCell max-height="1.5rem">
      {{ flatText }}
    </ExpandableCell>
  </td>
</template>
