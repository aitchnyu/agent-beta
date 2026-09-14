// Git-commit helpers shared by the Code pages.

// Display/URL form of a sha (git's 7-char prefix; the /git/commits routes
// accept it).
export function shortSha(sha: string): string {
  return sha.slice(0, 7)
}
