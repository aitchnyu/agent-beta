<script setup lang="ts">
import { computed } from "vue"
import type {
  DecimalFieldInput as DecimalFieldInputType,
  FieldValue,
} from "../../schemas"

type Value = FieldValue

interface Props {
  field: DecimalFieldInputType
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
  <div :class="['mb-3', 'column-input-' + field.name]">
    <label :for="field.name" class="form-label">{{ field.name }}</label>
    <input
      :id="field.name"
      v-model="formValue"
      type="number"
      :required="field.required"
      :step="`0.${'0'.repeat(field.decimal_places - 1)}1`"
      :class="['form-control', { 'is-invalid': error }]"
    />
    <div v-if="error" class="invalid-feedback">
      {{ error }}
    </div>
  </div>
</template>
