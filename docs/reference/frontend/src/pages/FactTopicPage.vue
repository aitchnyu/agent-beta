<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import { z } from "zod"
import { FactOutSchema, TopicOutSchema } from "../schemas/facts_sdk"
import { useAppPage } from "../../system/utils/useAppPage"
import "../styles/app.scss"

const FactTopicPagePropsSchema = z.object({
  topic: TopicOutSchema,
  fact: FactOutSchema.nullable(),
  topics: TopicOutSchema.array(),
})

// Parsed reactively (computed inside useAppPage): reload-safe.
const { data: p } = useAppPage(FactTopicPagePropsSchema)
</script>

<template>
    <div class="ours-facts-page">
      <h1>{{ p.topic.name }}</h1>
      <p v-if="p.fact" class="ours-fact-text">{{ p.fact.text }}</p>
      <p v-else class="text-muted">No facts in this topic yet.</p>

      <p>
        <Link class="text-muted" href="/facts">All facts</Link>
      </p>

      <h2>Topics</h2>
      <ul class="ours-topics-list">
        <li v-for="t in p.topics" :key="t.public_id">
          <Link :href="`/facts/${t.slug}`">{{ t.name }}</Link>
        </li>
      </ul>
    </div>
</template>
