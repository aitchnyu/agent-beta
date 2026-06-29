<script setup lang="ts">
import Layout from "../components/Layout.vue"
import { ManagePropsSchema } from "../schemas"

const props = defineProps<{
  collection_name: string
  app_name: string
  tables: { name: string; row_count: number }[]
}>()

const p = ManagePropsSchema.parse(props)
</script>

<template>
  <Layout>
    <div class="container apps-manage-page">
      <h1>{{ p.app_name }}</h1>
      <p class="text-muted">{{ p.collection_name }}</p>
      <table class="table table-sm align-middle apps-manage-table">
        <thead>
          <tr>
            <th scope="col">Table</th>
            <th scope="col" class="text-end">Rows</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="table in p.tables" :key="table.name">
            <td class="apps-manage-table-name">{{ table.name }}</td>
            <td class="text-end apps-manage-row-count">
              {{ table.row_count }}
            </td>
          </tr>
          <tr v-if="p.tables.length === 0">
            <td colspan="2" class="text-center text-muted py-4">No tables.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </Layout>
</template>
