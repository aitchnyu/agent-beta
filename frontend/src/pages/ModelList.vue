<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import Layout from "../components/Layout.vue"
import PageTitle from "../components/PageTitle.vue"
import { ModelListPropsSchema } from "../schemas"
import { rowListUrl } from "../utils/urls"

const props = defineProps<{ props: object }>()

const p = ModelListPropsSchema.parse(props.props)
</script>

<template>
  <Layout>
    <PageTitle value="Models" />
    <div class="container manage-modellist-page">
      <h1>Models</h1>
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th scope="col">Model</th>
            <th scope="col">Description</th>
            <th scope="col" class="text-end">Rows</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="model in p.models" :key="model.name">
            <td>
              <Link class="manage-model-link" :href="rowListUrl(model.name)">{{
                model.name
              }}</Link>
            </td>
            <td class="manage-model-docstring text-muted">
              {{ model.docstring }}
            </td>
            <td class="text-end">{{ model.row_count }}</td>
          </tr>
          <tr v-if="p.models.length === 0">
            <td colspan="3" class="text-center text-muted py-4">
              No models. Define a concrete model subclassing
              <code>BaseModel</code> in <code>ourapp/models/</code>.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </Layout>
</template>
