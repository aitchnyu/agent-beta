import pluginVue from "eslint-plugin-vue"

// Templates only: <template> correctness rules (duplicate attrs,
// v-if+v-for, missing v-for key…). Script blocks are vue-tsgo's job,
// formatting is prettier's — no TS parser, no prettier plugin here,
// which keeps this at three dev-deps instead of the old twelve.
export default [
  {
    ignores: ["dist/**", "node_modules/**", "**/*.gen.ts"],
  },
  ...pluginVue.configs["flat/essential"],
  {
    files: ["src/**/*.vue"],
    languageOptions: {
      parserOptions: {
        // false = skip <script> blocks (vue-tsgo's job); template
        // structural rules still run — that's this config's whole point.
        parser: false,
        sourceType: "module",
      },
    },
    rules: {
      // Template expressions are TypeScript (`$event.target as …`) and
      // scripts are lang="ts" — both skipped here (vue-tsgo owns them),
      // so vue/no-parsing-error only reports false positives on TS casts.
      "vue/no-parsing-error": "off",
      "vue/multi-word-component-names": "off",
      "vue/no-deprecated-filter": "off",
    },
  },
]
