<script setup lang="ts">
import { computed } from "vue"
import type {
  IntegerFieldInput as IntegerFieldInputType,
  FieldValue,
} from "../../schemas"
import SelectFieldInput from "./SelectFieldInput.vue"

type Value = FieldValue

interface Props {
  field: IntegerFieldInputType
  modelValue: Value
  error?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  "update:modelValue": [value: Value]
}>()

const choices = props.field.choices
  ? props.field.choices.map((c) => ({ value: c.value, label: c.label }))
  : null

const formValue = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
})
</script>

<template>
  <div :class="['mb-3', 'column-input-' + field.name]">
    <label :for="field.name" class="form-label">{{ field.name }}</label>
    <SelectFieldInput
      v-if="choices"
      :choices="choices"
      :model-value="modelValue"
      :field-id="field.name"
      :field-name="field.name"
      :required="field.required"
      :error="error"
      @update:model-value="emit('update:modelValue', $event)"
    />
    <input
      v-else
      :id="field.name"
      v-model.number="formValue"
      type="number"
      :required="field.required"
      :class="['form-control', { 'is-invalid': error }]"
    />
    <div v-if="error" class="invalid-feedback">
      {{ error }}
    </div>
  </div>
</template>
