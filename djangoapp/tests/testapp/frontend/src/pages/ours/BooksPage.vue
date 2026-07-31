<script setup lang="ts">
import { computed } from "vue"
import Layout from "../../components/Layout.vue"
import { z } from "zod"

const BookSchema = z.object({
  public_id: z.string(),
  title: z.string(),
  author: z.string(),
})

const props = defineProps<{ books: unknown[] }>()
const books = computed(() => BookSchema.array().parse(props.books))
</script>

<template>
  <Layout>
    <div class="container ours-books-page">
      <h1>Books</h1>
      <ul>
        <li v-for="book in books" :key="book.public_id">
          <strong>{{ book.title }}</strong> — {{ book.author }}
        </li>
      </ul>
    </div>
  </Layout>
</template>
