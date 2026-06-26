<script setup lang="ts">
import { computed } from "vue"
import type { FieldValue } from "../../schemas"

type Value = FieldValue

interface Choice {
  value: string
  label: string
}

interface Props {
  choices: Choice[]
  modelValue: Value
  fieldId: string
  fieldName: string
  required?: boolean | undefined
  error?: string | undefined
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
  <select
    :id="fieldId"
    v-model="formValue"
    :required="required"
    :class="['form-select', { 'is-invalid': error }]"
  >
    <option value="">--</option>
    <option v-for="choice in choices" :key="choice.value" :value="choice.value">
      {{ choice.label }}
    </option>
  </select>
</template>
