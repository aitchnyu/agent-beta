<script setup lang="ts">
import axios from "axios"
import { reactive, ref } from "vue"
import { router } from "@inertiajs/vue3"
import Layout from "../components/Layout.vue"
import ArticleForm from "../components/ArticleForm.vue"
import { humanSize } from "../utils/format"
import { showErrorToast } from "../utils/sweetalert"
import {
  ArticleEditPropsSchema,
  type ArticleFormData,
  type ArticleUserProfile,
} from "../schemas.js"

const props = defineProps<{
  props: object
}>()

const p = ArticleEditPropsSchema.parse(props.props)
const pathPrefix = p.path_prefix

const form = reactive<ArticleFormData>({
  title: p.article.title,
  publicId: p.article.public_id,
  content: p.article.content,
  selectedTags: [...p.article.tags],
  isCommentingEnabled: p.article.is_commenting_enabled,
  isPublished: !!p.article.published_at,
})
const selectedAuthor = ref<ArticleUserProfile | null>(p.article.author)
const isSubmitting = ref(false)

async function onSubmit() {
  isSubmitting.value = true

  try {
    const response = await axios.post(
      `${pathPrefix}/edit/${p.article.public_id}`,
      {
        title: form.title,
        public_id: form.publicId,
        content: form.content,
        published: form.isPublished,
        tags: form.selectedTags.map((t) => t.name),
        author_id: selectedAuthor.value?.id,
        is_commenting_enabled: form.isCommentingEnabled,
      },
    )
    const id = response.data.id
    router.visit(`${pathPrefix}/id/${id}`)
  } catch (e: unknown) {
    showErrorToast(e, "Failed to update article")
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <Layout :user="p.user">
    <div class="container article-edit-page">
      <h1>Edit Article</h1>
      <div v-if="p.media_summary" class="media-summary mb-3">
        <span class="text-muted">
          Media: {{ humanSize(p.media_summary.total_bytes) }} of
          {{ humanSize(p.media_summary.quota_bytes) }}
        </span>
      </div>

      <ArticleForm
        :form="form"
        :selected-author="selectedAuthor"
        :path-prefix="pathPrefix"
        :is-submitting="isSubmitting"
        :article-public-id="p.article.public_id"
        :is-editor="p.is_editor"
        @update:selected-author="selectedAuthor = $event"
        @submit="onSubmit"
      />
    </div>
  </Layout>
</template>
