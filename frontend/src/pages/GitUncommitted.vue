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
        :class="statusClass(f.status)"
      >
        <code class="git-letter">{{ statusLetter(f.status) }}</code>
        <Link
          :class="statusClass(f.status)"
          :href="`/git/uncommitted/${wt.name}/${f.path}`"
          ><code>{{ f.path }}</code></Link
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

// U/M/A/D to the left of the path — git-status style.
function statusLetter(status: string): string {
  switch (status) {
    case "untracked":
      return "U"
    case "modified":
      return "M"
    case "added":
      return "A"
    case "deleted":
      return "D"
    default:
      return "?"
  }
}

// Untracked → grey, deleted → strikethrough, added/modified → black (default).
function statusClass(status: string): string {
  if (status === "untracked") return "text-muted"
  if (status === "deleted") return "text-decoration-line-through"
  return ""
}
</script>
