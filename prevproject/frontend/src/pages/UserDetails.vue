<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import Layout from "../components/Layout.vue"
import RenderRawHtml from "../components/RenderRawHtml.vue"
import { UserDetailsPropsSchema } from "../schemas.ts"

const props = defineProps<{
  props: object
}>()

const p = UserDetailsPropsSchema.parse(props.props)
</script>

<template>
  <Layout :user="p.user">
    <div class="container user-details-page">
      <Link
        v-if="p.viewer_is_superuser"
        href="/users/list"
        class="small text-muted text-decoration-none"
      >
        &larr; Back to Users
      </Link>
      <h1 :class="{ 'user-inactive': p.viewer_is_superuser && !p.is_active }">
        {{ p.first_name }} {{ p.last_name }}
        <span
          v-if="p.viewer_is_superuser && !p.is_active"
          class="badge bg-secondary ms-2"
          >Inactive</span
        >
      </h1>
      <div v-if="p.username" class="text-muted mb-3">{{ p.username }}</div>
      <span v-if="p.is_owner" class="badge bg-primary mb-3">This is you</span>
      <div v-if="p.viewer_is_superuser" class="mb-3 d-flex gap-2">
        <Link
          :href="`/users/edit/${p.public_id}`"
          class="btn btn-outline-secondary btn-sm"
          >Edit</Link
        >
        <Link
          :href="`/users/history/${p.public_id}`"
          class="small text-muted text-decoration-none align-self-center"
          >History ({{ p.history_count }})</Link
        >
      </div>

      <table
        v-if="p.viewer_is_superuser"
        class="table table-sm user-details-attrs mb-4"
      >
        <tbody>
          <tr>
            <th scope="row">Email</th>
            <td>{{ p.email }}</td>
          </tr>
          <tr>
            <th scope="row">Public profile</th>
            <td>
              <span v-if="p.has_public_profile" class="user-yes">Yes</span>
              <span v-else class="user-no">No</span>
            </td>
          </tr>
          <tr>
            <th scope="row">Active</th>
            <td>
              <span v-if="p.is_active" class="user-yes">Yes</span>
              <span v-else class="user-no">No</span>
            </td>
          </tr>
          <tr>
            <th scope="row">Staff</th>
            <td>
              <span v-if="p.is_staff" class="user-yes">Yes</span>
              <span v-else class="user-no">No</span>
            </td>
          </tr>
          <tr>
            <th scope="row">Superuser</th>
            <td>
              <span v-if="p.is_superuser" class="user-yes">Yes</span>
              <span v-else class="user-no">No</span>
            </td>
          </tr>
        </tbody>
      </table>

      <RenderRawHtml
        v-if="p.description"
        :html="p.description"
        className="rich-text-display user-details-content"
      />
      <p v-else class="text-muted">This profile has no public description.</p>
    </div>
  </Layout>
</template>
