/** An error whose plain-language presentation is part of the error itself.
 *
 *  `message` is the technical copy (console + client-errors log);
 *  `userTitle`/`userHtml` are what the toast shows — `userHtml` is
 *  sanitized to a safe tag subset at render time (see sweetalert.ts).
 */
export class UserVisibleError extends Error {
  readonly userTitle: string
  readonly userHtml: string

  constructor(message: string, userTitle: string, userHtml: string) {
    super(message)
    this.name = "UserVisibleError"
    this.userTitle = userTitle
    this.userHtml = userHtml
  }
}
