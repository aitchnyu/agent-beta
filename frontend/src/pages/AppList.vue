<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import Layout from "../components/Layout.vue"
import { AppListPropsSchema } from "../schemas"
import { appEndpointUrl } from "../utils/urls"

const props = defineProps<{ props: object }>()

const p = AppListPropsSchema.parse(props.props)
</script>

<template>
  <Layout>
    <div class="container apps-applist-page">
      <h1>Applications</h1>
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th scope="col">Application</th>
            <th scope="col" class="text-end">Manage</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="app in p.apps" :key="app.name">
            <td>
              <!-- Plain <a>, not Inertia <Link>: /apps/<app> is a different
                   Inertia bundle, so a client-side visit would try to render the
                   app's component in the host bundle and fail. A full load fetches
                   the app's own main.js. First link opens the app's home. -->
              <a class="apps-app-link" :href="appEndpointUrl(app.name)">{{
                app.name
              }}</a>
            </td>
            <td class="text-end">
              <Link class="apps-app-manage" :href="`/manage/apps/${app.name}`"
                >Manage</Link
              >
            </td>
          </tr>
          <tr v-if="p.apps.length === 0">
            <td colspan="2" class="text-center text-muted py-4">
              No applications.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </Layout>
</template>
