<script setup lang="ts">
import { computed } from "vue"
import { Link } from "@inertiajs/vue3"
import { FactTopicPagePropsSchema } from "../schemas"
import "../style.scss"

// Inertia wraps the page data under a `props` key (page.props.props); parse it.
const props = defineProps<{ props: object }>()
const p = computed(() => FactTopicPagePropsSchema.parse(props.props))
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
