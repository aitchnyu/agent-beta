<script setup lang="ts">
import { ref } from "vue"
import type { z } from "zod"
import FieldError from "../../system/components/FieldError.vue"
import { NinjaError } from "../../system/utils/pydanticErrors"
import { TodoOutSchema, post_create_todo } from "../schemas/todos_sdk"

type TodoOut = z.infer<typeof TodoOutSchema>

// Create mode (no `todo` prop): the generated sdk call, then emit "created"
// with the todo the endpoint returns.
const props = defineProps<{ todo?: TodoOut }>()
const emit = defineEmits<{ created: [todo: TodoOut] }>()

const text = ref(props.todo?.text ?? "")
// Server validation errors, scoped to the payload. Cleared on edit.
const errors = ref<NinjaError | null>(null)
// Guards the POST so a double-click can't fire two creates.
const submitting = ref(false)

async function submit() {
  if (submitting.value) return
  errors.value = null
  submitting.value = true
  try {
    // expected_row_version: 0 — the required value for a create (no prior state to echo).
    const result = await post_create_todo({
      text: text.value,
      expected_row_version: 0,
    })
    text.value = ""
    emit("created", result)
  } catch (e) {
    // Not validation (network/server): rethrow — main.ts' global
    // handlers toast it. Validation scopes inline, under the field.
    if (!(e instanceof NinjaError)) throw e
    errors.value = e.childForPath(["body", "payload"])
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form class="ours-todo-form mb-4" @submit.prevent="submit">
    <input
      v-model="text"
      class="form-control mb-2"
      :class="{ 'is-invalid': !!errors?.errorAtPath(['text']) }"
      :aria-invalid="!!errors?.errorAtPath(['text'])"
      placeholder="What needs doing?"
      aria-label="New todo"
      @input="errors = null"
      required
    />
    <FieldError :error="errors?.errorAtPath(['text'])" />
    <button class="btn btn-primary btn-sm" type="submit" :disabled="submitting">
      Add todo
    </button>
  </form>
</template>
