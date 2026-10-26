# Golden Bootstrap theme

Applied to the app frontend: **option A** (v2 colorblind-safe ladder). Dark mode follows the OS
`prefers-color-scheme` setting (`$color-mode-type: media-query`).

A worked example for building a Bootstrap color theme: six golden primary options, each with a full
light + dark token set. Palette sheet: [`desmodium-theme.svg`](./desmodium-theme.svg).

## Wheel alignment

Each option fixes a hue `h` (its gold) and derives most of the set from `h` — the rule defines each
option's own secondary/success/info base, but the shipped palettes then converged on shared
deutan-safe status colors (see the ladder below), so not every option keeps a unique hue for
warning/danger.

| Role                                  | Rule                              | Rationale                                          |
|---------------------------------------|-----------------------------------|----------------------------------------------------|
| `$secondary`                          | complement, h+185°                | maximal wheel separation from the gold             |
| `$success`                            | h+65°                             | analogous step toward green                        |
| `$info`                               | moved onto the blue axis          | rides the blue axis deutan vision preserves        |
| `$warning`                            | toward orange, then lightened     | deutan ladder: must stay light with dark ink       |
| `$danger`                             | toward red, then darkened         | deutan ladder: must stay dark with white ink       |
| `$light`, `$dark`, tints, dark tokens | hue `h`, lightness only           | keeps the option's temperature                     |

## Options

| Opt | Name           | `$primary`     | Primary text | btn deep (white text) |
|-----|----------------|----------------|--------------|-----------------------|
| A   | Sunlit yellow  | `#e6d35a` h52  | dark ink     | `#716a14`             |
| B   | Gold leaf      | `#d2bd4b` h51  | dark ink     | `#715e14`             |
| C   | Goldenrod      | `#cc9900` h45  | dark ink     | `#8a6d00`             |
| D   | Marigold pop   | `#f5b800` h45  | dark ink     | `#8a6600`             |
| E   | Citrus flash   | `#ffe500` h54  | dark ink     | `#756800`             |
| F   | Pale gold      | `#e8c547` h47  | dark ink     | `#715b14`             |

A/B are soft, D/E full-saturation, F the palest.

## Contrast rules (WCAG AA)

As applied in the app (`frontend/src/system/styles/_bootstrap.scss`):

- Gold primaries take **dark ink**; buttons/badges use the deepened same-hue tone for white text.
- Status trio separates by **lightness, not hue** (deutan-safe): `$danger` dark red — `#861c0b`
  family (rel-lum ≈ 0.06, white text) → `$success` mid green — `#248727` (rel-lum ≈ 0.18, white
  text; soft variant `#36ba36` with dark ink) → `$warning` light salmon — `#f9ae9c` (rel-lum ≈ 0.53,
  dark ink). Pairwise ΔL: warning sits ≥ 0.35 from both; danger↔success ≈ 0.12 apart, split by the
  white/ink text swap.
- `$info` sits on the blue axis — `#3d7a72` (white text) — preserved by deutan vision; soft accent
  variant `#549c9c` takes dark ink.
- Never signal state by color alone — pair with icons/labels (WCAG 1.4.1).

## Dark mode

Hue-kept tokens per option (the dark strip in each card): body ~L8%, raised surface ~L13%,
text ~L90%, and a lit gold for primaries. Bootstrap mapping: `$body-bg-dark`, `$body-color-dark`,
`$border-color-dark` + the same `$theme-colors` map.

## Leaf icon styles

Every leaf: **short stalk** (8px round-cap petiole), **three leaflets** (center upright, two mirrored
at ±52°, scale 0.82; F fans at 0.9), same size across options — only the illustration style differs.

| Opt | Style             | Spec                                                                                                     |
|-----|-------------------|----------------------------------------------------------------------------------------------------------|
| A   | Veined falcate    | curved falcate blade, fill = primary; midrib + 2 laterals in outline olive (22–30%), joined to the midrib, tapering before the margin |
| B   | Serrated margin   | toothed (zigzag) leaflet edges, fill = primary, darker-gold outline + midrib                              |
| C   | Gradient-shaded   | smooth ovate blade, vertical light→deep gold gradient (`#e6b84d`→`#a87d0c`), thin dark outline, light midrib |
| D   | Line-art          | pale fill `#fdf3cf`, 1.4px goldenrod outline, single faint goldenrod midrib                               |
| E   | Faceted two-tone  | straight-segment polygon split along the midrib — dark half `#e0cf00`, light half `#fff763`, `#b3a600` outline |
| F   | Needle strips     | narrow crescent blades fanning wide (±48°, 0.9 scale), fill = primary, thin outline                       |

## Neutrals (shared)

Body `#ffffff`, border `#d8d2c0`, muted `#6b6656`, focus ring `#a4b83a`.

## Assets

Derived from this theme and shipped with the app:

- logo — [`desmodium-logo.svg`](./desmodium-logo.svg)
- favicon — `djangoapp/static/favicon.svg` (gold leaf on the deep-gold badge, linked from every
  shell template)
- home-button icon — `frontend/src/system/icons/leaf.svg`
