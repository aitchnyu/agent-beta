<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import HumanizedTime from "../components/HumanizedTime.vue"
import LucideIcon from "../components/LucideIcon.vue"
import PageTitle from "../components/PageTitle.vue"
import RepoNav from "../components/RepoNav.vue"
import fileCodeIcon from "../icons/file-code.svg"
import fileIcon from "../icons/file.svg"
import fileImageIcon from "../icons/file-image.svg"
import fileTextIcon from "../icons/file-text.svg"
import folderIcon from "../icons/folder.svg"
import { FileBrowserPropsSchema } from "../schemas"
import { detectLanguage, fileUrl, formatSize } from "../utils/files"

const props = defineProps<{ props: object }>()

const p = FileBrowserPropsSchema.parse(props.props)

// An entry under the current dir: join `rel` and the entry name.
function entryUrl(name: string): string {
  return fileUrl(p.rel ? `${p.rel}/${name}` : name)
}

// Icon per entry type:
// - dir → folder, image → file-image, md/txt/rst → file-text, rest → file
// - code → file-code, decided by detectLanguage — the same map the
//   viewer highlights from, so icon and highlighting can't drift
//   (lucide has no python/vue glyphs; all code shares file-code)
const TEXT_SUFFIXES = new Set(["md", "txt", "rst"])

function entryIcon(e: {
  is_dir: boolean
  is_image: boolean
  name: string
}): string {
  if (e.is_dir) return folderIcon
  if (e.is_image) return fileImageIcon
  const suffix = e.name.split(".").pop()?.toLowerCase() ?? ""
  if (TEXT_SUFFIXES.has(suffix)) return fileTextIcon
  if (detectLanguage(e.name)) return fileCodeIcon
  return fileIcon
}
</script>
<template>
  <PageTitle value="Files" />
  <div>
    <RepoNav />
    <h3>Files</h3>
    <div class="files-crumbs-row">
      <nav class="files-breadcrumb">
        <template v-for="c in p.breadcrumb" :key="c.rel">
          <Link class="files-crumb" :href="fileUrl(c.rel)">{{ c.label }}</Link>
          <span class="files-sep" aria-hidden="true">/</span>
        </template>
      </nav>
      <!-- Toggles excluded dirs (.venv/node_modules/.git/__pycache__) via ?hidden.
           Uses contains_hidden_entries so the label reflects the current state.
           Beside the nav (not inside it) — a display control isn't navigation. -->
      <Link
        class="files-toggle-hidden"
        :href="
          p.contains_hidden_entries
            ? fileUrl(p.rel)
            : `${fileUrl(p.rel)}?hidden=true`
        "
      >
        {{ p.contains_hidden_entries ? "Hide hidden" : "Show hidden" }}
      </Link>
    </div>
    <table class="table table-sm align-middle">
      <thead>
        <tr>
          <th scope="col">Name</th>
          <th scope="col" class="text-end">Size</th>
          <th scope="col">Modified</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="p.parent !== null">
          <td colspan="3">
            <Link class="files-entry" :href="fileUrl(p.parent)"
              ><LucideIcon :src="folderIcon" /> ..</Link
            >
          </td>
        </tr>
        <tr v-for="e in p.entries" :key="e.name">
          <td>
            <Link
              class="files-entry"
              :class="{ 'files-image': e.is_image }"
              :href="entryUrl(e.name)"
              ><LucideIcon :src="entryIcon(e)" /> {{ e.name }}</Link
            >
          </td>
          <td class="text-end files-size">
            {{ e.is_dir ? "—" : formatSize(e.size) }}
          </td>
          <td class="files-mtime"><HumanizedTime :ms="e.mtime" /></td>
        </tr>
        <tr v-if="p.entries.length === 0">
          <td colspan="3" class="text-center text-muted py-4">
            Empty directory.
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
