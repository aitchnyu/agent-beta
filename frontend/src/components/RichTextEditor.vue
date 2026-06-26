<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue"
import Quill from "quill"

interface Props {
  modelValue: string
  placeholder?: string
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
})

const emit = defineEmits<{
  "update:modelValue": [value: string]
}>()

const editorRef = ref<HTMLDivElement | null>(null)
let quillInstance: Quill | null = null

// Guards against re-emit loops: setHTML() writes innerHTML programmatically,
// which fires a "text-change"; without this flag the handler would emit the
// same HTML back to the parent and re-trigger setHTML in an infinite loop.
let isInternalChange = false

const setHTML = (html: string) => {
  if (!quillInstance) return
  if (quillInstance.root.innerHTML !== html) {
    isInternalChange = true
    quillInstance.root.innerHTML = html || "<p></p>"
    isInternalChange = false
  }
}

const onTextChange = () => {
  if (!quillInstance || isInternalChange) return
  const html = quillInstance.root.innerHTML
  emit("update:modelValue", html)
}

watch(
  () => props.modelValue,
  (newValue) => {
    if (!quillInstance || isInternalChange) return
    setHTML(newValue)
  },
)

onMounted(() => {
  if (!editorRef.value) return

  const toolbarOptions = {
    toolbar: [
      [{ header: [1, 2, 3, 4, 5, 6, false] }],
      ["bold", "italic"],
      [{ list: "ordered" }, { list: "bullet" }],
      ["link"],
      ["clean"],
    ],
  }

  quillInstance = new Quill(editorRef.value, {
    theme: "snow",
    placeholder: props.disabled ? "" : props.placeholder || "Enter text...",
    modules: toolbarOptions,
    readOnly: props.disabled,
  })

  if (props.modelValue) {
    setHTML(props.modelValue)
  }

  quillInstance.on("text-change", onTextChange)
})

watch(
  () => props.disabled,
  (newVal) => {
    if (quillInstance) {
      quillInstance.enable(!newVal)
    }
  },
)

onUnmounted(() => {
  if (quillInstance) {
    quillInstance.off("text-change", onTextChange)
    quillInstance = null
  }
})
</script>

<template>
  <div class="rich-text-editor-wrapper">
    <div ref="editorRef" class="rich-text-editor quill-editor"></div>
  </div>
</template>
