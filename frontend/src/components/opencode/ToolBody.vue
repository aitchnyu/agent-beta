<script setup lang="ts">
import { computed } from "vue"

// Shared tool output/content body: a white box. When `lineNumbers` is set (read
// output arrives as "21: <code>"), the leading "<num>:" prefix of each line is
// split out and deemphasized so the code reads primary.
const props = withDefaults(
  defineProps<{ text: string; lineNumbers?: boolean }>(),
  {
    lineNumbers: false,
  },
)

const lines = computed(() =>
  props.text.split("\n").map((line) => {
    if (!props.lineNumbers) return { prefix: "", body: line }
    const m = line.match(/^(\s*\d+:)(.*)$/)
    return m ? { prefix: m[1], body: m[2] } : { prefix: "", body: line }
  }),
)
</script>

<template>
  <pre
    class="opencode-tool-body"
  ><template v-for="(l, i) in lines" :key="i"><span
      v-if="l.prefix"
      class="opencode-lineno"
    >{{ l.prefix }}</span>{{ l.body }}{{ i < lines.length - 1 ? "\n" : "" }}</template></pre>
</template>
