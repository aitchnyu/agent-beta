<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import HumanizedTime from "../components/HumanizedTime.vue"
import PageTitle from "../components/PageTitle.vue"
import RepoNav from "../components/RepoNav.vue"
import { FileBrowserPropsSchema } from "../schemas"
import { fileUrl, formatSize } from "../utils/files"

const props = defineProps<{ props: object }>()
const p = FileBrowserPropsSchema.parse(props.props)

// An entry under the current dir: join `rel` and the entry name.
function entryUrl(name: string): string {
  return fileUrl(p.rel ? `${p.rel}/${name}` : name)
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
            <Link class="files-entry files-dir" :href="fileUrl(p.parent)"
              >📁 ..</Link
            >
          </td>
        </tr>
        <tr v-for="e in p.entries" :key="e.name">
          <td>
            <Link
              class="files-entry"
              :class="{ 'files-dir': e.is_dir, 'files-image': e.is_image }"
              :href="entryUrl(e.name)"
              >{{ e.is_dir ? "📁" : e.is_image ? "🖼" : "📄" }}
              {{ e.name }}</Link
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
