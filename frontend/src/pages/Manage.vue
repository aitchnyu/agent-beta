<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import BackToTopLink from "../components/BackToTopLink.vue"
import Layout from "../components/Layout.vue"
import { ManagePropsSchema } from "../schemas"
import { appEndpointUrl, rowListUrl } from "../utils/urls"

const props = defineProps<{ props: object }>()

const p = ManagePropsSchema.parse(props.props)
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
            <td class="apps-manage-table-name">
              <Link
                class="apps-manage-table-link"
                :href="rowListUrl(p.collection_name, p.app_name, table.name)"
                >{{ table.name }}</Link
              >
            </td>
            <td class="text-end apps-manage-row-count">
              {{ table.row_count }}
            </td>
          </tr>
          <tr v-if="p.tables.length === 0">
            <td colspan="2" class="text-center text-muted py-4">No tables.</td>
          </tr>
        </tbody>
      </table>
      <div class="apps-manage-links">
        <BackToTopLink :href="`/apps/a/${p.collection_name}/list`"
          >Back to {{ p.collection_name }}</BackToTopLink
        >
        <Link
          class="apps-manage-home"
          :href="appEndpointUrl(p.collection_name, p.app_name)"
          >Open {{ p.app_name }}</Link
        >
      </div>
    </div>
  </Layout>
</template>
