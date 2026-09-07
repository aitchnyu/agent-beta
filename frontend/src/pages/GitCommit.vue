<template>
  <PageTitle
    :value="'Commit ' + data.commit.short_sha + ' ' + data.commit.subject"
  />
  <GitNav />
  <h1>
    <code>{{ data.commit.short_sha }}</code> {{ data.commit.subject }}
  </h1>
  <p class="text-muted">
    {{ data.commit.author }} · <HumanizedTime :ms="data.commit.date" />
  </p>
  <p v-if="!data.files.length" class="text-muted">No changed files.</p>
  <ul v-else class="list-unstyled mb-0">
    <li
      v-for="f in data.files"
      :key="f.path"
      class="d-flex align-items-baseline"
    >
      <code class="git-status" :class="statusClass(f.status)">{{
        statusWord(f.status)
      }}</code>
      <Link
        :class="{ 'text-decoration-line-through': f.status === 'deleted' }"
        :href="`/git/commits/${data.commit.short_sha}/${f.path}`"
        ><code>{{ f.path }}</code></Link
      >
      <!-- No "file" link for deleted paths — /files/main/<path> would 404. -->
      <Link
        v-if="f.status !== 'deleted'"
        class="git-file-link ms-2"
        :href="fileUrl(`main/${f.path}`)"
        >file</Link
      >
    </li>
  </ul>
</template>

<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import HumanizedTime from "../components/HumanizedTime.vue"
import PageTitle from "../components/PageTitle.vue"
import GitNav from "../components/GitNav.vue"
import { GitCommitPropsSchema } from "../schemas"
import { fileUrl } from "../utils/files"

const props = defineProps<{ props: object }>()
const data = GitCommitPropsSchema.parse(props.props)

// Same new/mod/del words + colors as the uncommitted list (commits read
// main/ only, so file links prefix main/).
function statusWord(status: string): string {
  switch (status) {
    case "added":
      return "new"
    case "modified":
      return "mod"
    case "deleted":
      return "del"
    default:
      return "?"
  }
}

function statusClass(status: string): string {
  if (status === "added") return "text-success"
  if (status === "modified") return "text-warning"
  if (status === "deleted") return "text-danger"
  return ""
}
</script>
