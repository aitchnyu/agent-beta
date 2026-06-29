<script setup lang="ts">
import axios from "axios"
import { reactive, ref } from "vue"
import { router } from "@inertiajs/vue3"
import Layout from "../components/Layout.vue"
import RichTextEditor from "../components/RichTextEditor.vue"
import { showErrorToast } from "../utils/sweetalert"
import { MessageResponseSchema, UserEditPropsSchema } from "../schemas.ts"

const props = defineProps<{
  props: object
}>()

const p = UserEditPropsSchema.parse(props.props)
const pathPrefix = p.path_prefix

// username is read-only; the rest are editable.
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
    const res = MessageResponseSchema.parse(
      (
        await axios.post(`${pathPrefix}/edit/${p.target.public_id}`, {
          ...form,
        })
      ).data,
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
  <Layout>
    <div class="container user-edit-page">
      <h1>Edit User</h1>
      <p class="text-muted">
        Editing {{ p.target.username }} ({{ p.target.first_name }}
        {{ p.target.last_name }})
      </p>

      <form @submit.prevent="onSubmit">
        <div class="row g-3 mb-3">
          <div class="col-md-6">
            <label class="form-label">First name</label>
            <input
              v-model="form.first_name"
              type="text"
              class="form-control user-edit-first-name"
            />
          </div>
          <div class="col-md-6">
            <label class="form-label">Last name</label>
            <input v-model="form.last_name" type="text" class="form-control" />
          </div>
          <div class="col-md-6">
            <label class="form-label">Username</label>
            <input
              :value="p.target.username"
              type="text"
              class="form-control"
              disabled
            />
            <div class="form-text">Username cannot be changed.</div>
          </div>
          <div class="col-md-6">
            <label class="form-label">Email</label>
            <input v-model="form.email" type="email" class="form-control" />
          </div>
        </div>

        <div class="mb-3">
          <label class="form-label">Description</label>
          <RichTextEditor v-model="form.description" />
        </div>

        <div class="d-flex gap-4 mb-3">
          <div class="form-check">
            <input
              id="has_public_profile"
              v-model="form.has_public_profile"
              type="checkbox"
              class="form-check-input"
            />
            <label class="form-check-label" for="has_public_profile">
              Public profile
            </label>
          </div>
          <div class="form-check">
            <input
              id="is_active"
              v-model="form.is_active"
              type="checkbox"
              class="form-check-input"
            />
            <label class="form-check-label" for="is_active"> Active </label>
          </div>
          <div class="form-check">
            <input
              id="is_staff"
              v-model="form.is_staff"
              type="checkbox"
              class="form-check-input"
            />
            <label class="form-check-label" for="is_staff"> Staff </label>
          </div>
          <div class="form-check">
            <input
              id="is_superuser"
              v-model="form.is_superuser"
              type="checkbox"
              class="form-check-input"
            />
            <label class="form-check-label" for="is_superuser">
              Superuser
            </label>
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
  </Layout>
</template>
