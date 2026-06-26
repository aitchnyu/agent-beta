<script setup lang="ts">
import Layout from "../components/Layout.vue"
import { Link } from "@inertiajs/vue3"
import { DebugViewSchema } from "../schemas.js"

const props = defineProps<{
  props: object
}>()

const validatedProps = DebugViewSchema.parse(props.props)
</script>

<template>
  <Layout :user="validatedProps.user">
    <ul class="list-group list-group-flush">
      <li
        v-for="table_and_url in validatedProps.table_urls"
        :key="table_and_url.name"
        class="list-group-item"
      >
        <Link :href="table_and_url.url">
          {{ table_and_url.name }}
        </Link>
      </li>
    </ul>
  </Layout>
</template>
