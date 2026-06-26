<script setup lang="ts">
import axios from "axios"
import { reactive, ref } from "vue"
import { router } from "@inertiajs/vue3"
import Layout from "../components/Layout.vue"
import ArticleForm from "../components/ArticleForm.vue"
import { showErrorToast } from "../utils/sweetalert"
import { ArticleCreatePropsSchema, type ArticleFormData } from "../schemas.js"

const props = defineProps<{
  props: object
}>()

const p = ArticleCreatePropsSchema.parse(props.props)
const pathPrefix = p.path_prefix

const form = reactive<ArticleFormData>({
  title: "",
  publicId: "",
  content: "",
  selectedTags: [],
  isCommentingEnabled: true,
  isPublished: false,
})
const isSubmitting = ref(false)

async function onSubmit() {
  isSubmitting.value = true

  try {
    const response = await axios.post(`${pathPrefix}/create`, {
      title: form.title,
      public_id: form.publicId,
      content: form.content,
      published: form.isPublished,
      tags: form.selectedTags.map((t) => t.name),
      is_commenting_enabled: form.isCommentingEnabled,
    })
    const id = response.data.id
    router.visit(`${pathPrefix}/id/${id}`)
  } catch (e: unknown) {
    showErrorToast(e, "Failed to create article")
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <Layout :user="p.user">
    <div class="container article-create-page">
      <h1>Create Article</h1>
      <ArticleForm
        :form="form"
        :path-prefix="pathPrefix"
        :is-submitting="isSubmitting"
        :is-create="true"
        :is-editor="p.is_editor"
        @submit="onSubmit"
      />
    </div>
  </Layout>
</template>
