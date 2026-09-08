// Folder-tree construction for the git viewer pages: flat {status, path}
// entries → nested folders, so deep paths read as structure instead of long
// strings. Pure presentation — the backend keeps sending flat lists (the
// props/schemas/view tests stay untouched). Folders sort first (alphabetical),
// files after; each folder counts its total leaves.

export interface FileTreeEntry {
  status: string
  path: string // full repo-relative path (links + keys); display name = last segment
}

export interface FileTreeFolder {
  name: string // this folder's segment ("" at the root)
  /** Full dir path from the repo root ("" at the root) — unique within a
   *  worktree section, so it keys the data-tree-folder/-toggle attributes
   *  tests select by (no positional nth() chains). */
  path: string
  count: number // total file entries beneath (filled by finalize)
  folders: FileTreeFolder[]
  files: FileTreeEntry[]
}

/** Builds the href for a changed file's diff/file link from its path. (The
 *  bare `_` param name satisfies no-unused-vars' argsIgnorePattern: ^_$.) */
export type PathLinkBuilder = (_: string) => string

/** Build the nested tree; the returned root's name is "" and its own files
 *  are the changed paths sitting at the repo root. */
export function buildFileTree(entries: FileTreeEntry[]): FileTreeFolder {
  const root: FileTreeFolder = {
    name: "",
    path: "",
    count: 0,
    folders: [],
    files: [],
  }
  const folders = new Map<string, FileTreeFolder>([["", root]])
  // Get-or-create the folder node for a dir path, creating parents first so
  // every node lands under its real parent (paths arrive in any order).
  const folderFor = (dir: string): FileTreeFolder => {
    const existing = folders.get(dir)
    if (existing) return existing
    const parentDir = dir.includes("/")
      ? dir.slice(0, dir.lastIndexOf("/"))
      : ""
    const node: FileTreeFolder = {
      name: dir.slice(dir.lastIndexOf("/") + 1),
      path: dir,
      count: 0,
      folders: [],
      files: [],
    }
    folderFor(parentDir).folders.push(node)
    folders.set(dir, node)
    return node
  }
  for (const entry of entries) {
    const dir = entry.path.includes("/")
      ? entry.path.slice(0, entry.path.lastIndexOf("/"))
      : ""
    folderFor(dir).files.push(entry)
  }
  const finalize = (node: FileTreeFolder): number => {
    node.folders.sort((a, b) => a.name.localeCompare(b.name))
    node.files.sort((a, b) => a.path.localeCompare(b.path))
    node.count =
      node.files.length +
      node.folders.reduce((sum, folder) => sum + finalize(folder), 0)
    return node.count
  }
  finalize(root)
  return root
}
