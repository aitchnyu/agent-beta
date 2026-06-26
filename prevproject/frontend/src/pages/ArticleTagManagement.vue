<script setup lang="ts">
import axios from "axios"
import { computed, ref } from "vue"
import { router } from "@inertiajs/vue3"
import Layout from "../components/Layout.vue"
import { showConfirm, showErrorToast, showToast } from "../utils/sweetalert"
import {
  ArticleTagManagementPropsSchema,
  type ArticleTagWithCount,
} from "../schemas.js"

const props = defineProps<{
  props: object
}>()

const p = computed(() => ArticleTagManagementPropsSchema.parse(props.props))
const pathPrefix = p.value.path_prefix

const newName = ref("")
const newColor = ref("#3b82f6")
const editingTag = ref<string | null>(null)
const editName = ref("")
const editColor = ref("")

async function createTag() {
  try {
    await axios.post(`${pathPrefix}/tag/create`, {
      name: newName.value,
      color: newColor.value,
    })
    newName.value = ""
    newColor.value = "#3b82f6"
    showToast("success", "Tag created")
    router.reload()
  } catch (e: unknown) {
    showErrorToast(e, "Failed to create tag")
  }
}

function startEdit(tag: ArticleTagWithCount) {
  editingTag.value = tag.name
  editName.value = tag.name
  editColor.value = tag.color
}

async function saveEdit(originalName: string) {
  try {
    await axios.post(`${pathPrefix}/tag/update/${originalName}`, {
      name: editName.value,
      color: editColor.value,
    })
    editingTag.value = null
    showToast("success", "Tag updated")
    router.reload()
  } catch (e: unknown) {
    showErrorToast(e, "Failed to update tag")
  }
}

async function deleteTag(name: string) {
  const confirmed = await showConfirm({ title: `Delete tag "${name}"?` })
  if (!confirmed) return
  try {
    await axios.post(`${pathPrefix}/tag/delete/${name}`)
    showToast("success", "Tag deleted")
    router.reload()
  } catch (e: unknown) {
    showErrorToast(e, "Failed to delete tag")
  }
}
</script>

<template>
  <Layout :user="p.user">
    <div class="container article-tag-page">
      <h1>Tag Management</h1>

      <div class="card mb-4">
        <div class="card-body">
          <h5 class="card-title">Create Tag</h5>
          <div class="d-flex align-items-center gap-2">
            <input
              v-model="newName"
              type="text"
              class="form-control form-control-sm tag-input-name"
              placeholder="Tag name (no spaces)"
            />
            <input
              v-model="newColor"
              type="color"
              class="form-control form-control-sm tag-input-color"
            />
            <button class="btn btn-primary btn-sm" @click="createTag">
              Create
            </button>
          </div>
        </div>
      </div>

      <table class="table">
        <thead>
          <tr>
            <th>Color</th>
            <th>Name</th>
            <th>Articles</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="tag in p.tags" :key="tag.name">
            <td v-if="editingTag === tag.name">
              <input
                v-model="editColor"
                type="color"
                class="form-control form-control-sm tag-input-color"
              />
            </td>
            <td v-else>
              <span
                class="article-tag-badge"
                :style="{ backgroundColor: tag.color }"
              >
                &nbsp;
              </span>
            </td>
            <td v-if="editingTag === tag.name">
              <input
                v-model="editName"
                type="text"
                class="form-control form-control-sm tag-edit-name"
              />
            </td>
            <td v-else>{{ tag.name }}</td>
            <td>{{ tag.article_count }}</td>
            <td>
              <template v-if="editingTag === tag.name">
                <button
                  class="btn btn-success btn-sm me-1"
                  @click="saveEdit(tag.name)"
                >
                  Save
                </button>
                <button
                  class="btn btn-secondary btn-sm"
                  @click="editingTag = null"
                >
                  Cancel
                </button>
              </template>
              <template v-else>
                <button
                  class="btn btn-outline-primary btn-sm me-1"
                  @click="startEdit(tag)"
                >
                  Edit
                </button>
                <button
                  class="btn btn-outline-danger btn-sm"
                  @click="deleteTag(tag.name)"
                >
                  Delete
                </button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </Layout>
</template>
