<template>
  <Layout>
    <h1>Uncommitted changes</h1>
    <p v-if="!files.length" class="text-muted">No uncommitted files.</p>
    <ul v-else class="list-group">
      <li
        v-for="f in files"
        :key="f.path"
        class="list-group-item d-flex justify-content-between align-items-center"
      >
        <Link :href="`/git/uncommitted/${f.path}`"
          ><code>{{ f.path }}</code></Link
        >
        <span class="badge bg-secondary">{{ f.status }}</span>
      </li>
    </ul>
  </Layout>
</template>

<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import Layout from "../components/Layout.vue"
import { GitUncommittedPropsSchema } from "../schemas"

const { props } = defineProps<{ props: object }>()
const files = GitUncommittedPropsSchema.parse(props).files
</script>
