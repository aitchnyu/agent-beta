<script setup lang="ts">
import axios from "axios"
import { Link } from "@inertiajs/vue3"
import { computed, ref } from "vue"
import Layout from "../components/Layout.vue"
import RenderRawHtml from "../components/RenderRawHtml.vue"
import ArticleCommentSection from "../components/ArticleCommentSection.vue"
import { humanSize } from "../utils/format"
import { showConfirm, showErrorToast, showToast } from "../utils/sweetalert"
import { ArticleDetailsPropsSchema } from "../schemas.js"

const props = defineProps<{
  props: object
}>()

const p = ArticleDetailsPropsSchema.parse(props.props)
const pathPrefix = p.path_prefix
const showMedia = ref(false)
const subscribed = ref(p.is_subscribed)
const isSubscribing = ref(false)

function formatDate(iso: string | null): string {
  if (!iso) return "Draft"
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

const mediaUsage = computed(() => {
  if (!p.media_summary) return ""
  return `${humanSize(p.media_summary.total_bytes)} of ${humanSize(p.media_summary.quota_bytes)}`
})

async function deleteArticle() {
  const confirmed = await showConfirm({ title: "Delete this article?" })
  if (!confirmed) return
  try {
    await axios.post(`${pathPrefix}/delete/${p.article.public_id}`)
    showToast("success", "Article deleted")
    window.location.href = `${pathPrefix}/list`
  } catch (e) {
    showErrorToast(e, "Failed to delete article")
  }
}

async function toggleSubscription() {
  if (isSubscribing.value) return
  const wasSubscribed = subscribed.value
  const endpoint = wasSubscribed ? "unsubscribe" : "subscribe"
  subscribed.value = !wasSubscribed
  isSubscribing.value = true
  try {
    await axios.post(`${pathPrefix}/api/${endpoint}/${p.article.public_id}`)
    showToast("success", wasSubscribed ? "Unsubscribed" : "Subscribed")
  } catch (e) {
    subscribed.value = wasSubscribed
    showErrorToast(e, "Failed to update subscription")
  } finally {
    isSubscribing.value = false
  }
}
</script>

<template>
  <Layout :user="p.user">
    <div class="container article-details-page">
      <Link
        :href="`${pathPrefix}/list`"
        class="small text-muted text-decoration-none"
      >
        &larr; Back to Articles
      </Link>
      <div class="d-flex justify-content-between align-items-start mb-3">
        <div>
          <h1>{{ p.article.title }}</h1>
          <div class="d-flex align-items-center gap-2 flex-wrap mb-2">
            <span
              v-if="!p.article.published_at"
              class="badge bg-warning text-dark"
              >Draft</span
            >
            <span
              v-for="tag in p.article.tags"
              :key="tag.name"
              class="article-tag-badge"
              :style="{ backgroundColor: tag.color }"
            >
              {{ tag.name }}
            </span>
          </div>
          <div class="text-muted">
            By
            <Link
              v-if="p.article.author.public_id"
              :href="`/users/id/${p.article.author.public_id}`"
              class="article-author-link text-muted text-decoration-none"
              >{{ p.article.author.title }}</Link
            >
            <template v-else>{{ p.article.author.title }}</template>
            &middot;
            {{ formatDate(p.article.published_at) }}
          </div>
        </div>
        <div class="d-flex flex-column align-items-end gap-2">
          <button
            v-if="p.user !== null && !!p.article.published_at"
            class="btn btn-sm btn-subscribe"
            :class="subscribed ? 'btn-outline-secondary' : 'btn-primary'"
            :disabled="isSubscribing"
            @click="toggleSubscription"
          >
            {{ subscribed ? "Unsubscribe" : "Subscribe" }}
          </button>
          <div v-if="p.can_edit || p.can_delete" class="d-flex gap-2">
            <Link
              v-if="p.can_edit && p.history_count > 0"
              :href="`${pathPrefix}/history/${p.article.public_id}`"
              class="small text-muted text-decoration-none"
            >
              {{ p.history_count }} history entries
            </Link>
            <Link
              v-if="p.can_edit"
              :href="`${pathPrefix}/edit/${p.article.public_id}`"
              class="btn btn-outline-primary btn-sm"
            >
              Edit
            </Link>
            <button
              v-if="p.can_delete"
              class="btn btn-outline-danger btn-sm"
              @click="deleteArticle"
            >
              Delete
            </button>
          </div>
        </div>
      </div>

      <RenderRawHtml
        :html="p.article.content"
        className="rich-text-display article-details-content"
      />

      <div v-if="p.media_summary" class="media-summary mt-4">
        <span class="media-summary-toggle" @click="showMedia = !showMedia">
          {{ showMedia ? "Hide" : "Show" }} media ({{ mediaUsage }})
        </span>
        <div v-if="showMedia" class="media-summary-box">
          <div
            v-for="img in p.media_summary.images"
            :key="img.uuid_id"
            class="media-summary-image"
          >
            <img :src="img.image_url" class="media-summary-thumb" />
            <span class="media-summary-size">{{ humanSize(img.size) }}</span>
          </div>
        </div>
      </div>

      <ArticleCommentSection
        :publicId="p.article.public_id"
        :pathPrefix="p.path_prefix"
        :canComment="
          p.is_commenting_enabled && p.user !== null && !!p.article.published_at
        "
        :canDeleteAny="p.can_delete"
        :userId="p.user?.id ?? null"
      />
    </div>
  </Layout>
</template>
