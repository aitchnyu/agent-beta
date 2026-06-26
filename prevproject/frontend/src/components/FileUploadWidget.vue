<script setup lang="ts">
import { ref, watch, computed, nextTick } from "vue"
import type { Field, FileFieldValue } from "../schemas"

interface Props {
  field: Field
  modelValue: FileFieldValue
  viewname: string
  error?: string | undefined
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
})

const emit = defineEmits<{
  "update:modelValue": [value: FileFieldValue]
}>()

const fileInput = ref<HTMLInputElement | null>(null)

const handleFileChange = (event: Event) => {
  // When file input changes, emit the selected File or null
  console.log("handle file change")
  const target = event.target as HTMLInputElement
  const file = target.files?.[0] || null
  emit("update:modelValue", file)
}

const handleClear = () => {
  emit("update:modelValue", null)
}

const hasValue = computed(() => props.modelValue !== null)

// This will show the file field as having the old filename, for UX. Also we have `Your existing file is kept.`
const localFileValue = computed<File | null>(() => {
  const newVal = props.modelValue
  if (newVal instanceof File) {
    return newVal
  } else if (newVal && "filename" in newVal) {
    return new File([], newVal.filename)
  } else {
    return null
  }
})

// Sync file input with localFileValue changes
watch(
  localFileValue,
  (newVal) => {
    nextTick(() => {
      if (!fileInput.value) return
      if (newVal) {
        const dt = new DataTransfer()
        dt.items.add(newVal)
        fileInput.value.files = dt.files
      } else {
        fileInput.value.files = new DataTransfer().files
      }
    })
  },
  { immediate: true },
)
</script>

<template>
  <div class="file-upload-widget mb-3">
    <label class="form-label">{{ field.name }}</label>

    <div class="input-group">
      <input
        ref="fileInput"
        type="file"
        @change="handleFileChange"
        class="form-control"
        :class="{ 'is-invalid': error }"
        :disabled="disabled"
      />
      <button
        type="button"
        class="btn btn-outline-secondary remove-file"
        @click="handleClear"
        :disabled="!hasValue || disabled"
      >
        X
      </button>
    </div>

    <small
      v-if="
        modelValue &&
        'filename' in modelValue &&
        !('download_url' in modelValue)
      "
      class="text-muted"
    >
      Your existing file is kept.
    </small>

    <div v-if="error" class="invalid-feedback">
      {{ error }}
    </div>
  </div>
</template>
