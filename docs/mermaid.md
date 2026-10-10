# Mermaid diagrams in feature docs

The /files viewer renders ```` ```mermaid ```` fences with the mermaid
version pinned in `frontend/package.json`. **Validate before deploying**
— run `./run checkmermaid` (no args, interactive) and it parses every
fence in the default docs with that exact build; to validate ONE diagram,
pipe it on stdin. A broken diagram otherwise shows as raw source in the
browser. Full grammar per type lives at mermaid.js.org/docs; this page
carries the constructs feature docs use, with skeletons that parse (this
file is itself among checkmermaid's default targets).

## usecase-beta (12.0+)

> **This section is scaffolding.** It exists because AI models don't yet
> write usecase-beta fluently from mermaid's own docs — they drift into
> PlantUML. Once models are reliably fluent, delete this section and the
> usecase-beta entry in agentconfig/steer.md (the skeleton and the
> validation rule).

The grammar is mermaid's OWN. PlantUML habits are parse errors — no `as`
aliases, no `usecase "…" as ID` lines, no `{ … }` braces after
systemBoundary, and actors are never inferred from edges (declare every
one with `actor`).

```mermaid
usecase-beta
direction LR
actor Guest("Anonymous visitor")
actor Member("Library member")
actor Librarian("Librarian") <<Staff>>
Librarian --|> Member
systemBoundary catalog["Catalogue"]
  Search("Search the catalogue")
  Reserve("Reserve a book")
  Borrow("Borrow a book")
end
systemBoundary desk["Librarian desk"]
  Checkin("Check in a return")
  Audit("Audit overdue loans")
end
Guest --> Search
Member --> Reserve
Member --> Borrow
Librarian --> Checkin
Librarian --> Audit
Borrow ..> : include Search
Reserve ..> : extend Borrow
note for Guest "Gets a 404. The feature is hidden until you sign in."
json LoansSnapshot@{
  "overdue": 3,
  "due this week": 7
}
Audit --> LoansSnapshot
```

What the example demonstrates: `direction`; actors as roles with
generalization (`Librarian --|> Member` — the librarian can do everything
a member can); one boundary per area of the app; a `<<stereotype>>`;
include (`Borrow` always searches) and extend (`Reserve` optionally
extends `Borrow`); a note carrying the permission rule for the excluded
actor; and a `json` node showing a payload shape.

Rules that bite:

- **One statement per physical line** — no `;` separators.
- **Labels** (inside `…` or `[…]`): a literal `"` ends the label —
  rephrase, or use the `#quot;` entity code. Everything else that looks
  scary (`'`, `--`, `-->`, `:::`, `@{`, `<<`) parses fine; rephrase only
  if rendering looks off.
- **systemBoundary bodies hold declarations only** (actors, use cases,
  comments); relationships, notes, and json nodes stay at top level.
  Boundaries are one level deep.
- An edge endpoint with no declaration becomes an ellipse use case; an
  **actor must be declared** with `actor` somewhere.
- UML semantics: `A ..> : include B`, `A ..> : extend B`, and
  generalization `A --|> B` (specialized → general; how superuser
  inherits user).
- Notes attach to one element: `note for Id "text"`. JSON tables are
  strict JSON objects, top level only — use them for a payload shape
  worth seeing.
- Per-diagram theme/look rides frontmatter (the viewer's global theme is
  `base`; the new usecase look is `redux-color` + `neo`):

```mermaid
---
config:
  theme: redux-color
  look: neo
---
usecase-beta
direction LR
actor Member("Library member")
systemBoundary Library
  Borrow("Borrow a book")
end
Member --> Borrow
```

## erDiagram

One field per line as `type name`; relationship lines
`PARENT ||--o{ CHILD : "verb"`; FK policies belong in the field comment
(`FK RESTRICT`) and in prose — translate them into behavior ("a book with
loans can never be deleted").

## stateDiagram-v2

For a row kind's lifecycle: `A --> B : what moves it`; start/end with
`[*]`. Keep labels in plain words — the transition phrase, not the
method name.

## Workflow

**Always run the validator** — the usecase grammar is too new for AI
training data: pipe the whole draft through
`printf '%s' "usecase-beta …" | ./run checkmermaid` (exit 0 = valid;
exit 1 = the parser's error). The viewer shows raw source on parse
failure, so a broken diagram is user-visible — never deploy one.
