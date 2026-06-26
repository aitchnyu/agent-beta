<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import { ref } from "vue"
import AuthorChange from "../components/article-history/AuthorChange.vue"
import ContentChange from "../components/article-history/ContentChange.vue"
import PublishedDateChange from "../components/article-history/PublishedDateChange.vue"
import PublicIdChange from "../components/article-history/PublicIdChange.vue"
import TagsChange from "../components/article-history/TagsChange.vue"
import TitleChange from "../components/article-history/TitleChange.vue"
import Layout from "../components/Layout.vue"
import { ArticleHistoryPropsSchema } from "../schemas.ts"

const props = defineProps<{
  props: object
}>()

const p = ArticleHistoryPropsSchema.parse(props.props)
const pathPrefix = p.path_prefix

const fullyExpanded = ref<Record<number, boolean>>({})

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function actionLabel(action: string): string {
  switch (action) {
    case "created":
      return "Created"
    case "edited":
      return "Edited"
    case "deleted":
      return "Deleted"
    default:
      return action
  }
}
</script>

<template>
  <Layout :user="p.user">
    <div class="container article-history-page">
      <Link
        :href="`${pathPrefix}/id/${p.article_public_id}`"
        class="small text-muted text-decoration-none"
      >
        &larr; Back to Article
      </Link>
      <h1 class="mt-2">History: {{ p.article_title }}</h1>

      <div v-if="p.entries.length === 0" class="text-muted py-4">
        No history entries.
      </div>

      <div class="article-history-timeline">
        <div
          v-for="entry in p.entries"
          :key="entry.id"
          class="article-history-entry"
        >
          <div class="article-history-header">
            <span class="article-history-action">{{
              actionLabel(entry.action)
            }}</span>
            <span class="article-history-time">{{
              formatTime(entry.time)
            }}</span>
          </div>

          <div class="article-history-diffs">
            <div v-if="entry.changes?.title" class="article-history-diff">
              <span class="article-history-field">Title:</span>
              <template v-if="entry.action === 'edited'">
                <span class="article-history-old">
                  <TitleChange :value="entry.changes.title.old" />
                </span>
                <span class="article-history-arrow">&rarr;</span>
              </template>
              <span class="article-history-new">
                <TitleChange :value="entry.changes.title.new" />
              </span>
            </div>

            <div v-if="entry.changes?.public_id" class="article-history-diff">
              <span class="article-history-field">Public ID:</span>
              <template v-if="entry.action === 'edited'">
                <span class="article-history-old">
                  <PublicIdChange :value="entry.changes.public_id.old" />
                </span>
                <span class="article-history-arrow">&rarr;</span>
              </template>
              <span class="article-history-new">
                <PublicIdChange :value="entry.changes.public_id.new" />
              </span>
            </div>

            <div
              v-if="entry.changes?.published_date"
              class="article-history-diff"
            >
              <span class="article-history-field">Published:</span>
              <template v-if="entry.action === 'edited'">
                <span class="article-history-old">
                  <PublishedDateChange
                    :value="entry.changes.published_date.old"
                  />
                </span>
                <span class="article-history-arrow">&rarr;</span>
              </template>
              <span class="article-history-new">
                <PublishedDateChange
                  :value="entry.changes.published_date.new"
                />
              </span>
            </div>

            <div v-if="entry.changes?.tags" class="article-history-diff">
              <span class="article-history-field">Tags:</span>
              <template v-if="entry.action === 'edited'">
                <span class="article-history-old">
                  <TagsChange :value="entry.changes.tags.old" />
                </span>
                <span class="article-history-arrow">&rarr;</span>
              </template>
              <span class="article-history-new">
                <TagsChange :value="entry.changes.tags.new" />
              </span>
            </div>

            <div v-if="entry.changes?.author" class="article-history-diff">
              <span class="article-history-field">Author:</span>
              <template v-if="entry.action === 'edited'">
                <span class="article-history-old">
                  <AuthorChange :value="entry.changes.author.old" />
                </span>
                <span class="article-history-arrow">&rarr;</span>
              </template>
              <span class="article-history-new">
                <AuthorChange :value="entry.changes.author.new" />
              </span>
            </div>

            <div v-if="entry.changes?.content" class="article-history-diff">
              <span class="article-history-field">Content:</span>
              <div class="article-history-content-sections">
                <div
                  v-if="entry.action === 'edited'"
                  class="article-history-content-section"
                >
                  <div class="article-history-content-label">Before</div>
                  <ContentChange
                    :value="entry.changes.content.old"
                    :isExpanded="!!fullyExpanded[entry.id]"
                  />
                </div>
                <div class="article-history-content-section">
                  <div class="article-history-content-label">
                    {{ entry.action === "edited" ? "After" : "Content" }}
                  </div>
                  <ContentChange
                    :value="entry.changes.content.new"
                    :isExpanded="!!fullyExpanded[entry.id]"
                  />
                </div>
              </div>
              <button
                v-if="!fullyExpanded[entry.id]"
                class="article-history-content-expand"
                @click="fullyExpanded[entry.id] = true"
              >
                Show more
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Layout>
</template>
