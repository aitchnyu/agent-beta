<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import { z } from "zod"
import { FactOutSchema, TopicOutSchema } from "../schemas/facts_sdk"
import { useAppPage } from "../../system/utils/useAppPage"
import "../styles/facts.scss"

// The Inertia page data is nested under `props` (page.props.props).
const FactsPagePropsSchema = z.object({
  fact: FactOutSchema.nullable(),
  topics: TopicOutSchema.array(),
})

// Parsed reactively (computed inside useAppPage): reload-safe.
const { data: p } = useAppPage(FactsPagePropsSchema)
</script>

<template>
    <div class="ours-facts-page">
      <h1>Random Fact</h1>
      <p v-if="p.fact" class="ours-fact-text">{{ p.fact.text }}</p>
      <p v-else class="text-muted">No facts yet — run <code>./run djangomanage seedfacts</code>.</p>
      <p v-if="p.fact" class="text-muted">
        Topic:
        <Link :href="`/facts/${p.fact.topic.slug}`">{{ p.fact.topic.name }}</Link>
      </p>

      <h2>Topics</h2>
      <ul class="ours-topics-list">
        <li v-for="t in p.topics" :key="t.public_id">
          <Link :href="`/facts/${t.slug}`">{{ t.name }}</Link>
        </li>
      </ul>
    </div>
</template>
