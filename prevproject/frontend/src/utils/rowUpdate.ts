import type { z } from "zod"
import { RowColumnValueSchema } from "../schemas"

type ColumnValue = z.infer<typeof RowColumnValueSchema>

export const formatDateTime = (dateStr: string): string => {
  return new Date(dateStr).toLocaleString()
}

export const getActionLabel = (action: string): string => {
  switch (action) {
    case "created_row":
      return "Created"
    case "updated_row":
      return "Updated"
    case "commented":
      return "Commented"
    default:
      return action
  }
}

export const formatValue = (cv: ColumnValue, isOld: boolean): string => {
  const value = isOld ? cv.old_value : cv.new_value
  if (value === null || value === undefined) {
    return ""
  }
  switch (cv.d) {
    case "text":
      return typeof value === "string" ? value : ""
    case "char":
      return String(value)
    case "char_choice": {
      if (typeof value === "object" && value !== null) {
        const v = value as { value: string | null; value_title?: string | null }
        return v.value_title ?? String(v.value ?? "")
      }
      return String(value)
    }
    case "integer":
      return String(value)
    case "integer-choice": {
      if (typeof value === "object" && value !== null) {
        const v = value as { value: number | null; value_title?: string | null }
        return v.value_title ?? String(v.value ?? "")
      }
      return String(value)
    }
    case "boolean":
      return value ? "Yes" : "No"
    case "decimal":
      return String(value)
    case "datetime":
      return value ? new Date(value as string).toLocaleString() : ""
    case "foreign_key": {
      if (typeof value === "object" && value !== null) {
        const v = value as { id: number | null; title?: string | null }
        return v.title ?? String(v.id ?? "")
      }
      return String(value)
    }
    case "file":
      return String(value)
    default:
      return String(value)
  }
}

export const isTextField = (cv: ColumnValue): boolean => {
  return cv.d === "text"
}

export const isForeignKey = (cv: ColumnValue): boolean => {
  return cv.d === "foreign_key"
}

interface FkData {
  id: string | null
  title: string | null
  url: string | null
}

export const getFkData = (cv: ColumnValue, isOld: boolean): FkData | null => {
  if (cv.d !== "foreign_key") {
    return null
  }
  const value = isOld ? cv.old_value : cv.new_value
  if (value === null || value === undefined || typeof value !== "object") {
    return null
  }
  return value as unknown as FkData
}

export const getTextValue = (cv: ColumnValue, isOld: boolean): string => {
  if (cv.d !== "text") {
    return ""
  }
  const value = isOld ? cv.old_value : cv.new_value
  return typeof value === "string" ? value : ""
}
