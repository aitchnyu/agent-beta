<script setup lang="ts">
import { computed } from "vue"
import type {
  TextFieldInput as TextFieldInputType,
  FieldValue,
} from "../../schemas"
import RichTextEditor from "../RichTextEditor.vue"

type Value = FieldValue

interface Props {
  field: TextFieldInputType
  modelValue: Value
  error?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  "update:modelValue": [value: Value]
}>()

const formValue = computed({
  get: () => (props.modelValue as string) ?? "",
  set: (value) => emit("update:modelValue", value),
})
</script>

<template>
  <div :class="['mb-2', 'column-input-' + field.name]">
    <label :for="field.name" class="form-label">{{ field.name }}</label>
    <RichTextEditor :id="field.name" v-model="formValue" />
    <div v-if="error" class="invalid-feedback">
      {{ error }}
    </div>
  </div>
</template>
