import js from "@eslint/js"
import vue from "eslint-plugin-vue"
import typescript from "@typescript-eslint/eslint-plugin"
import typescriptParser from "@typescript-eslint/parser"
import vueParser from "vue-eslint-parser"
import {
  defineConfigWithVueTs,
  vueTsConfigs,
} from "@vue/eslint-config-typescript"
import prettierConfig from "@vue/eslint-config-prettier"

export default defineConfigWithVueTs(
  js.configs.recommended,
  ...vue.configs["flat/essential"],
  vueTsConfigs.recommended,
  {
    files: ["**/*.vue", "**/*.ts"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parser: vueParser,
      parserOptions: {
        parser: typescriptParser,
      },
      globals: {
        window: "readonly",
        document: "readonly",
        console: "readonly",
      },
    },
    plugins: {
      "@typescript-eslint": typescript,
    },
    rules: {
      "no-unused-vars": ["error", { argsIgnorePattern: "^_$" }],
      "no-debugger": "off",
      "vue/multi-word-component-names": "off",
      "vue/no-deprecated-filter": "off",
    },
  },
  {
    ignores: ["dist/**", "node_modules/**"],
  },
  prettierConfig,
)
