<script setup lang="ts">
import { Link } from "@inertiajs/vue3"

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- Inertia props are untyped
const { props } = defineProps<{ props: Record<string, any> }>()
</script>

<template>
  <div class="container py-4">
    <h1>{{ props.title }}</h1>
    <dl class="foo-details">
      <template v-for="name in props.column_names" :key="name">
        <dt>{{ name }}</dt>
        <dd>{{ props.cell_values[name] }}</dd>
      </template>
    </dl>
    <Link
      v-if="props.can_edit"
      :href="`/${props.viewname}/update/${props.id}`"
      class="btn btn-primary"
    >
      Edit
    </Link>
  </div>
</template>
