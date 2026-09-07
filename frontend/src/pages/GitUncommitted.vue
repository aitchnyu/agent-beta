<template>
  <PageTitle value="Uncommitted changes" />
  <GitNav />
  <h1>Uncommitted changes</h1>
  <section v-for="wt in sections" :key="wt.name" class="mb-4">
    <h2 class="h6 mb-1">{{ wt.name }}</h2>
    <ul v-if="wt.files.length" class="list-unstyled mb-0">
      <li
        v-for="f in wt.files"
        :key="f.path"
        class="d-flex align-items-baseline"
      >
        <code class="git-status" :class="statusClass(f.status)">{{
          statusWord(f.status)
        }}</code>
        <Link
          :class="{ 'text-decoration-line-through': f.status === 'deleted' }"
          :href="`/git/uncommitted/${wt.name}/${f.path}`"
          ><code>{{ f.path }}</code></Link
        >
        <!-- No "file" link for deleted paths — the file no longer exists and
             /files/<worktree>/<path> would 404. -->
        <Link
          v-if="f.status !== 'deleted'"
          class="git-file-link ms-2"
          :href="fileUrl(`${wt.name}/${f.path}`)"
          >file</Link
        >
      </li>
    </ul>
    <p v-else class="text-muted mb-0">No changes.</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Link } from "@inertiajs/vue3"
import GitNav from "../components/GitNav.vue"
import PageTitle from "../components/PageTitle.vue"
import { GitUncommittedPropsSchema } from "../schemas"
import { fileUrl } from "../utils/files"

const props = defineProps<{ props: object }>()
const data = GitUncommittedPropsSchema.parse(props.props)

// main is mandatory; scratch is optional (null when scratch/ isn't on disk yet).
const sections = computed(() => {
  const list: { name: string; files: typeof data.main_files }[] = [
    { name: "main", files: data.main_files },
  ]
  if (data.scratch_files)
    list.push({ name: "scratch", files: data.scratch_files })
  return list
})

// new/mod/del + colors to the left of the path — the backend statuses
// (untracked|added|modified|deleted) map here, not in the API: untracked and
// added are both "new". del keeps the filename strikethrough.
function statusWord(status: string): string {
  switch (status) {
    case "untracked":
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
  if (status === "untracked" || status === "added") return "text-success"
  if (status === "modified") return "text-warning"
  if (status === "deleted") return "text-danger"
  return ""
}
</script>
