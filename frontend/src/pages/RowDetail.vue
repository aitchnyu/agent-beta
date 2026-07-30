<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import BackToTopLink from "../components/BackToTopLink.vue"
import Layout from "../components/Layout.vue"
import RowCell from "../components/RowCell.vue"
import { RowDetailPropsSchema, type RowListColumnDef } from "../schemas"
import { formatDateTime } from "../utils/time"
import { rowListUrl } from "../utils/urls"

const props = defineProps<{ props: object }>()

const p = RowDetailPropsSchema.parse(props.props)

const createdByCol: RowListColumnDef = {
  name: "created_by",
  type: "user",
  has_choices: false,
}

const listHref = rowListUrl(p.model_name)
</script>

<template>
  <Layout>
    <div class="container manage-rowdetail-page">
      <h1>{{ p.model_name }} / {{ p.public_id }}</h1>
      <p class="text-muted">
        <Link :href="listHref">Back to {{ p.model_name }} list</Link>
      </p>

      <table class="table table-sm align-middle manage-rowdetail-table">
        <tbody>
          <tr v-for="col in p.columns" :key="col.name">
            <th scope="row">{{ col.name }}</th>
            <td>
              <RowCell :col="col" :value="p.values[col.name]" />
            </td>
          </tr>
          <tr>
            <th scope="row">Created by</th>
            <td>
              <RowCell :col="createdByCol" :value="p.created_by" />
            </td>
          </tr>
          <tr>
            <th scope="row">Created at</th>
            <td>{{ formatDateTime(p.created_at) }}</td>
          </tr>
          <tr>
            <th scope="row">Edited at</th>
            <td>{{ formatDateTime(p.edited_at) }}</td>
          </tr>
        </tbody>
      </table>

      <BackToTopLink :href="listHref">Back to {{ p.model_name }}</BackToTopLink>
    </div>
  </Layout>
</template>
