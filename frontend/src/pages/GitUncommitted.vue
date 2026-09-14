<template>
  <PageTitle value="Uncommitted changes" />
  <RepoNav />
  <h3>Uncommitted changes</h3>
  <section
    v-for="wt in sections"
    :key="wt.name"
    class="mb-4"
    :data-tree-section="wt.name"
  >
    <h4 class="h6 mb-1">{{ wt.name }}</h4>
    <FileTree
      v-if="wt.files.length"
      :node="wt.tree"
      :diff-href="(path: string) => `/git/uncommitted/${wt.name}/${path}`"
      :file-href="(path: string) => fileUrl(`${wt.name}/${path}`)"
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
import { buildFileTree, type FileTreeFolder } from "../utils/fileTree"
import { fileUrl } from "../utils/files"

const props = defineProps<{ props: object }>()
const data = GitUncommittedPropsSchema.parse(props.props)

// main is mandatory; scratch is optional (null when scratch/ isn't on disk yet).
// Each worktree's flat file list becomes the folder tree FileTree renders;
// link builders carry the worktree segment (uncommitted diffs + file urls).
const sections = computed(() => {
  const list: {
    name: string
    files: typeof data.main_files
    tree: FileTreeFolder
  }[] = [
    {
      name: "main",
      files: data.main_files,
      tree: buildFileTree(data.main_files),
    },
  ]
  if (data.scratch_files)
    list.push({
      name: "scratch",
      files: data.scratch_files,
      tree: buildFileTree(data.scratch_files),
    })
  return list
})
</script>
