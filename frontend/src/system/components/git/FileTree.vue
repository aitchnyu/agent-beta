<script setup lang="ts">
import { ref, useId } from "vue"
import { Link } from "@inertiajs/vue3"
import LucideIcon from "../../components/LucideIcon.vue"
import chevronDownIcon from "../../icons/chevron-down.svg"
import chevronRightIcon from "../../icons/chevron-right.svg"
import filePenIcon from "../../icons/file-pen.svg"
import filePlus2Icon from "../../icons/file-plus-2.svg"
import fileXIcon from "../../icons/file-x.svg"
import type { FileTreeEntry, FileTreeFolder, PathLinkBuilder } from "./fileTree"

// Recursive changed-files tree shared by the uncommitted and commit pages.
// The pages supply the three link builders — routes AND worktree prefixes
// differ (uncommitted links carry the worktree, commit links read main/);
// the status icons/colors live HERE, one mapping instead of the two per-page
// copies this replaces. Fold state is per-FOLDER (a Set of sibling names —
// names are unique within a level), NOT one ref per component instance: the
// v-for renders many folders through one instance, and a shared ref there
// folded every sibling together. Folders start expanded.

const props = defineProps<{
  node: FileTreeFolder
  diffHref: PathLinkBuilder
  fileHref: PathLinkBuilder
  dirHref: PathLinkBuilder
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

const STATUS_ICON_BY_STATUS: Record<string, string> = {
  untracked: filePlus2Icon,
  added: filePlus2Icon,
  modified: filePenIcon,
  deleted: fileXIcon,
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
      <div class="d-flex align-items-baseline">
        <button
          class="git-folder-toggle"
          type="button"
          :data-tree-toggle="folder.path"
          :aria-expanded="!collapsedFolders.has(folder.name)"
          :aria-controls="subtreeId(folder.name)"
          :aria-label="`fold ${folder.path}/`"
          @click="toggleFolder(folder.name)"
        >
          <LucideIcon
            class="git-folder-caret"
            :src="
              collapsedFolders.has(folder.name)
                ? chevronRightIcon
                : chevronDownIcon
            "
          />
        </button>
        <!-- The title visits the dir in /files — the LIVE tree, so a dir
             deleted after this commit 404s (accepted, same tradeoff as
             the nulled-out file links in git.py); the caret alone folds. -->
        <Link class="git-folder-name" :href="props.dirHref(folder.path)"
          >{{ folder.name }}/
          <span class="git-folder-count">({{ folder.count }})</span></Link
        >
      </div>
      <FileTree
        v-show="!collapsedFolders.has(folder.name)"
        :node="folder"
        :diff-href="props.diffHref"
        :file-href="props.fileHref"
        :dir-href="props.dirHref"
        :ul-id="subtreeId(folder.name)"
      />
    </li>
    <li
      v-for="entry in props.node.files"
      :key="entry.path"
      class="d-flex align-items-baseline"
      :title="entry.path"
    >
      <span
        class="git-status"
        :class="statusClass(entry.status)"
        role="img"
        :aria-label="entry.status"
        :title="entry.status"
      >
        <LucideIcon
          v-if="STATUS_ICON_BY_STATUS[entry.status]"
          :src="STATUS_ICON_BY_STATUS[entry.status]"
        />
        <template v-else>?</template>
      </span>
      <Link
        :class="{ 'text-decoration-line-through': entry.status === 'deleted' }"
        :href="
          entry.status === 'deleted'
            ? props.diffHref(entry.path)
            : props.fileHref(entry.path)
        "
        ><code>{{ fileName(entry) }}</code></Link
      >
      <!-- Muted diff companion to the file-view name link. Deleted paths
           only have the diff — the name IS the diff link, no duplicate. -->
      <Link
        v-if="entry.status !== 'deleted'"
        class="git-file-link ms-2"
        :href="props.diffHref(entry.path)"
        >diff</Link
      >
    </li>
  </ul>
</template>
