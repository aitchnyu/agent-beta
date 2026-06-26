<script setup lang="ts">
import RowForm from "../components/RowForm.vue"
import { UpdateRowProps } from "../schemas"

const { props } = defineProps<{ props: UpdateRowProps }>()
const p = UpdateRowProps.parse(props)
</script>

<template>
  <div class="container py-4">
    <h1>Update {{ p.viewname }}</h1>
    <RowForm
      :column_names="p.column_names"
      :fields="p.fields"
      :viewname="p.viewname"
      mode="update"
      :row_id="p.row_id"
      :submit-url="`/${p.viewname}/update/${p.row_id}`"
      :details-base-url="`/${p.viewname}`"
    />
  </div>
</template>
