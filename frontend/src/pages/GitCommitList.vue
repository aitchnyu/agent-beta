<template>
  <PageTitle value="Commits" />
  <RepoNav />
  <h3>Commits</h3>
  <p v-if="!data.commits.length" class="text-muted">No commits.</p>
  <ul v-else class="list-group">
    <li v-for="c in data.commits" :key="c.sha" class="list-group-item">
      <Link :href="`/git/commits/${shortSha(c.sha)}`" prefetch="hover">{{
        c.subject
      }}</Link>
      <br />
      <small class="text-muted"
        ><code>{{ shortSha(c.sha) }}</code> · <HumanizedTime :ms="c.date"
      /></small>
    </li>
  </ul>
  <div
    v-if="data.pagination.total_pages > 1"
    class="d-flex align-items-center mt-2"
  >
    <Link :href="buildUrl(1)" class="btn btn-outline-primary btn-sm me-2">
      First
    </Link>
    <Link
      v-if="currentPage > 1"
      :href="buildUrl(currentPage - 1)"
      class="btn btn-secondary btn-sm me-2"
    >
      Prev
    </Link>
    <Link
      v-if="currentPage < data.pagination.total_pages"
      :href="buildUrl(currentPage + 1)"
      class="btn btn-secondary btn-sm"
    >
      Next
    </Link>
    <span class="text-muted ms-2"
      >Page {{ data.pagination.page }} of {{ data.pagination.total_pages }} ({{
        data.pagination.total_count
      }}
      commits)</span
    >
  </div>
  <p v-else class="mt-2 text-muted">
    {{ data.pagination.total_count }} commits
  </p>
</template>

<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import HumanizedTime from "../components/HumanizedTime.vue"
import PageTitle from "../components/PageTitle.vue"
import RepoNav from "../components/RepoNav.vue"
import { GitCommitListPropsSchema } from "../schemas"
import { shortSha } from "../utils/git"

const props = defineProps<{ props: object }>()
const data = GitCommitListPropsSchema.parse(props.props)
const currentPage = data.pagination.page

function buildUrl(page: number) {
  return page > 1 ? `/git/commits?page=${page}` : "/git/commits"
}
</script>
