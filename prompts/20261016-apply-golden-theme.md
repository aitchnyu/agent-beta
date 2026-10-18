# Apply the golden theme (option A) + leaf favicon

Apply the "Sunlit yellow" palette from `docs/desmodium-theme.svg` (conclusions in
`docs/golden-theme.md`) to the app. Dark mode follows the OS setting automatically.
Do not touch `docs/` or `prompts/`.

## 1. Tokens — `frontend/src/styles/_variables.scss`

Add (keep the legacy vars for now):

```scss
// golden theme (option A)
$gold-300: #e6d35a;   // bright accent, dark-mode primary
$gold-700: #716a14;   // buttons / links (white text)
$leaf-500: #36ba36;   // success (soft)
$teal-600: #549c9c;   // info (soft)
$salmon-300: #f9ae9c; // warning
$rust-700: #861c0b;   // danger (white text)
$plum-700: #323276;   // secondary
$cream-100: #f5f4e5;  // light
$soil-900: #2b2a1d;   // dark
$ink: #2b2620;        // body text
$line: #d8d2c0;       // border
$muted: #6b6656;      // muted text
$focus-gold: #a4b83a; // focus ring
```

## 2. Bootstrap — `frontend/src/styles/_bootstrap.scss`

Before the imports:

```scss
$color-mode-type: media-query; // dark follows prefers-color-scheme
$primary: $gold-700;
$secondary: $plum-700;
$success: #248727;          // white-text-safe
$info: #3d7a72;             // white-text-safe
$warning: $salmon-300;
$warning-color: #2b2620;    // dark ink on warning
$danger: $rust-700;
$light: $cream-100;
$dark: $soil-900;
$body-bg: #ffffff;
$body-color: $ink;
$border-color: $line;
$link-color: $gold-700;
$focus-ring-color: $focus-gold;
```

Dark-mode overrides via Bootstrap's dark map: body `#1a1a0e`, secondary bg
`#282819`, text `#ececde`, border `#3a3423`, `$primary: $gold-300`.
Then wire the token aliases so the partials re-skin with zero diff:
`$blue-600: $gold-700`, `$blue-500: $gold-700`, `$green-500: $leaf-500`,
`$amber-500: $salmon-300`, `$red-500: $rust-700`, `$red-50: #f6e7e5`,
`$gray-*`: warm grays from `#d8d2c0`/`#6b6656` (keep lightness).

## 3. Leaf home button — `frontend/src/components/Layout.vue`

Add `frontend/src/icons/leaf.svg`: 24×24 single-path trifoliate silhouette
(short stalk, three leaflets), fill-rule so it works as a currentColor mask
(same contract as `house.svg`). In `Layout.vue` replace the `houseIcon`
import with `leaf.svg` — the home link becomes the golden leaf.

## 4. Favicon

Add `djangoapp/static/favicon.svg`: 32×32 badge — rounded square `#716a14`,
gold leaf glyph centered. Reference it in every shell template
(`inertia/base.html`, `simple.html`, `404.html`, allauth base):

```html
<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
```

## 5. Verify

- `./run dev` — check home, users list, a form: buttons, links, badges,
  focus ring, danger text; OS dark mode flips the palette.
- `npm run build` (or the repo build) passes.
- Note "Applied: option A" in `docs/golden-theme.md`.
