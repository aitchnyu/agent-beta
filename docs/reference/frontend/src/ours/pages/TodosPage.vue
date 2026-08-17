<script setup lang="ts">
import { computed, ref } from "vue"
import { router } from "@inertiajs/vue3"
import TodoForm from "../components/TodoForm.vue"
import { TodosPagePropsSchema, type TodoOut } from "../schemas"
import { postJSON } from "../../utils/http"
import { showErrorToast } from "../../utils/sweetalert"
import "../style.scss"

// Inertia wraps the page data under a `props` key (page.props.props); parse it.
const props = defineProps<{ props: object }>()
const todos = computed(() => TodosPagePropsSchema.parse(props.props).todos)
// Guard the toggle POST + reload so a double-click can't fire two toggles.
const toggling = ref<string | null>(null)

async function reload() {
  // The server is the source of truth — reload the list after any mutation.
  try {
    await router.reload()
  } catch (e) {
    showErrorToast(e, "Could not reload todos")
  }
}

function onCreated() {
  void reload()
}

async function toggle(todo: TodoOut) {
  if (toggling.value !== null) return
  toggling.value = todo.public_id
  try {
    await postJSON(`/todos/${todo.public_id}/toggle`)
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
