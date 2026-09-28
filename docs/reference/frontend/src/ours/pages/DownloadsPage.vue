<script setup lang="ts">
import { computed, ref } from "vue"
import { router } from "@inertiajs/vue3"
import PageTitle from "../../components/PageTitle.vue"
import { DownloadsPagePropsSchema, type DownloadOut } from "../schemas"
import { postForm, postJSON } from "../../utils/http"
import { showErrorToast } from "../../utils/sweetalert"
import "../style.scss"

// Inertia wraps the page data under a `props` key (page.props.props); parse it.
const props = defineProps<{ props: object }>()
const downloads = computed(() => DownloadsPagePropsSchema.parse(props.props).downloads)

// One upload form state: the file picker + the optional expiry picker
// (empty = the server default, one week out).
const uploading = ref(false)
const uploadInput = ref<HTMLInputElement | null>(null)
const expiry = ref("")

// One hidden replace input; `pending` holds the row whose Replace button
// opened it (a cancelled picker never fires change — the stale pending is
// harmless, the next click overwrites it).
const replaceInput = ref<HTMLInputElement | null>(null)
const pending = ref<DownloadOut | null>(null)
const busy = ref<string | null>(null)

function fmt(iso: string): string {
  return new Date(iso).toLocaleString()
}

function shareUrl(d: DownloadOut): string {
  return `${window.location.origin}/downloads/${d.stored_name}`
}

function reload() {
  router.reload().catch((e) => showErrorToast(e, "Could not reload downloads"))
}

function onReplaceChange() {
  const row = pending.value
  pending.value = null
  if (row) void replace(row)
}

async function upload() {
  const file = uploadInput.value?.files?.[0]
  if (!file || uploading.value) return
  uploading.value = true
  try {
    const form = new FormData()
    form.append("file", file)
    if (expiry.value) form.append("expires_at", expiry.value)
    await postForm("/downloads/upload", form)
    if (uploadInput.value) uploadInput.value.value = ""
    expiry.value = ""
    reload()
  } catch (e) {
    showErrorToast(e, "Could not upload the file")
  } finally {
    uploading.value = false
  }
}

async function replace(d: DownloadOut) {
  const file = replaceInput.value?.files?.[0]
  // Clear immediately: a failed replace (or the busy-guard early return)
  // must not leave the old selection in the picker — re-picking the SAME
  // file would fire no change event and silently dead-click.
  if (replaceInput.value) replaceInput.value.value = ""
  if (!file || busy.value !== null) return
  busy.value = d.public_id
  try {
    const form = new FormData()
    form.append("file", file)
    form.append("expected_row_version", String(d.row_version))
    await postForm(`/downloads/${d.public_id}/replace`, form)
    reload()
  } catch (e) {
    showErrorToast(e, "Could not replace the file")
  } finally {
    busy.value = null
  }
}

async function remove(d: DownloadOut) {
  if (busy.value !== null) return
  busy.value = d.public_id
  try {
    await postJSON(`/downloads/${d.public_id}/delete`)
    reload()
  } catch (e) {
    showErrorToast(e, "Could not delete the download")
  } finally {
    busy.value = null
  }
}

async function copyLink(d: DownloadOut) {
  try {
    await navigator.clipboard.writeText(shareUrl(d))
  } catch (e) {
    showErrorToast(e, "Could not copy the link")
  }
}
</script>

<template>
    <div class="ours-downloads-page">
      <PageTitle value="Downloads" />
      <h1>Downloads</h1>

      <form class="ours-downloads-form" @submit.prevent="upload">
        <input ref="uploadInput" type="file" aria-label="File to share" />
        <input
          v-model="expiry"
          type="datetime-local"
          aria-label="Expiry date (default: one week)"
        />
        <button class="btn btn-primary" type="submit" :disabled="uploading">
          Upload
        </button>
      </form>

      <table v-if="downloads.length" class="ours-downloads-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Expires</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in downloads" :key="d.public_id">
            <td>{{ d.original_name }}</td>
            <td>
              <span :class="{ 'text-muted': d.is_expired }">
                {{ fmt(d.expires_at) }}
              </span>
              <span v-if="d.is_expired" class="badge text-bg-secondary">
                expired
              </span>
            </td>
            <td>
              <a
                v-if="!d.is_expired"
                class="btn btn-sm btn-outline-primary"
                :href="`/downloads/${d.stored_name}`"
                :download="d.original_name"
              >
                Download
              </a>
              <button
                class="btn btn-sm btn-outline-secondary"
                type="button"
                @click="copyLink(d)"
              >
                Copy link
              </button>
              <button
                class="btn btn-sm btn-outline-secondary"
                type="button"
                :disabled="busy !== null"
                :data-testid="`replace-${d.public_id}`"
                @click="pending = d; replaceInput?.click()"
              >
                Replace
              </button>
              <button
                class="btn btn-sm btn-outline-danger"
                type="button"
                :disabled="busy !== null"
                :data-testid="`delete-${d.public_id}`"
                @click="remove(d)"
              >
                Delete
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="text-muted">No files shared yet.</p>

      <!-- The one hidden picker every Replace button opens; the change
           handler reads the pending row captured at click time. -->
      <input ref="replaceInput" type="file" hidden @change="onReplaceChange" />
    </div>
</template>
