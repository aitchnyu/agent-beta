<script setup lang="ts">
import axios from "axios"
import { computed } from "vue"
import { Link, router } from "@inertiajs/vue3"
import { showErrorToast, showToast, showConfirm } from "../utils/sweetalert"
import { pushStartEdit } from "../utils/startEdit"
import Layout from "./Layout.vue"
import RowUpdateList from "./RowUpdateList.vue"
import { RowDetailsProps } from "../schemas"
import { getTdComponent } from "../utils/tdComponents"

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- Inertia props are untyped
const { props: rawProps } = defineProps<{ props: Record<string, any> }>()

const p = computed(() => RowDetailsProps.parse(rawProps))

function navigateToUpdate(fieldName: string) {
  if (!p.value.can_edit) return
  pushStartEdit(fieldName)
  router.visit(`/tables/${p.value.viewname}/update-row/${p.value.id}`)
}

const deleteRow = async () => {
  const confirmed = await showConfirm({
    title: "Are you sure?",
    text: "You won't be able to revert this!",
    confirmButtonText: "Yes, delete it!",
    cancelButtonText: "cancel",
    reverseButtons: true,
  })

  if (confirmed) {
    try {
      const response = await axios.post(
        `/tables/api/${p.value.viewname}/delete-row/${p.value.id}`,
      )
      showToast("success", response.data.message)
      router.visit(p.value.view_url)
    } catch (e: unknown) {
      showErrorToast(e, "There was an error deleting the row.")
    }
  }
}
</script>

<template>
  <Layout :user="p.user">
    <div class="container">
      <h2 class="details-breadcrumb">
        <Link :href="p.view_url">{{ p.viewname }}</Link>
        <span class="breadcrumb-sep"> &gt; </span>
        {{ p.title }}
      </h2>
      <div class="row">
        <div class="col-md-8">
          <div v-if="$slots['before-row']" class="slot-before-row">
            <slot name="before-row"></slot>
          </div>

          <div>
            <div
              v-for="field in p.fields"
              :key="field.name"
              class="mb-3 border-bottom pb-2 field-display-row"
              :class="'field-display-row-' + field.name"
              @dblclick="navigateToUpdate(field.name)"
            >
              <label class="form-label text-muted small">{{
                field.name
              }}</label>
              <div class="field-display-value">
                <component
                  :is="getTdComponent(p.cell_values[field.name]!)"
                  :content="p.cell_values[field.name]!"
                />
              </div>
            </div>
            <div class="d-flex gap-2 mt-3">
              <button
                v-if="p.can_edit"
                class="btn btn-outline-primary"
                @click="navigateToUpdate(p.column_names[0]!)"
              >
                Edit
              </button>
              <button
                v-if="p.can_delete"
                class="btn btn-outline-danger"
                @click="deleteRow"
              >
                Delete
              </button>
            </div>
          </div>

          <div v-if="$slots['after-row']" class="slot-after-row">
            <slot name="after-row"></slot>
          </div>

          <RowUpdateList
            :viewname="p.viewname"
            :rowId="p.id"
            :currentUsername="p.user?.title || null"
          />
        </div>
      </div>
    </div>
  </Layout>
</template>
