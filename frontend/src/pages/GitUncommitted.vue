<template>
  <PageTitle value="Uncommitted changes" />
  <RepoNav />
  <h3>Uncommitted changes</h3>
  <section v-if="data.scratch_files" class="mb-4" data-tree-section="scratch">
    <h4 class="h6 mb-1">scratch</h4>
    <FileTree
      v-if="data.scratch_files.length"
      :node="scratchTree"
      :diff-href="(path: string) => `/git/uncommitted/scratch/${path}`"
      :file-href="(path: string) => fileUrl(`scratch/${path}`)"
    />
    <p v-else class="text-muted mb-0">No changes.</p>
  </section>
  <section class="mb-4" data-tree-section="main">
    <h4 class="h6 mb-1">main</h4>
    <FileTree
      v-if="data.main_files.length"
      :node="mainTree"
      :diff-href="(path: string) => `/git/uncommitted/main/${path}`"
      :file-href="(path: string) => fileUrl(`main/${path}`)"
    />
    <p v-else class="text-muted mb-0">No changes.</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue"
import FileTree from "../components/FileTree.vue"
import RepoNav from "../components/RepoNav.vue"
import PageTitle from "../components/PageTitle.vue"
import { GitUncommittedPropsSchema } from "../schemas"
import { buildFileTree } from "../utils/fileTree"
import { fileUrl } from "../utils/files"

const props = defineProps<{ props: object }>()
const data = GitUncommittedPropsSchema.parse(props.props)

// scratch_files is null when scratch/ isn't on disk — its section is
// omitted then. main always renders.
const scratchTree = computed(() => buildFileTree(data.scratch_files ?? []))
const mainTree = computed(() => buildFileTree(data.main_files))
</script>
