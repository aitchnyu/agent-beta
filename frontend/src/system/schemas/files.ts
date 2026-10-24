import { z } from "zod"

// File browser/viewer feature's zod schemas (system/pages/files/*). Sizes are
// bytes, mtimes epoch ms — both formatted client-side.

const FileCrumbSchema = z.object({
  label: z.string(),
  rel: z.string(),
})

export const FileBrowserPropsSchema = z.object({
  rel: z.string(),
  breadcrumb: z.array(FileCrumbSchema),
  parent: z.string().nullable(),
  entries: z.array(
    z.object({
      name: z.string(),
      is_dir: z.boolean(),
      is_image: z.boolean(),
      size: z.number(), // bytes — formatted client-side (humanized)
      // epoch ms — formatted client-side in the local timezone
      mtime: z.number(),
    }),
  ),
  contains_hidden_entries: z.boolean(),
})

export const FileViewerPropsSchema = z.object({
  rel: z.string(),
  breadcrumb: z.array(FileCrumbSchema),
  parent: z.string(),
  name: z.string(),
  size: z.number(),
  mtime: z.number(), // epoch ms — formatted client-side in the local timezone
  kind: z.enum(["text", "image", "binary", "markdown"]),
  text: z.string().default(""),
})
