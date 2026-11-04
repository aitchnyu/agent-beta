<script setup lang="ts">
// MAINTAIN-CONSISTENCY repo-map: excerpted in .pi/repo-map.md §9 — change both together.
import { computed, ref } from "vue"
import { router } from "@inertiajs/vue3"
import { z } from "zod"
import TodoForm from "../components/TodoForm.vue"
import { TodoSchema, type TodoOut } from "../schemas/todos"
import { postJSON } from "../../system/utils/http"
import { useAppPage } from "../../system/utils/useAppPage"
import { showErrorToast } from "../../system/utils/sweetalert"
import "../styles/app.scss"

const TodosPagePropsSchema = z.object({
  todos: TodoSchema.array(),
})

// The page's own data: useAppPage parses the inner `props` key REACTIVELY
// (computed inside) — after any router.reload() the list re-renders from
// the fresh server payload.
const { data: p } = useAppPage(TodosPagePropsSchema)
const todos = computed(() => p.value.todos)
// Guard the toggle POST + reload so a double-click can't fire two toggles.
const toggling = ref<string | null>(null)

async function reload() {
  // The server is the source of truth — reload the props after any mutation.
  try {
    await router.reload()
  } catch (e) {
    showErrorToast(e, "Could not reload todos")
  }
}

function onCreated() {
  // The form's create POST succeeded; a reload lands the row via props.
  void reload()
}

async function toggle(todo: TodoOut) {
  if (toggling.value !== null) return
  toggling.value = todo.public_id
  try {
    // Optimistic-lock echo (the frontend half of the pattern; the backend half
    // is save_plus' expected_row_version): send the row_version this
    // list was rendered with — a fresh create sends 0, see TodoForm. If the
    // row changed server-side since this read, the stale number is rejected
    // with a 404 and only the catch below runs; reload() is reached solely on
    // success, so the list never shows a toggle the server refused.
    await postJSON(`/todos/${todo.public_id}/toggle`, {
      expected_row_version: todo.row_version,
    })
    await reload()
  } catch (e) {
    showErrorToast(e, "Could not toggle todo")
  } finally {
    toggling.value = null
  }
}
</script>

<template>
    <div class="ours-todos-page">
      <h1>Todos</h1>
      <TodoForm @created="onCreated" />
      <ul class="ours-todos-list">
        <li
          v-for="todo in todos"
          :key="todo.public_id"
          class="ours-todo-item"
          :class="{ 'ours-todo-completed': todo.completed }"
        >
          <span>{{ todo.text }}</span>
          <button
            class="btn btn-sm btn-outline-secondary"
            type="button"
            aria-label="Toggle complete"
            :disabled="toggling === todo.public_id"
            @click="toggle(todo)"
          >
            {{ todo.completed ? "Undo" : "Done" }}
          </button>
        </li>
      </ul>
      <p v-if="todos.length === 0" class="text-muted">Nothing to do yet.</p>
    </div>
</template>
