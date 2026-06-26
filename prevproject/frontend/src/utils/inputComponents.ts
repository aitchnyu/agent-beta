import { type Component } from "vue"
import type { InputSchemaType } from "../schemas"

const modules = import.meta.glob<{ default: Component }>(
  ["../components/inputs/*.vue"],
  { eager: true },
)

const componentMap = new Map<string, Component>()
for (const [path, module] of Object.entries(modules)) {
  const key = path.replace(/^\.\.\//, "/").replace(/\.vue$/, "")
  componentMap.set(key, module.default)
}

export function getInputComponent(input: InputSchemaType): Component {
  const component = componentMap.get(input.component)
  if (!component) {
    throw new Error(`No input component found for "${input.component}".`)
  }
  return component
}
