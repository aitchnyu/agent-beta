<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import { onMounted, onUnmounted, ref, watch } from "vue"
import axios from "axios"
import Quill from "quill"
import Multiselect from "vue-multiselect"
import {
  type ArticleFormData,
  type ArticleTagItem,
  type ArticleUserProfile,
} from "../schemas.js"
import { showErrorToast } from "../utils/sweetalert"

interface Props {
  form: ArticleFormData
  selectedAuthor?: ArticleUserProfile | null
  pathPrefix: string
  isSubmitting: boolean
  articlePublicId?: string
  isCreate?: boolean
  isEditor?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  "update:selectedAuthor": [value: ArticleUserProfile | null]
  submit: []
}>()

const editorRef = ref<HTMLDivElement | null>(null)
let quillInstance: Quill | null = null
let isInternalChange = false

const tagOptions = ref<ArticleTagItem[]>([])
const authorOptions = ref<ArticleUserProfile[]>([])
const isUploading = ref(false)

function setHTML(html: string) {
  if (!quillInstance) return
  if (quillInstance.root.innerHTML !== html) {
    isInternalChange = true
    quillInstance.root.innerHTML = html || "<p></p>"
    isInternalChange = false
  }
}

function onTextChange() {
  if (!quillInstance || isInternalChange) return
  // eslint-disable-next-line vue/no-mutating-props -- form is a reactive object passed by reference, mutations flow to parent
  props.form.content = quillInstance!.root.innerHTML
}

onMounted(() => {
  if (!editorRef.value) return

  quillInstance = new Quill(editorRef.value, {
    theme: "snow",
    placeholder: "Write your article...",
    modules: {
      toolbar: {
        container: [
          [{ header: [1, 2, 3, 4, 5, 6, false] }],
          ["bold", "italic"],
          [{ list: "ordered" }, { list: "bullet" }],
          ...(props.isCreate ? [] : [["link", "image"]]),
          ["clean"],
        ],
        handlers: {
          image: function () {
            const input = document.createElement("input")
            input.setAttribute("type", "file")
            input.setAttribute("accept", "image/*")
            input.click()
            input.onchange = async () => {
              const file = input.files?.[0]
              if (!file) return
              await uploadImage(file)
            }
          },
        },
      },
    },
  })

  if (props.form.content) {
    setHTML(props.form.content)
  }

  quillInstance.on("text-change", onTextChange)
})

watch(
  () => props.form.content,
  (newValue) => {
    if (!quillInstance || isInternalChange) return
    setHTML(newValue)
  },
)

onUnmounted(() => {
  if (quillInstance) {
    quillInstance.off("text-change", onTextChange)
    quillInstance = null
  }
})

async function uploadImage(file: File) {
  isUploading.value = true

  if (props.articlePublicId) {
    const formData = new FormData()
    formData.append("image", file)

    try {
      const response = await axios.post(
        `${props.pathPrefix}/api/upload-image/${props.articlePublicId}`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } },
      )
      const url = response.data.url
      if (quillInstance) {
        const range = quillInstance.getSelection(true)
        quillInstance.insertEmbed(range.index, "image", url)
        quillInstance.setSelection(range.index + 1)
      }
    } catch (e: unknown) {
      showErrorToast(e, "Failed to upload image")
    } finally {
      isUploading.value = false
    }
  }
}

async function searchTags(query: string) {
  try {
    const response = await axios.get(`${props.pathPrefix}/api/search-tags`, {
      params: { q: query },
    })
    tagOptions.value = response.data.tags
  } catch (e: unknown) {
    showErrorToast(e, "Failed to load tags")
    tagOptions.value = []
  }
}

async function searchAuthors(query: string) {
  try {
    const response = await axios.get(`${props.pathPrefix}/api/search-authors`, {
      params: { q: query },
    })
    authorOptions.value = response.data.authors
  } catch (e: unknown) {
    showErrorToast(e, "Failed to load authors")
    authorOptions.value = []
  }
}
</script>

<template>
  <!-- eslint-disable vue/no-mutating-props -- form is a reactive object passed by reference, mutations are intentional -->
  <div class="article-form">
    <div class="mb-3">
      <label class="form-label">Title</label>
      <input type="text" class="form-control" v-model="form.title" />
    </div>

    <div class="mb-3">
      <label class="form-label">Public ID</label>
      <input
        type="text"
        class="form-control"
        v-model="form.publicId"
        placeholder="Auto-generated if left empty"
      />
    </div>

    <div class="mb-3">
      <div class="d-flex align-items-center gap-2">
        <label class="form-label mb-0">Tags</label>
        <Link
          v-if="isEditor"
          :href="`${pathPrefix}/tag`"
          class="small text-muted text-decoration-none"
        >
          Manage Tags
        </Link>
      </div>
      <Multiselect
        v-model="form.selectedTags"
        :options="tagOptions"
        :multiple="true"
        :close-on-select="false"
        :preserve-search="true"
        :internal-search="false"
        :hide-selected="true"
        :allow-empty="true"
        placeholder="Search tags..."
        track-by="name"
        label="name"
        @search-change="searchTags"
      />
    </div>

    <div v-if="!isCreate && isEditor" class="mb-3">
      <label class="form-label">Author</label>
      <Multiselect
        :model-value="selectedAuthor ?? null"
        :options="authorOptions"
        :multiple="false"
        :close-on-select="true"
        :preserve-search="true"
        :internal-search="false"
        :allow-empty="false"
        placeholder="Search author..."
        track-by="id"
        label="title"
        @update:model-value="
          emit('update:selectedAuthor', $event as ArticleUserProfile | null)
        "
        @search-change="searchAuthors"
      />
    </div>

    <div class="mb-3">
      <label class="form-label">Content</label>
      <div v-if="isCreate" class="alert alert-info py-1">
        Save the article first to upload images.
      </div>
      <div class="rich-text-editor-wrapper">
        <div ref="editorRef" class="rich-text-editor quill-editor"></div>
      </div>
    </div>

    <div class="mb-3 form-check form-switch">
      <input
        class="form-check-input"
        type="checkbox"
        role="switch"
        id="commentingEnabled"
        v-model="form.isCommentingEnabled"
      />
      <label class="form-check-label" for="commentingEnabled"
        >Enable comments</label
      >
    </div>

    <div class="mb-3 form-check form-switch">
      <input
        class="form-check-input"
        type="checkbox"
        role="switch"
        id="publishedCheckbox"
        v-model="form.isPublished"
      />
      <label class="form-check-label" for="publishedCheckbox">Publish</label>
    </div>

    <div class="d-flex gap-2">
      <button
        class="btn btn-primary"
        :disabled="isSubmitting"
        @click="emit('submit')"
      >
        {{ isSubmitting ? "Saving..." : "Save" }}
      </button>
    </div>
  </div>
</template>
