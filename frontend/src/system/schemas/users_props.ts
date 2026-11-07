// Users page props — hand-maintained (page props are never generated;
// generatesdk emits endpoint models only). Kept in lockstep with the
// page-props pydantic models in djangoapp/views/users.py.

import { z } from "zod"

export const UserListItem = z.object({
  public_id: z.string(),
  first_name: z.string(),
  last_name: z.string(),
  username: z.string(),
  email: z.string(),
  has_public_profile: z.boolean(),
  is_active: z.boolean(),
  is_staff: z.boolean(),
  is_superuser: z.boolean(),
})

export const UserListPagination = z.object({
  page: z.number().int(),
  total_pages: z.number().int(),
  total_count: z.number().int(),
})

export const UserListFilters = z.object({
  page: z.number().int().gte(1).optional(),
  q: z.string().optional(),
})

export const UserListProps = z.object({
  path_prefix: z.string(),
  users: z.array(UserListItem),
  pagination: UserListPagination,
  filters: UserListFilters,
})

export const UserDetailsProps = z.object({
  path_prefix: z.string(),
  public_id: z.string(),
  first_name: z.string(),
  last_name: z.string(),
  username: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  is_owner: z.boolean().optional(),
  email: z.string().nullable().optional(),
  has_public_profile: z.boolean().optional(),
  is_active: z.boolean().optional(),
  is_staff: z.boolean().optional(),
  is_superuser: z.boolean().optional(),
  history_count: z.number().int().optional(),
  last_login: z.string().nullable().optional(),
  session_count: z.number().int().optional(),
})

export const UserEditItem = z.object({
  public_id: z.string(),
  username: z.string(),
  first_name: z.string(),
  last_name: z.string(),
  email: z.string(),
  description: z.string(),
  has_public_profile: z.boolean(),
  is_active: z.boolean(),
  is_staff: z.boolean(),
  is_superuser: z.boolean(),
})

export const UserEditProps = z.object({
  path_prefix: z.string(),
  target: UserEditItem,
})

export const StringChange = z.object({
  old: z.string(),
  new: z.string(),
})

export const BoolChange = z.object({
  old: z.boolean(),
  new: z.boolean(),
})

export const UserHistoryContent = z.object({
  first_name: StringChange.nullable().optional(),
  last_name: StringChange.nullable().optional(),
  email: StringChange.nullable().optional(),
  description: StringChange.nullable().optional(),
  has_public_profile: BoolChange.nullable().optional(),
  is_active: BoolChange.nullable().optional(),
  is_staff: BoolChange.nullable().optional(),
  is_superuser: BoolChange.nullable().optional(),
  login_link_minutes: z.number().int().nullable().optional(),
  logout_all_sessions: z.number().int().nullable().optional(),
})

export const UserHistoryEntryItem = z.object({
  public_id: z.string(),
  action: z.enum(['created', 'edited', 'deleted', 'login', 'login_link', 'logout_all']),
  time: z.string(),
  changes: UserHistoryContent,
})

export const UserHistoryProps = z.object({
  path_prefix: z.string(),
  target_public_id: z.string(),
  target_title: z.string(),
  entries: z.array(UserHistoryEntryItem),
})
