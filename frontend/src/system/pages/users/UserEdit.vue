<script setup lang="ts">
import { defineAsyncComponent, reactive, ref } from "vue"
import { router } from "@inertiajs/vue3"
import PageTitle from "../../components/PageTitle.vue"
import {
  UserEditPropsSchema,
  UserMessageResponseSchema,
} from "../../schemas/users"
import { showErrorToast } from "../../../utils/sweetalert"
import { postJSON } from "../../../utils/http"

// Quill ships in its own lazy chunk (RichTextEditor + quill); the async
// component resolves it on first mount of this page.
const RichTextEditor = defineAsyncComponent(
  () => import("../../components/RichTextEditor.vue"),
)

const props = defineProps<{
  props: object
}>()

const p = UserEditPropsSchema.parse(props.props)
const pathPrefix = p.path_prefix

// username is read-only; the rest are editable. Mutations go through the
// app's HTTP layer (utils/http.ts: CSRF hook + errors normalized to the
// @inertiajs/core classes showErrorToast already understands).
const form = reactive({
  first_name: p.target.first_name,
  last_name: p.target.last_name,
  email: p.target.email,
  description: p.target.description,
  has_public_profile: p.target.has_public_profile,
  is_active: p.target.is_active,
  is_staff: p.target.is_staff,
  is_superuser: p.target.is_superuser,
})
const isSubmitting = ref(false)

async function onSubmit() {
  isSubmitting.value = true
  try {
    const res = UserMessageResponseSchema.parse(
      await postJSON(`${pathPrefix}/edit/${p.target.public_id}`, {
        ...form,
      }),
    )
    // Server echoes the edited user's public id; confirm it matches the target.
    if (res.id !== p.target.public_id) {
      throw new Error("Saved a different user than expected")
    }
    router.visit(`${pathPrefix}/id/${p.target.public_id}`)
  } catch (e: unknown) {
    showErrorToast(e, "Failed to update user")
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <PageTitle value="Edit User" />
  <div class="container user-edit-page">
    <h1>Edit User</h1>
    <p class="text-muted">
      Editing {{ p.target.username }} ({{ p.target.first_name }}
      {{ p.target.last_name }})
    </p>

    <form @submit.prevent="onSubmit">
      <div class="mb-3">
        <label class="form-label" for="user-edit-first-name">First name</label>
        <input
          id="user-edit-first-name"
          v-model="form.first_name"
          type="text"
          class="form-control user-edit-first-name"
        />
        <div class="form-text">Displayed on this user's profile page.</div>
      </div>
      <div class="mb-3">
        <label class="form-label" for="user-edit-last-name">Last name</label>
        <input
          id="user-edit-last-name"
          v-model="form.last_name"
          type="text"
          class="form-control"
        />
        <div class="form-text">
          Displayed alongside the first name on the profile page.
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label" for="user-edit-username">Username</label>
        <input
          id="user-edit-username"
          :value="p.target.username"
          type="text"
          class="form-control"
          disabled
        />
        <div class="form-text">Username cannot be changed.</div>
      </div>
      <div class="mb-3">
        <label class="form-label" for="user-edit-email">Email</label>
        <input
          id="user-edit-email"
          v-model="form.email"
          type="email"
          class="form-control"
        />
        <div class="form-text">
          Login identity — social sign-in matches this address.
        </div>
      </div>

      <div class="mb-3">
        <label class="form-label" for="user-edit-description"
          >Description</label
        >
        <RichTextEditor v-model="form.description" />
        <div class="form-text">Rich-text blurb shown on the profile page.</div>
      </div>

      <div class="mb-3">
        <div class="form-check mb-2">
          <input
            id="has_public_profile"
            v-model="form.has_public_profile"
            type="checkbox"
            class="form-check-input"
          />
          <label class="form-check-label" for="has_public_profile">
            Public profile
          </label>
          <div class="form-text">
            Show this user's username and description on their public profile
            page.
          </div>
        </div>
        <div class="form-check mb-2">
          <input
            id="is_active"
            v-model="form.is_active"
            type="checkbox"
            class="form-check-input"
          />
          <label class="form-check-label" for="is_active"> Active </label>
          <div class="form-text">
            Inactive users cannot sign in; existing sessions stay until logged
            out.
          </div>
        </div>
        <div class="form-check mb-2">
          <input
            id="is_staff"
            v-model="form.is_staff"
            type="checkbox"
            class="form-check-input"
          />
          <label class="form-check-label" for="is_staff"> Staff </label>
          <div class="form-text">
            Django admin access at /admin/ — rarely needed.
          </div>
        </div>
        <div class="form-check mb-2">
          <input
            id="is_superuser"
            v-model="form.is_superuser"
            type="checkbox"
            class="form-check-input"
          />
          <label class="form-check-label" for="is_superuser"> Superuser </label>
          <div class="form-text">
            Full control: the manage pages, editing any user, minting login
            links.
          </div>
        </div>
      </div>

      <button
        type="submit"
        class="btn btn-primary user-edit-save"
        :disabled="isSubmitting"
      >
        {{ isSubmitting ? "Saving..." : "Save" }}
      </button>
    </form>
  </div>
</template>
