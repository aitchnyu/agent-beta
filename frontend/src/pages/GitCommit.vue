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
  <div v-else data-tree-section="main">
    <FileTree
      :node="tree"
      :diff-href="
        (path: string) => `/git/commits/${data.commit.short_sha}/${path}`
      "
      :file-href="(path: string) => fileUrl(`main/${path}`)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import FileTree from "../components/FileTree.vue"
import HumanizedTime from "../components/HumanizedTime.vue"
import PageTitle from "../components/PageTitle.vue"
import GitNav from "../components/GitNav.vue"
import { GitCommitPropsSchema } from "../schemas"
import { buildFileTree, type FileTreeFolder } from "../utils/fileTree"
import { fileUrl } from "../utils/files"

const props = defineProps<{ props: object }>()
const data = GitCommitPropsSchema.parse(props.props)

// The commit's flat file list as the folder tree FileTree renders; commits
// read main/ only, so file urls prefix main/.
const tree = computed<FileTreeFolder>(() => buildFileTree(data.files))
</script>
