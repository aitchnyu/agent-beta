<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import BackToTopLink from "../components/BackToTopLink.vue"
import Layout from "../components/Layout.vue"
import { AppListPropsSchema } from "../schemas"

const props = defineProps<{ props: object }>()

const p = AppListPropsSchema.parse(props.props)
</script>

<template>
  <Layout>
    <div class="container apps-applist-page">
      <h1>{{ p.collection_name }}</h1>
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th scope="col">Application</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="app in p.apps" :key="app.name">
            <td>
              <Link
                class="apps-app-link"
                :href="`/apps/a/${p.collection_name}/${app.name}/manage`"
                >{{ app.name }}</Link
              >
            </td>
          </tr>
          <tr v-if="p.apps.length === 0">
            <td class="text-center text-muted py-4">No applications.</td>
          </tr>
        </tbody>
      </table>
      <BackToTopLink href="/apps/collections"
        >Back to collections</BackToTopLink
      >
    </div>
  </Layout>
</template>
