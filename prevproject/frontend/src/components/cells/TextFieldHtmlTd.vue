<script setup lang="ts">
import { TextValueSchema } from "../../schemas"
import ExpandableCell from "../ExpandableCell.vue"
import RenderRawHtml from "../RenderRawHtml.vue"

const props = defineProps<{
  content: Parameters<typeof TextValueSchema.parse>[0]
}>()
const parsed = TextValueSchema.parse(props.content)
</script>

<template>
  <td>
    <ExpandableCell max-height="6rem">
      <RenderRawHtml :html="parsed.value" className="rich-text-display" />
    </ExpandableCell>
  </td>
</template>
