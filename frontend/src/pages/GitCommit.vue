<template>
  <PageTitle
    :value="'Commit ' + shortSha(data.commit.sha) + ' ' + data.commit.subject"
  />
  <RepoNav />
  <h3>
    <code>{{ shortSha(data.commit.sha) }}</code> {{ data.commit.subject }}
  </h3>
  <p class="text-muted">
    {{ data.commit.author }} · <HumanizedTime :ms="data.commit.date" />
  </p>
  <p v-if="!data.files.length" class="text-muted">No changed files.</p>
  <div v-else data-tree-section="main">
    <FileTree
      :node="tree"
      :diff-href="
        (path: string) => `/git/commits/${shortSha(data.commit.sha)}/${path}`
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
import RepoNav from "../components/RepoNav.vue"
import { GitCommitPropsSchema } from "../schemas"
import { buildFileTree, type FileTreeFolder } from "../utils/fileTree"
import { fileUrl } from "../utils/files"
import { shortSha } from "../utils/git"

const props = defineProps<{ props: object }>()
const data = GitCommitPropsSchema.parse(props.props)

// The commit's flat file list as the folder tree FileTree renders; commits
// read main/ only, so file urls prefix main/.
const tree = computed<FileTreeFolder>(() => buildFileTree(data.files))
</script>
