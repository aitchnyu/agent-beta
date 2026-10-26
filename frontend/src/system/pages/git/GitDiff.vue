<template>
  <PageTitle :value="data.title" />
  <h3>
    {{ data.title }}
    <!-- Muted companion: this diff's path in the file view. Deleted paths
         have no file to view — the backend sends null and no link shows. -->
    <Link v-if="data.file_url" class="git-file-link ms-2" :href="data.file_url"
      >file</Link
    >
  </h3>
  <p v-if="!data.diff" class="text-muted">No changes.</p>
  <SplitDiff v-else :diff="data.diff" />
</template>

<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import PageTitle from "../../components/PageTitle.vue"
import SplitDiff from "../../components/git/SplitDiff.vue"
import { GitDiffPropsSchema } from "../../schemas/git"

const props = defineProps<{ props: object }>()
const data = GitDiffPropsSchema.parse(props.props)

// SplitDiff lazy-loads diff2html + hljs and shows its own Loading note until
// the (async) render lands — nothing to await here.
</script>
