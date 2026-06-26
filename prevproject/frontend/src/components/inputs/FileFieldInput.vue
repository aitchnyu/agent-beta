<script setup lang="ts">
import type {
  FileFieldInput as FileFieldInputType,
  FieldValue,
  FileFieldValue,
} from "../../schemas"
import FileUploadWidget from "../FileUploadWidget.vue"

type Value = FieldValue

interface Props {
  field: FileFieldInputType
  modelValue: Value
  viewname: string
  error?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  "update:modelValue": [value: Value]
}>()
</script>

<template>
  <div :class="['mb-3', 'column-input-' + field.name]">
    <FileUploadWidget
      :field="field"
      :model-value="props.modelValue as FileFieldValue"
      @update:model-value="emit('update:modelValue', $event)"
      :viewname="viewname"
      :error="error"
    />
  </div>
</template>
