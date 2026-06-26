<script setup lang="ts">
import { computed } from "vue"
import type {
  BooleanFieldInput as BooleanFieldInputType,
  FieldValue,
} from "../../schemas"

type Value = FieldValue

interface Props {
  field: BooleanFieldInputType
  modelValue: Value
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
  <div :class="['form-check mb-3', 'column-input-' + field.name]">
    <input
      :id="field.name"
      v-model="formValue"
      type="checkbox"
      :class="['form-check-input', { 'is-invalid': error }]"
    />
    <label class="form-check-label" :for="field.name">{{ field.name }}</label>
    <div v-if="error" class="invalid-feedback">
      {{ error }}
    </div>
  </div>
</template>
