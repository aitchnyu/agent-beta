<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from "vue"
import axios from "axios"
import { router } from "@inertiajs/vue3"
import type { InputField, FieldValue } from "../schemas"
import { RowFormResponseSchema } from "../schemas"
import { getInputComponent } from "../utils/inputComponents"
import { showErrorToast } from "../utils/sweetalert"
import { rowDetailsUrl } from "../utils/urls"

type Value = FieldValue

interface Props {
  column_names: string[]
  fields: Record<string, InputField>
  viewname: string
  mode: "create" | "update"
  row_id?: string
  focusedField?: string | null
  onCancel?: (() => void) | null
  showDelete?: boolean
  // Optional overrides for non-/tables mount schemes (e.g. Foo CRUD /allcolumns).
  submitUrl?: string | null
  detailsBaseUrl?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  focusedField: null,
  onCancel: null,
  showDelete: false,
  submitUrl: null,
  detailsBaseUrl: null,
})

const emit = defineEmits<{
  delete: []
  saved: []
}>()

const fieldValues = ref<Record<string, Value>>(
  Object.fromEntries(
    props.column_names.map((name) => [
      name,
      props.fields[name]?.default ?? null,
    ]),
  ),
)

const isDirty = ref(false)

watch(
  fieldValues,
  () => {
    isDirty.value = true
  },
  { deep: true },
)

const getField = (name: string): Value => fieldValues.value[name] ?? null
const setField = (name: string, value: Value): void => {
  fieldValues.value[name] = value
}

const errors = ref<Record<string, string>>({})
const getError = (name: string): string => errors.value[name] ?? ""
const topLevelError = ref<string>("")
const isSubmitting = ref(false)

const url = computed(
  () =>
    props.submitUrl ??
    (props.mode === "create"
      ? `/tables/api/${props.viewname}/create-row-submit`
      : `/tables/api/${props.viewname}/update-row-submit/${props.row_id}`),
)

const detailsUrl = (id: string): string =>
  props.detailsBaseUrl
    ? `${props.detailsBaseUrl}/id/${id}`
    : rowDetailsUrl(props.viewname, id)

const submitDisabled = computed(() => {
  if (isSubmitting.value) return true
  if (props.mode === "update" && !isDirty.value) return true
  return false
})

const submitForm = async () => {
  errors.value = {}
  topLevelError.value = ""
  isSubmitting.value = true

  const formData = new FormData()
  for (const name of props.column_names) {
    const field = props.fields[name]
    if (!field) continue
    const value = fieldValues.value[name]
    if (field.d === "foreignkey") {
      if (value !== null && typeof value === "object" && "id" in value) {
        formData.append(name, (value as { id: string }).id)
      }
    } else if (field.d === "file") {
      if (value instanceof File) {
        formData.append(name, value)
      } else if (value && typeof value === "object" && "filename" in value) {
        formData.append(name, value.filename)
      } else {
        formData.append(name, "")
      }
    } else if (field.d === "boolean") {
      if (value === true) {
        formData.append(name, "on")
      }
    } else {
      if (value !== null && value !== undefined) {
        formData.append(name, value.toString())
      }
    }
  }

  try {
    const response = await axios.post(url.value, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    const data = RowFormResponseSchema.parse(response.data)
    if (data.d === "success" && data.id !== null) {
      if (props.mode === "update" && props.row_id === data.id) {
        router.visit(detailsUrl(data.id), {
          preserveState: true,
          onSuccess: () => {
            emit("saved")
          },
        })
      } else {
        router.visit(detailsUrl(data.id))
      }
    } else if (data.d === "validation_error") {
      if (data.errors) {
        errors.value = data.errors as Record<string, string>
      }
      if (data.top_level_error) {
        topLevelError.value = data.top_level_error
      }
    }
  } catch (e: unknown) {
    showErrorToast(e, "An error occurred while submitting the form.")
    topLevelError.value = "An error occurred while submitting the form."
  } finally {
    isSubmitting.value = false
  }
}

onMounted(() => {
  if (props.focusedField) {
    nextTick(() => {
      const el = document.querySelector(
        `.column-input-${props.focusedField} input, .column-input-${props.focusedField} select, .column-input-${props.focusedField} textarea`,
      ) as HTMLElement | null
      el?.focus()
    })
  }
})
</script>

<template>
  <form @submit.prevent="submitForm">
    <div v-if="topLevelError" class="alert alert-danger">
      {{ topLevelError }}
    </div>
    <!-- row-id distinguishes create vs update mode and builds upload URL -->
    <component
      v-for="name in column_names"
      :key="name"
      :is="getInputComponent(fields[name]!)"
      :field="fields[name]!"
      :model-value="getField(name)"
      @update:model-value="setField(name, $event)"
      :viewname="viewname"
      :row-id="row_id"
      :error="getError(name)"
    />
    <div class="d-flex gap-2">
      <button type="submit" :disabled="submitDisabled" class="btn btn-primary">
        {{ mode === "create" ? "Create" : "Update" }}
      </button>
      <button
        v-if="showDelete"
        type="button"
        class="btn btn-danger"
        @click="emit('delete')"
      >
        Delete
      </button>
      <button
        v-if="onCancel"
        type="button"
        class="btn btn-secondary"
        @click="onCancel()"
      >
        Cancel
      </button>
    </div>
  </form>
</template>
