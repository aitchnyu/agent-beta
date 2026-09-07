# Dedupe fixture

Duplicate heading texts, a literal "Section 1", and a symbol-only heading —
pins assignHeadingIds' taken-id dedupe and the section-N fallback ordering.
The invalid mermaid fence below pins the render-error fallback.

## Foo

First foo.

## Foo 2

Slugs to foo-2 — a per-base counter would later re-emit it.

## Foo

Second foo must become foo-3.

## Section 1

Occupies section-1 before the anonymous fallback wants it.

## ✨✨✨

Symbol-only → empty slug → section-N fallback.

```mermaid
this is not valid mermaid
```
