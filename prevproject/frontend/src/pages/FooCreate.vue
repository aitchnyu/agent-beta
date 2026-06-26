<script setup lang="ts">
import RowForm from "../components/RowForm.vue"
import { CreateRowProps } from "../schemas"

const { props } = defineProps<{ props: CreateRowProps }>()
const p = CreateRowProps.parse(props)
</script>

<template>
  <div class="container py-4">
    <h1>Create {{ p.viewname }}</h1>
    <RowForm
      :column_names="p.column_names"
      :fields="p.fields"
      :viewname="p.viewname"
      mode="create"
      :submit-url="`/${p.viewname}/create`"
      :details-base-url="`/${p.viewname}`"
    />
  </div>
</template>
