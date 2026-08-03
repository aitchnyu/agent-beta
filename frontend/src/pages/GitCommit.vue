<template>
  <Layout>
    <GitNav />
    <h1>
      <code>{{ data.commit.short_sha }}</code> {{ data.commit.subject }}
    </h1>
    <p class="text-muted">
      {{ data.commit.author }} · <HumanizedTime :ms="data.commit.date" />
    </p>
    <p v-if="!data.files.length" class="text-muted">No changed files.</p>
    <ul v-else class="list-group">
      <li
        v-for="f in data.files"
        :key="f.path"
        class="list-group-item d-flex justify-content-between align-items-center"
      >
        <Link :href="`/git/commits/${data.commit.short_sha}/${f.path}`">
          <code>{{ f.path }}</code>
        </Link>
        <span class="badge bg-secondary">{{ f.status }}</span>
      </li>
    </ul>
  </Layout>
</template>

<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import HumanizedTime from "../components/HumanizedTime.vue"
import Layout from "../components/Layout.vue"
import GitNav from "../components/GitNav.vue"
import { GitCommitPropsSchema } from "../schemas"

const props = defineProps<{ props: object }>()
const data = GitCommitPropsSchema.parse(props.props)
</script>
