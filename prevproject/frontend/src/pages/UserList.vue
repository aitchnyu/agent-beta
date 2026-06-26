<script setup lang="ts">
import { Link, router } from "@inertiajs/vue3"
import axios from "axios"
import { computed, onMounted, ref } from "vue"
import Multiselect from "vue-multiselect"
import Layout from "../components/Layout.vue"
import { showErrorToast } from "../utils/sweetalert"
import {
  UserListPropsSchema,
  UserSearchResponseSchema,
  type UserSearchItem,
} from "../schemas.ts"

const props = defineProps<{
  props: object
}>()

const p = UserListPropsSchema.parse(props.props)
const pathPrefix = p.path_prefix

// Jump-to-profile search (single-select that navigates on pick).
const selectedUser = ref<UserSearchItem | null>(null)
const userOptions = ref<UserSearchItem[]>([])

async function searchUsers(query: string) {
  try {
    const response = await axios.get(`${pathPrefix}/api/search`, {
      params: { q: query },
    })
    userOptions.value = UserSearchResponseSchema.parse(response.data).users
  } catch (e: unknown) {
    showErrorToast(e, "Failed to load users")
  }
}

function goToProfile(value: UserSearchItem | null) {
  if (!value) return
  router.visit(`${pathPrefix}/id/${value.public_id}`)
}

// Paginated browse table below.
const currentPage = ref(p.pagination.page)
const allPages = computed(() =>
  Array.from({ length: p.pagination.total_pages }, (_, i) => i + 1),
)

function buildUrl(page?: number) {
  const params = new URLSearchParams()
  if (page && page > 1) params.set("page", String(page))
  const qs = params.toString()
  return `${pathPrefix}/list${qs ? `?${qs}` : ""}`
}

function navigateToPage(page: number) {
  router.visit(buildUrl(page))
}

function fullName(user: (typeof p.users)[number]): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username
}

onMounted(() => {
  searchUsers("")
})
</script>

<template>
  <Layout :user="p.user">
    <div class="container users-page">
      <h1>Users</h1>

      <div class="users-search mb-4">
        <Multiselect
          v-model="selectedUser"
          :options="userOptions"
          :multiple="false"
          :close-on-select="true"
          :preserve-search="true"
          :internal-search="false"
          :allow-empty="true"
          placeholder="Search by username..."
          track-by="public_id"
          label="username"
          class="users-search-multiselect"
          @search-change="searchUsers"
          @update:model-value="goToProfile"
        >
          <template #option="{ option }">
            <span class="users-search-option-username">{{
              option.username
            }}</span>
            <span class="users-search-option-title">{{ option.title }}</span>
          </template>
          <template #singleLabel="{ value }">
            <span>{{ value.username }}</span>
          </template>
          <template #noResult>
            <span>No users found.</span>
          </template>
        </Multiselect>
      </div>

      <table class="table table-sm align-middle users-table">
        <thead>
          <tr>
            <th scope="col">Full name</th>
            <th scope="col">Username</th>
            <th scope="col">Email</th>
            <th scope="col" class="text-center">Public</th>
            <th scope="col" class="text-center">Staff</th>
            <th scope="col" class="text-center">Superuser</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="user in p.users"
            :key="user.public_id"
            :class="{ 'user-inactive': !user.is_active }"
          >
            <td>
              <Link
                :href="`${pathPrefix}/id/${user.public_id}`"
                class="user-table-name"
                >{{ fullName(user) }}</Link
              >
            </td>
            <td class="text-muted">{{ user.username }}</td>
            <td class="text-muted">{{ user.email }}</td>
            <td class="text-center">
              <span v-if="user.has_public_profile" class="user-yes">Yes</span>
              <span v-else class="user-no">&mdash;</span>
            </td>
            <td class="text-center">
              <span v-if="user.is_staff" class="user-yes">Yes</span>
              <span v-else class="user-no">&mdash;</span>
            </td>
            <td class="text-center">
              <span v-if="user.is_superuser" class="user-yes">Yes</span>
              <span v-else class="user-no">&mdash;</span>
            </td>
          </tr>
          <tr v-if="p.users.length === 0">
            <td colspan="6" class="text-center text-muted py-4">
              No users found.
            </td>
          </tr>
        </tbody>
      </table>

      <div
        v-if="p.pagination.total_pages > 1"
        class="d-flex align-items-center users-pagination mt-3"
      >
        <div class="me-2">
          Page
          <select
            :value="currentPage"
            class="form-select d-inline-block w-auto mx-1"
            @change="
              navigateToPage(Number(($event.target as HTMLSelectElement).value))
            "
          >
            <option v-for="pg in allPages" :key="pg" :value="pg">
              {{ pg }}
            </option>
          </select>
          of {{ p.pagination.total_pages }}
        </div>
        <Link :href="buildUrl(1)" class="btn btn-outline-primary btn-sm me-2">
          First
        </Link>
        <Link
          v-if="currentPage > 1"
          :href="buildUrl(currentPage - 1)"
          class="btn btn-secondary btn-sm me-2"
        >
          Prev
        </Link>
        <Link
          v-if="currentPage < p.pagination.total_pages"
          :href="buildUrl(currentPage + 1)"
          class="btn btn-secondary btn-sm"
        >
          Next
        </Link>
        <span class="text-muted ms-2"
          >{{ p.pagination.total_count }} users total</span
        >
      </div>
    </div>
  </Layout>
</template>
