<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import { ForeignKeyValueSchema } from "../../schemas"
import { rowDetailsUrl } from "../../utils/urls"

const props = defineProps<{
  content: Parameters<typeof ForeignKeyValueSchema.parse>[0]
}>()
const parsed = ForeignKeyValueSchema.parse(props.content)
const hrefUrl = rowDetailsUrl(parsed.value.viewname, parsed.value.id)
</script>

<template>
  <Link :href="hrefUrl" target="_blank" @dblclick.stop.prevent>
    {{ parsed.value.title }}
  </Link>
</template>
