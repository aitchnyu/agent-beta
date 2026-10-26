import { z } from "zod"

// Git viewer feature's zod schemas (system/pages/git/*): the four pages'
// props. Dates are epoch ms (rendered via HumanizedTime).

export const GitDiffPropsSchema = z.object({
  title: z.string(),
  diff: z.string(),
  // The diff path's file-view URL (/files/<worktree>/<path>) — muted
  // link; null when the path has no file to view (deleted).
  file_url: z.string().nullable(),
})

// A changed file in a commit or the working tree (status: git's letter code).
export const GitFileStatusSchema = z.object({
  path: z.string(),
  status: z.string(),
})

export const GitUncommittedPropsSchema = z.object({
  main_files: z.array(GitFileStatusSchema),
  scratch_files: z.array(GitFileStatusSchema).nullable(),
})

// List rows render subject + sha + date only
export const GitCommitListItemSchema = z.object({
  sha: z.string(),
  date: z.number(), // epoch ms — rendered via HumanizedTime
  subject: z.string(),
})

export const GitCommitListPropsSchema = z.object({
  commits: z.array(GitCommitListItemSchema),
  pagination: z.object({
    page: z.number(),
    total_pages: z.number(),
    total_count: z.number(),
  }),
})

export const GitCommitSummarySchema = z.object({
  sha: z.string(),
  author: z.string(),
  date: z.number(), // epoch ms — rendered via HumanizedTime
  subject: z.string(),
})

export const GitCommitPropsSchema = z.object({
  commit: GitCommitSummarySchema,
  files: z.array(GitFileStatusSchema),
})
