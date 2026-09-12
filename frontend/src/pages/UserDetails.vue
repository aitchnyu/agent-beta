<script setup lang="ts">
import { computed, ref } from "vue"
import type { z } from "zod"
import { Link, usePage } from "@inertiajs/vue3"
import PageTitle from "../components/PageTitle.vue"
import RichTextViewer from "../components/RichTextViewer.vue"
import { postJSON } from "../utils/http"
import { showErrorToast, showToast } from "../utils/sweetalert"
import { formatDateTime } from "../utils/time"
import {
  LoginLinkResponseSchema,
  SharedPropsSchema,
  UserDetailsPropsSchema,
} from "../schemas.ts"

const props = defineProps<{
  props: object
}>()

const p = UserDetailsPropsSchema.parse(props.props)
// Admin UI gates on the shared viewer_is_superuser flag (was a page prop).
const isSuperuser = computed(
  () => SharedPropsSchema.parse(usePage().props).viewer_is_superuser,
)

// ── Admin action: login link ───────────────────────────────────────────────
// Mutations ride the app's HTTP layer (CSRF hook + normalized errors), same
// as the edit page.

const showLinkPanel = ref(false)
const ttlMinutes = ref(15)
const linkResult = ref<z.infer<typeof LoginLinkResponseSchema> | null>(null)
const generating = ref(false)

async function generateLink() {
  generating.value = true
  try {
    linkResult.value = LoginLinkResponseSchema.parse(
      await postJSON(`${p.path_prefix}/api/${p.public_id}/loginlink`, {
        ttl_minutes: ttlMinutes.value,
      }),
    )
  } catch (e: unknown) {
    showErrorToast(e, "Failed to generate login link")
  } finally {
    generating.value = false
  }
}

async function copyLink() {
  if (!linkResult.value) return
  try {
    await navigator.clipboard.writeText(linkResult.value.url)
    showToast("success", "Login link copied")
  } catch {
    showToast("error", "Could not copy — select the URL manually")
  }
}
</script>

<template>
  <PageTitle :value="p.first_name + ' ' + p.last_name" />
  <div class="container user-details-page">
    <Link
      v-if="isSuperuser"
      href="/users/list"
      class="small text-muted text-decoration-none"
    >
      &larr; Back to Users
    </Link>
    <h1 :class="{ 'user-inactive': isSuperuser && !p.is_active }">
      {{ p.first_name }} {{ p.last_name }}
      <span v-if="isSuperuser && !p.is_active" class="badge bg-secondary ms-2"
        >Inactive</span
      >
    </h1>
    <div v-if="p.username" class="text-muted mb-3">{{ p.username }}</div>
    <span v-if="p.is_owner" class="badge bg-primary mb-3">This is you</span>
    <div v-if="isSuperuser" class="mb-3 d-flex gap-2">
      <Link
        :href="`/users/edit/${p.public_id}`"
        class="btn btn-outline-secondary btn-sm"
        >Edit</Link
      >
      <button
        class="btn btn-outline-secondary btn-sm user-details-login-link-btn"
        :aria-expanded="showLinkPanel"
        aria-controls="user-details-link-panel"
        @click="showLinkPanel = !showLinkPanel"
      >
        Login link
      </button>
      <Link
        :href="`/users/history/${p.public_id}`"
        class="small text-muted text-decoration-none align-self-center"
        >History ({{ p.history_count }})</Link
      >
    </div>

    <div
      v-if="isSuperuser && showLinkPanel"
      id="user-details-link-panel"
      class="card mb-4 user-details-link-panel"
    >
      <div class="card-body">
        <div class="d-flex gap-2 align-items-center mb-2">
          <label class="form-label mb-0" for="user-details-ttl"
            >Valid for</label
          >
          <select
            id="user-details-ttl"
            v-model="ttlMinutes"
            class="form-select form-select-sm w-auto"
          >
            <option :value="15">15 minutes</option>
            <option :value="60">1 hour</option>
            <option :value="480">8 hours</option>
            <option :value="1440">24 hours</option>
          </select>
          <button
            class="btn btn-sm btn-primary user-details-generate-link-btn"
            :disabled="generating"
            @click="generateLink()"
          >
            {{ generating ? "Generating..." : "Generate" }}
          </button>
        </div>
        <div v-if="linkResult">
          <div class="input-group input-group-sm">
            <input
              :value="linkResult.url"
              type="text"
              readonly
              class="form-control user-details-link-url"
              @focus="($event.target as HTMLInputElement).select()"
            />
            <button
              class="btn btn-outline-secondary user-details-copy-link-btn"
              @click="copyLink()"
            >
              Copy
            </button>
          </div>
          <div class="form-text">
            Single use, expires {{ formatDateTime(linkResult.expires_at) }}.
            Anyone with this URL can sign in as {{ p.first_name }} — treat it
            like a password.
          </div>
        </div>
      </div>
    </div>

    <table v-if="isSuperuser" class="table table-sm user-details-attrs mb-4">
      <tbody>
        <tr>
          <th scope="row">Email</th>
          <td>{{ p.email }}</td>
        </tr>
        <tr>
          <th scope="row">Public profile</th>
          <td>
            <span v-if="p.has_public_profile" class="user-yes">Yes</span>
            <span v-else class="user-no">No</span>
          </td>
        </tr>
        <tr>
          <th scope="row">Active</th>
          <td>
            <span v-if="p.is_active" class="user-yes">Yes</span>
            <span v-else class="user-no">No</span>
          </td>
        </tr>
        <tr>
          <th scope="row">Staff</th>
          <td>
            <span v-if="p.is_staff" class="user-yes">Yes</span>
            <span v-else class="user-no">No</span>
          </td>
        </tr>
        <tr>
          <th scope="row">Superuser</th>
          <td>
            <span v-if="p.is_superuser" class="user-yes">Yes</span>
            <span v-else class="user-no">No</span>
          </td>
        </tr>
        <tr>
          <th scope="row">Last login</th>
          <td>
            <span v-if="p.last_login">{{ formatDateTime(p.last_login) }}</span>
            <span v-else class="text-muted">Never</span>
          </td>
        </tr>
      </tbody>
    </table>

    <RichTextViewer
      v-if="p.description"
      :html="p.description"
      className="rich-text-display user-details-content"
    />
    <p v-else class="text-muted">This profile has no public description.</p>
  </div>
</template>
