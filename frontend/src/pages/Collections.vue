<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import Layout from "../components/Layout.vue"
import { CollectionsPropsSchema } from "../schemas"

const props = defineProps<{
  collections: { name: string }[]
}>()

const p = CollectionsPropsSchema.parse(props)
</script>

<template>
  <Layout>
    <div class="container apps-collections-page">
      <h1>Application Collections</h1>
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th scope="col">Name</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="collection in p.collections" :key="collection.name">
            <td>
              <Link
                class="apps-collection-link"
                :href="`/apps/a/${collection.name}/list`"
                >{{ collection.name }}</Link
              >
            </td>
          </tr>
          <tr v-if="p.collections.length === 0">
            <td class="text-center text-muted py-4">No collections.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </Layout>
</template>
