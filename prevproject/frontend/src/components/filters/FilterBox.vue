<script setup lang="ts">
interface Props {
  active?: boolean
}
defineProps<Props>()
</script>

<template>
  <div class="filter-box" :class="{ 'filter-box-active': active }">
    <slot></slot>
  </div>
</template>
