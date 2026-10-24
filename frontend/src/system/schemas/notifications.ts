import { z } from "zod"

// Notifications feature's zod schemas: the page's props + the API responses
// the page and utils/push.ts parse.

export const NotificationItemSchema = z.object({
  public_id: z.string(),
  kind: z.string(),
  body: z.string(),
  url: z.string(),
  read: z.boolean(),
  created_at: z.number(), // epoch ms — rendered via HumanizedTime
})

export type NotificationItem = z.infer<typeof NotificationItemSchema>

export const NotificationsPagePropsSchema = z.object({
  notifications: z.array(NotificationItemSchema),
  unread_count: z.number(),
  vapid_public_key: z.string(),
  // The active ?kind= filter, echoed for the page's filter chip ("" = all).
  kind: z.string(),
  // Whether older rows exist beyond this page (drives "Load more").
  has_more: z.boolean(),
})

export const NotificationPageResponseSchema = z.object({
  notifications: z.array(NotificationItemSchema),
  has_more: z.boolean(),
})

// POST reply of mark-read / mark-unread: the row's public id.
export const MessageResponseSchema = z.object({ id: z.string() })

export const CountResponseSchema = z.object({ count: z.number() })

// The checkbox selection's bulk-action body: the checked rows' public ids
// (bounded to match the server's SelectedIdsSchema).
export const SelectedIdsSchema = z.object({
  public_ids: z.string().min(1).array().min(1).max(500),
})

// POST /notifications/api/subscriptions reply (utils/push.ts).
export const SubscribeResponseSchema = z.object({
  subscribed: z.boolean(),
})
