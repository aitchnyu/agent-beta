<script setup lang="ts">
import { computed } from "vue"
import { Link } from "@inertiajs/vue3"
import Layout from "../../components/Layout.vue"
import { FactsPagePropsSchema } from "../schemas"
import "../style.scss"

// Inertia wraps the page data under a `props` key (page.props.props); parse it.
const props = defineProps<{ props: object }>()
const p = computed(() => FactsPagePropsSchema.parse(props.props))
</script>

<template>
  <Layout>
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
  </Layout>
</template>
