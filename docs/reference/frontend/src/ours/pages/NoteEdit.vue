<script setup lang="ts">
import { computed } from "vue"
import { Link, router } from "@inertiajs/vue3"
import Layout from "../../components/Layout.vue"
import NoteForm from "../components/NoteForm.vue"
import { NoteEditPagePropsSchema } from "../schemas"
import "../style.scss"

const props = defineProps<{ props: object }>()
const p = computed(() => NoteEditPagePropsSchema.parse(props.props))

// After a save, visit the detail page so the new revision count shows.
function onSaved() {
  void router.visit(`/notes/${p.value.note.public_id}`)
}
</script>

<template>
  <Layout>
    <div class="ours-note-edit">
      <h1>Edit note</h1>
      <NoteForm :note="p.note" @saved="onSaved" />
      <Link class="text-muted" :href="`/notes/${p.note.public_id}`">Cancel</Link>
    </div>
  </Layout>
</template>
