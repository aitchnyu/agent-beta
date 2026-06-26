<script setup lang="ts">
import { Link, router } from "@inertiajs/vue3"
import { computed, ref, watch } from "vue"
import axios from "axios"
import Multiselect from "vue-multiselect"
import Layout from "../components/Layout.vue"
import { showErrorToast } from "../utils/sweetalert"
import {
  ArticleListPropsSchema,
  type ArticleTagItem,
  type ArticleUserProfile,
} from "../schemas.ts"

const props = defineProps<{
  props: object
}>()

const p = ArticleListPropsSchema.parse(props.props)
const pathPrefix = p.path_prefix

const currentPage = ref(p.pagination.page)
const showUnpublished = ref(p.filters.unpublished)
const selectedAuthors = ref<ArticleUserProfile[]>(p.selected_authors)
const selectedTags = ref<ArticleTagItem[]>(p.selected_tags)
const authorOptions = ref<ArticleUserProfile[]>(p.selected_authors)
const tagOptions = ref<ArticleTagItem[]>(p.selected_tags)
const sortBy = ref(p.filters.sort_by)

const allPages = computed(() =>
  Array.from({ length: p.pagination.total_pages }, (_, i) => i + 1),
)

function buildUrl(page?: number) {
  const params = new URLSearchParams()
  if (page && page > 1) params.set("page", String(page))
  if (showUnpublished.value && p.is_editor) params.set("unpublished", "true")
  for (const a of selectedAuthors.value) {
    params.append("author", String(a.id))
  }
  for (const t of selectedTags.value) {
    params.append("tag", t.name)
  }
  if (sortBy.value && sortBy.value !== "published_at") {
    params.set("sort_by", sortBy.value)
  }
  const qs = params.toString()
  return `${pathPrefix}/list${qs ? `?${qs}` : ""}`
}

function navigateToPage(page: number) {
  router.visit(buildUrl(page))
}

function applyFilters() {
  router.visit(buildUrl(1))
}

watch(showUnpublished, () => {
  applyFilters()
})

watch(sortBy, () => {
  applyFilters()
})

async function searchAuthors(query: string) {
  try {
    const response = await axios.get(`${pathPrefix}/api/search-authors`, {
      params: { q: query },
    })
    authorOptions.value = response.data.authors
  } catch (e: unknown) {
    showErrorToast(e, "Failed to load authors")
  }
}

async function searchTags(query: string) {
  try {
    const response = await axios.get(`${pathPrefix}/api/search-tags`, {
      params: { q: query },
    })
    tagOptions.value = response.data.tags
  } catch (e: unknown) {
    showErrorToast(e, "Failed to load tags")
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return "Draft"
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}
</script>

<template>
  <Layout :user="p.user">
    <div class="container articles-page">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h1>Articles</h1>
        <div class="d-flex align-items-center gap-2">
          <Link
            v-if="p.is_editor"
            :href="`${pathPrefix}/tag`"
            class="small text-muted text-decoration-none"
          >
            Manage Tags
          </Link>
          <Link
            v-if="p.is_editor"
            :href="`${pathPrefix}/create`"
            class="btn btn-primary"
          >
            Create Article
          </Link>
        </div>
      </div>

      <div class="articles-filters mb-3">
        <div class="row g-2 align-items-center">
          <div class="col-auto">
            <Multiselect
              v-model="selectedAuthors"
              :options="authorOptions"
              :multiple="true"
              :close-on-select="false"
              :preserve-search="true"
              :internal-search="false"
              :hide-selected="true"
              :allow-empty="true"
              placeholder="Filter by authors..."
              track-by="id"
              label="title"
              @search-change="searchAuthors"
              @update:model-value="applyFilters"
            />
          </div>
          <div class="col-auto">
            <Multiselect
              v-model="selectedTags"
              :options="tagOptions"
              :multiple="true"
              :close-on-select="false"
              :preserve-search="true"
              :internal-search="false"
              :hide-selected="true"
              :allow-empty="true"
              placeholder="Filter by tags..."
              track-by="name"
              label="name"
              @search-change="searchTags"
              @update:model-value="applyFilters"
            />
          </div>
          <div v-if="p.is_editor" class="col-auto">
            <div class="form-check">
              <input
                id="unpublished-check"
                v-model="showUnpublished"
                type="checkbox"
                class="form-check-input"
              />
              <label class="form-check-label" for="unpublished-check">
                Unpublished
              </label>
            </div>
          </div>
          <div class="col-auto">
            <select v-model="sortBy" class="form-select form-select-sm">
              <option value="published_at">Sort by published date</option>
              <option value="latest_comment">Sort by latest comment</option>
            </select>
          </div>
        </div>
      </div>

      <div class="articles-list">
        <div
          v-for="article in p.articles"
          :key="article.public_id"
          class="article-card card mb-3"
        >
          <div class="card-body d-flex">
            <div v-if="article.cover_image_url" class="article-card-cover me-3">
              <Link :href="`${pathPrefix}/id/${article.public_id}`">
                <img
                  :src="article.cover_image_url"
                  :alt="article.title"
                  class="article-card-cover-img"
                />
              </Link>
            </div>
            <div class="article-card-content flex-grow-1">
              <div class="d-flex align-items-center gap-2 mb-1">
                <Link
                  :href="`${pathPrefix}/id/${article.public_id}`"
                  class="article-card-title"
                >
                  {{ article.title }}
                </Link>
                <span
                  v-if="!article.published_at"
                  class="badge bg-warning text-dark"
                  >Draft</span
                >
              </div>
              <p class="article-card-excerpt text-muted mb-2">
                {{ article.excerpt }}
              </p>
              <div class="d-flex align-items-center gap-2 flex-wrap">
                <span
                  v-for="tag in article.tags"
                  :key="tag.name"
                  class="article-tag-badge"
                  :style="{ backgroundColor: tag.color }"
                >
                  {{ tag.name }}
                </span>
                <span class="text-muted article-card-meta">
                  <Link
                    v-if="article.author.public_id"
                    :href="`/users/id/${article.author.public_id}`"
                    class="article-author-link text-muted text-decoration-none"
                    >{{ article.author.title }}</Link
                  >
                  <template v-else>{{ article.author.title }}</template>
                  &middot;
                  {{ formatDate(article.published_at) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="p.articles.length === 0" class="text-center text-muted py-4">
          No articles found.
        </div>
      </div>

      <div
        v-if="p.pagination.total_pages > 1"
        class="d-flex align-items-center articles-pagination mt-3"
      >
        <div class="me-2">
          Page
          <select
            :value="currentPage"
            class="form-select d-inline-block w-auto mx-1"
            @change="
              navigateToPage(Number(($event.target as HTMLSelectElement).value))
            "
          >
            <option v-for="pg in allPages" :key="pg" :value="pg">
              {{ pg }}
            </option>
          </select>
          of {{ p.pagination.total_pages }}
        </div>
        <Link :href="buildUrl(1)" class="btn btn-outline-primary btn-sm me-2">
          First
        </Link>
        <Link
          v-if="currentPage > 1"
          :href="buildUrl(currentPage - 1)"
          class="btn btn-secondary btn-sm me-2"
        >
          Prev
        </Link>
        <Link
          v-if="currentPage < p.pagination.total_pages"
          :href="buildUrl(currentPage + 1)"
          class="btn btn-secondary btn-sm"
        >
          Next
        </Link>
        <span class="text-muted ms-2"
          >{{ p.pagination.total_count }} articles total</span
        >
      </div>
    </div>
  </Layout>
</template>
