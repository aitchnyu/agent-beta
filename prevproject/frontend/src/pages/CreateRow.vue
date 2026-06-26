<script setup lang="ts">
import Layout from "../components/Layout.vue"
import RowForm from "../components/RowForm.vue"
import { CreateRowProps } from "../schemas"

interface Props {
  props: CreateRowProps
}

const { props } = defineProps<Props>()

const p = CreateRowProps.parse(props)
</script>

<template>
  <Layout :user="p.user">
    <div class="container">
      <h1>Create {{ p.viewname }}</h1>
      <RowForm
        :column_names="p.column_names"
        :fields="p.fields"
        :viewname="p.viewname"
        mode="create"
      />
    </div>
  </Layout>
</template>
