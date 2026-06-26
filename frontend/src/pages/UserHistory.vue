<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import Layout from "../components/Layout.vue"
import RenderRawHtml from "../components/RenderRawHtml.vue"
import { UserHistoryPropsSchema } from "../schemas.ts"

const props = defineProps<{
  props: object
}>()

const p = UserHistoryPropsSchema.parse(props.props)
const pathPrefix = p.path_prefix

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

type StrChange = { old: string; new: string }
type BoolChange = { old: boolean; new: boolean }
type Changes = {
  first_name: StrChange | null
  last_name: StrChange | null
  email: StrChange | null
  description: StrChange | null
  has_public_profile: BoolChange | null
  is_active: BoolChange | null
  is_staff: BoolChange | null
  is_superuser: BoolChange | null
}

interface FieldDiff {
  label: string
  old: string
  new: string
  html: boolean
}

function fieldLabel(key: string): string {
  const labels: Record<string, string> = {
    first_name: "First name",
    last_name: "Last name",
    email: "Email",
    description: "Description",
    has_public_profile: "Public profile",
    is_active: "Active",
    is_staff: "Staff",
    is_superuser: "Superuser",
  }
  return labels[key] ?? key
}

function diffsFor(changes: Changes): FieldDiff[] {
  const out: FieldDiff[] = []
  for (const [key, change] of Object.entries(changes)) {
    if (!change) continue
    out.push({
      label: fieldLabel(key),
      old: String(change.old),
      new: String(change.new),
      html: key === "description",
    })
  }
  return out
}
</script>

<template>
  <Layout :user="p.user" :is-superuser="true">
    <div class="container user-history-page">
      <Link
        :href="`${pathPrefix}/id/${p.target_public_id}`"
        class="small text-muted text-decoration-none"
      >
        &larr; Back to User
      </Link>
      <h1 class="mt-2">History: {{ p.target_title }}</h1>

      <div v-if="p.entries.length === 0" class="text-muted py-4">
        No history entries.
      </div>

      <div class="user-history-timeline">
        <div
          v-for="entry in p.entries"
          :key="entry.public_id"
          class="user-history-entry card mb-2"
        >
          <div class="card-body">
            <div class="d-flex justify-content-between mb-2">
              <span class="badge bg-secondary">{{
                actionLabel(entry.action)
              }}</span>
              <span class="text-muted small">{{ formatTime(entry.time) }}</span>
            </div>
            <div
              v-for="diff in diffsFor(entry.changes)"
              :key="diff.label"
              class="user-history-diff mb-1"
            >
              <span class="user-history-field text-muted"
                >{{ diff.label }}:</span
              >
              <template v-if="diff.html">
                <div class="user-history-content-sections">
                  <div
                    v-if="entry.action === 'edited'"
                    class="user-history-content-section"
                  >
                    <div class="user-history-content-label">Before</div>
                    <RenderRawHtml
                      :html="diff.old"
                      className="user-history-content-body"
                    />
                  </div>
                  <div class="user-history-content-section">
                    <div class="user-history-content-label">
                      {{ entry.action === "edited" ? "After" : "Content" }}
                    </div>
                    <RenderRawHtml
                      :html="diff.new"
                      className="user-history-content-body"
                    />
                  </div>
                </div>
              </template>
              <template v-else>
                <template v-if="entry.action === 'edited'">
                  <span class="user-history-old">{{ diff.old }}</span>
                  <span class="user-history-arrow">&rarr;</span>
                </template>
                <span class="user-history-new">{{ diff.new }}</span>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Layout>
</template>
