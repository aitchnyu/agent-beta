<template>
  <PageTitle :value="data.title" />
  <GitNav />
  <h1>{{ data.title }}</h1>
  <p v-if="!data.diff" class="text-muted">No changes.</p>
  <SplitDiff v-else :diff="data.diff" />
</template>

<script setup lang="ts">
import PageTitle from "../components/PageTitle.vue"
import GitNav from "../components/GitNav.vue"
import SplitDiff from "../components/SplitDiff.vue"
import { GitDiffPropsSchema } from "../schemas"

const props = defineProps<{ props: object }>()
const data = GitDiffPropsSchema.parse(props.props)

// SplitDiff lazy-loads diff2html + hljs and shows its own Loading note until
// the (async) render lands — nothing to await here.
</script>
