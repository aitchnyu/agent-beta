<script setup lang="ts">
// Permanent demo of the mockup convention (agentconfig/steer.md § Mockups
// and diagrams): a stage-1 mockup — hardcoded markup only, no props, no
// v-if/v-for, no client state — with the root div.mockup crosshatch layer.
// Unlike a feature mockup it never graduates; /mockup-todos IS the example.
// The markup + styles mirror the reference app's todos page
// (docs/reference/frontend/src/ours/pages/TodosPage.vue) so the demo shows
// a real feature page as it looks under the overlay. The demo also doubles
// as the mockup↔final contrast for the README: ?final=1 drops the crosshatch
// wrapper so the same markup shows its "graduated" look.
import PageTitle from "../../components/PageTitle.vue"
// Side-effect import: the .mockup crosshatch + the mirrored todos styles
// live in ours/style.scss.
import "../style.scss"

const isFinal = new URLSearchParams(window.location.search).has("final")
</script>

<template>
  <PageTitle value="Todos (mockup)" />
  <div class="ours-todos-page ours-mockup-todos" :class="{ mockup: !isFinal }">
    <h1>Todos</h1>

    <form class="ours-todo-form mb-4">
      <input
        type="text"
        class="form-control mb-2"
        placeholder="What needs doing?"
        aria-label="New todo"
      />
      <button class="btn btn-primary btn-sm" type="submit">Add todo</button>
    </form>

    <ul class="ours-todos-list">
      <li class="ours-todo-item">
        <span>Book flights for the March trip</span>
        <button class="btn btn-sm btn-outline-secondary" type="button">
          Done
        </button>
      </li>
      <li class="ours-todo-item">
        <span>Renew the passport</span>
        <button class="btn btn-sm btn-outline-secondary" type="button">
          Done
        </button>
      </li>
      <li class="ours-todo-item ours-todo-completed">
        <span>Pay the electricity bill</span>
        <button class="btn btn-sm btn-outline-secondary" type="button">
          Undo
        </button>
      </li>
      <li class="ours-todo-item">
        <span>Water the plants</span>
        <button class="btn btn-sm btn-outline-secondary" type="button">
          Done
        </button>
      </li>
      <li class="ours-todo-item ours-todo-completed">
        <span>Order grandma's birthday cake</span>
        <button class="btn btn-sm btn-outline-secondary" type="button">
          Undo
        </button>
      </li>
      <li class="ours-todo-item">
        <span>Return the library books</span>
        <button class="btn btn-sm btn-outline-secondary" type="button">
          Done
        </button>
      </li>
    </ul>
  </div>
</template>
