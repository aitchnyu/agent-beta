import { type Component, defineAsyncComponent } from "vue"

interface ContentLike {
  component: string
}

const eagerModules = import.meta.glob<{ default: Component }>(
  "../components/cells/*.vue",
  { eager: true },
)

const lazyModules = import.meta.glob<{ default: Component }>(
  "../components/custom/*.vue",
)

const componentMap = new Map<string, Component>()
for (const [path, module] of Object.entries(eagerModules)) {
  const key = path.replace(/^\.\.\//, "/").replace(/\.vue$/, "")
  componentMap.set(key, module.default)
}
for (const [path, loader] of Object.entries(lazyModules)) {
  const key = path.replace(/^\.\.\//, "/").replace(/\.vue$/, "")
  componentMap.set(key, defineAsyncComponent(loader))
}

/**
 * Returns a Vue component for the given Content cell.
 * Throws if the component path is not found in the whitelisted directories.
 */
export function getTdComponent(content: ContentLike): Component {
  const component = componentMap.get(content.component)
  if (!component) {
    throw new Error(`No Td component found for "${content.component}".`)
  }
  return component
}
