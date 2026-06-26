<script setup lang="ts">
import { computed } from "vue"
import { router } from "@inertiajs/vue3"
import Layout from "../components/Layout.vue"
import RowForm from "../components/RowForm.vue"
import { UpdateRowProps } from "../schemas"
import { popStartEdit } from "../utils/startEdit"
import { rowDetailsUrl } from "../utils/urls"

interface Props {
  props: UpdateRowProps
}

const { props } = defineProps<Props>()

const p = UpdateRowProps.parse(props)

const pendingField = popStartEdit()
const focusedField = computed(() => pendingField ?? p.column_names[0] ?? null)

function cancelEdit() {
  router.visit(rowDetailsUrl(p.viewname, p.row_id))
}
</script>

<template>
  <Layout :user="p.user">
    <div class="container">
      <h1>Update {{ p.viewname }}</h1>
      <RowForm
        :column_names="p.column_names"
        :fields="p.fields"
        :viewname="p.viewname"
        mode="update"
        :row_id="p.row_id"
        :focused-field="focusedField"
        :on-cancel="cancelEdit"
      />
    </div>
  </Layout>
</template>
