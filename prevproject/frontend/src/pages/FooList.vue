<script setup lang="ts">
import { Link } from "@inertiajs/vue3"

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- Inertia props are untyped
const { props } = defineProps<{ props: Record<string, any> }>()
</script>

<template>
  <div class="container py-4">
    <h1 class="h3 mb-3 text-capitalize">{{ props.viewname }}</h1>
    <ul class="list-group">
      <li v-for="row in props.rows" :key="row.id" class="list-group-item">
        <Link
          :href="`/${props.viewname}/id/${row.id}`"
          class="text-decoration-none"
        >
          {{ row.title }}
        </Link>
      </li>
    </ul>
  </div>
</template>
