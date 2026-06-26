<script setup lang="ts">
import { computed } from "vue"
import type {
  ForeignKeyFieldInput as ForeignKeyFieldInputType,
  FieldValue,
} from "../../schemas"
import ForeignKeyMultiselect from "../filters/ForeignKeyMultiselect.vue"

type Value = FieldValue

interface Props {
  field: ForeignKeyFieldInputType
  modelValue: Value
  viewname: string
  error?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  "update:modelValue": [value: Value]
}>()

const formValue = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
})
</script>

<template>
  <div :class="['mb-3', 'column-input-' + field.name]">
    <label :for="field.name" class="form-label">{{ field.name }}</label>
    <ForeignKeyMultiselect
      :id="field.name"
      v-model="formValue"
      :field-name="field.name"
      :view-name="viewname"
      :error="error"
    />
  </div>
</template>
