<script setup lang="ts">
import axios from "axios"
import { ref } from "vue"
import { showErrorToast } from "../../utils/sweetalert"
import { NoteSchema, type NoteOut } from "../schemas"

// Create mode (no `note` prop): POST /notes/create, then emit "created".
// Edit mode (`note` prop): PUT /notes/<id>, then emit "saved" with the result.
const props = defineProps<{ note?: NoteOut }>()
const emit = defineEmits<{ created: []; saved: [note: NoteOut] }>()

const title = ref(props.note?.title ?? "")
const body = ref(props.note?.body ?? "")

async function submit() {
  try {
    if (props.note) {
      const resp = await axios.put(`/notes/${props.note.public_id}`, {
        title: title.value,
        body: body.value,
      })
      emit("saved", NoteSchema.parse(resp.data))
    } else {
      await axios.post("/notes/create", { title: title.value, body: body.value })
      title.value = ""
      body.value = ""
      emit("created")
    }
  } catch (e) {
    showErrorToast(e, props.note ? "Could not save note" : "Could not create note")
  }
}
</script>

<template>
  <form class="ours-note-form mb-4" @submit.prevent="submit">
    <input v-model="title" class="form-control mb-2" placeholder="Title" aria-label="Title" required />
    <textarea v-model="body" class="form-control mb-2" placeholder="Body" />
    <button class="btn btn-primary btn-sm" type="submit">
      {{ props.note ? "Save note" : "Add note" }}
    </button>
  </form>
</template>
