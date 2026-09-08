<script setup lang="ts">
import { ref, useId } from "vue"
import { Link } from "@inertiajs/vue3"
import type {
  FileTreeEntry,
  FileTreeFolder,
  PathLinkBuilder,
} from "../utils/fileTree"

// Recursive changed-files tree shared by the uncommitted and commit pages.
// The pages supply the two link builders — routes AND worktree prefixes
// differ (uncommitted links carry the worktree, commit links read main/);
// the status words/colors live HERE, one mapping instead of the two per-page
// copies this replaces. Fold state is per-FOLDER (a Set of sibling names —
// names are unique within a level), NOT one ref per component instance: the
// v-for renders many folders through one instance, and a shared ref there
// folded every sibling together. Folders start expanded.

const props = defineProps<{
  node: FileTreeFolder
  diffHref: PathLinkBuilder
  fileHref: PathLinkBuilder
  /** id for this instance's root <ul> — the parent's toggle points at it
   *  via aria-controls (ids must be unique across the whole page, which
   *  same-named folders in sibling sections otherwise break). */
  ulId?: string
}>()

// Unique per-instance prefix for subtree ul ids (same-named folders appear
// in both worktree sections — and at different depths — so folder names
// alone can't key them document-wide).
const instanceId = useId()

const collapsedFolders = ref(new Set<string>())

function toggleFolder(name: string) {
  const next = new Set(collapsedFolders.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  collapsedFolders.value = next
}

const subtreeId = (name: string) => `${instanceId}-${name}`

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

const fileName = (entry: FileTreeEntry) =>
  entry.path.slice(entry.path.lastIndexOf("/") + 1)
</script>

<template>
  <ul class="list-unstyled mb-0 file-tree" :id="props.ulId">
    <li
      v-for="folder in props.node.folders"
      :key="folder.path"
      class="git-folder"
      :data-tree-folder="folder.path"
    >
      <button
        class="git-folder-toggle"
        type="button"
        :data-tree-toggle="folder.path"
        :aria-expanded="!collapsedFolders.has(folder.name)"
        :aria-controls="subtreeId(folder.name)"
        @click="toggleFolder(folder.name)"
      >
        <span class="git-folder-caret" aria-hidden="true">{{
          collapsedFolders.has(folder.name) ? "▸" : "▾"
        }}</span>
        <span class="git-folder-name"
          >{{ folder.name }}/
          <span class="git-folder-count">({{ folder.count }})</span></span
        >
      </button>
      <FileTree
        v-show="!collapsedFolders.has(folder.name)"
        :node="folder"
        :diff-href="props.diffHref"
        :file-href="props.fileHref"
        :ul-id="subtreeId(folder.name)"
      />
    </li>
    <li
      v-for="entry in props.node.files"
      :key="entry.path"
      class="d-flex align-items-baseline"
      :title="entry.path"
    >
      <code class="git-status" :class="statusClass(entry.status)">{{
        statusWord(entry.status)
      }}</code>
      <Link
        :class="{ 'text-decoration-line-through': entry.status === 'deleted' }"
        :href="props.diffHref(entry.path)"
        ><code>{{ fileName(entry) }}</code></Link
      >
      <!-- No "file" link for deleted paths — /files/<worktree>/<path> would 404. -->
      <Link
        v-if="entry.status !== 'deleted'"
        class="git-file-link ms-2"
        :href="props.fileHref(entry.path)"
        >file</Link
      >
    </li>
  </ul>
</template>
