<script setup lang="ts">
import { computed } from "vue"
import { Link } from "@inertiajs/vue3"
import { z } from "zod"
import PageTitle from "../../system/components/PageTitle.vue"
import { FactSchema, TopicSchema } from "../schemas/facts"
import "../styles/app.scss"

// One specific fact by public_id (a stable permalink; non-null or the route 404s).
const FactPagePropsSchema = z.object({
  fact: FactSchema,
  topics: TopicSchema.array(),
})

// Inertia wraps the page data under a `props` key (page.props.props); parse it.
const props = defineProps<{ props: object }>()
const p = computed(() => FactPagePropsSchema.parse(props.props))
</script>

<template>
    <PageTitle value="Fact" />
    <div class="ours-facts-page">
      <h1>Fact</h1>
      <p class="ours-fact-text">{{ p.fact.text }}</p>
      <p class="text-muted">
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
