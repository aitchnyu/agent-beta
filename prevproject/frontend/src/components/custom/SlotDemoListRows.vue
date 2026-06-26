<script setup lang="ts">
import ListRowsContent from "../ListRowsContent.vue"
import DiffFilter from "./DiffFilter.vue"

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- Inertia props are untyped
const { props } = defineProps<{ props: Record<string, any> }>()
</script>

<template>
  <ListRowsContent :props="props">
    <template #extra-filters="{ schema }">
      <DiffFilter
        :wrapper="schema"
        :currentValue="(props.list_page_schema as Record<string, unknown>).diff"
      />
    </template>
  </ListRowsContent>
</template>
