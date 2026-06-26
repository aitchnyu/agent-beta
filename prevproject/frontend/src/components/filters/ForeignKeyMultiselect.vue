<script setup lang="ts">
import axios from "axios"
import { ref, watch } from "vue"
import Multiselect from "vue-multiselect"
import { SearchRowsResponseSchema } from "../../schemas"
import type { FieldValue } from "../../schemas"
import { showErrorToast } from "../../utils/sweetalert"

interface Option {
  id: string
  text: string
}

function isOption(val: FieldValue): val is Option {
  return val !== null && typeof val === "object" && "id" in val && "text" in val
}

interface Props {
  modelValue: FieldValue
  fieldName: string
  viewName: string
  error: string | undefined
  disabled?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  "update:modelValue": [value: FieldValue]
}>()

const options = ref<Option[]>([])
const isLoading = ref(false)

const value = ref<Option | null>(null)

watch(
  () => props.modelValue,
  (newVal: FieldValue) => {
    if (newVal && isOption(newVal)) {
      value.value = newVal
    } else {
      value.value = null
    }
  },
  { immediate: true },
)

watch(value, (newVal: Option | null) => {
  emit("update:modelValue", newVal)
})

const search = async (query: string) => {
  if (!query) {
    options.value = []
    return
  }
  isLoading.value = true
  try {
    const response = await axios.get(
      `/tables/api/${props.viewName}/search-rows/${props.fieldName}`,
      {
        params: { query },
      },
    )
    const data = SearchRowsResponseSchema.parse(response.data)
    options.value = data.rows.map((row) => ({
      id: row.id,
      text: row.title,
    }))
  } catch (e: unknown) {
    showErrorToast(e, "Search failed")
    options.value = []
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <Multiselect
    v-model="value"
    :options="options"
    :multiple="false"
    :taggable="false"
    :close-on-select="true"
    :clear-on-select="false"
    :preserve-search="false"
    :internal-search="false"
    :hide-selected="true"
    :allow-empty="true"
    :placeholder="`Search for ${fieldName}...`"
    :loading="isLoading"
    :searchable="true"
    :track-by="'id'"
    :label="'text'"
    :custom-label="(option) => option.text"
    :disabled="disabled"
    @search-change="search"
  />
  <div v-if="error" class="invalid-feedback d-block">
    {{ error }}
  </div>
</template>
