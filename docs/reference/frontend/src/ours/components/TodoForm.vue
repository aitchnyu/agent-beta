<script setup lang="ts">
import { ref } from "vue"
import { postJSON } from "../../utils/http"
import { showErrorToast } from "../../utils/sweetalert"
import { type TodoOut } from "../schemas"

// Create mode (no `todo` prop): POST /todos/create, then emit "created".
const props = defineProps<{ todo?: TodoOut }>()
const emit = defineEmits<{ created: [] }>()

const text = ref(props.todo?.text ?? "")

async function submit() {
  try {
    await postJSON("/todos/create", { text: text.value })
    text.value = ""
    emit("created")
  } catch (e) {
    showErrorToast(e, "Could not create todo")
  }
}
</script>

<template>
  <form class="ours-todo-form mb-4" @submit.prevent="submit">
    <input
      v-model="text"
      class="form-control mb-2"
      placeholder="What needs doing?"
      aria-label="New todo"
      required
    />
    <button class="btn btn-primary btn-sm" type="submit">Add todo</button>
  </form>
</template>
