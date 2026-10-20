<script setup lang="ts">
import { computed, ref } from "vue"

import LucideIcon from "./LucideIcon.vue"
import calendarIcon from "../icons/calendar.svg"

const props = defineProps<{ ms: number; absolute?: boolean }>()
// Click toggles between humanized (relative) and absolute.
// `absolute` sets the starting side — file listings use it.
const showAbsolute = ref(props.absolute ?? false)

// Relative ("5m ago") for the last week, else a local date — friendly + local TZ.
function relativeTime(ms: number): string {
  const diffSec = (Date.now() - ms) / 1000
  if (diffSec < 60) return "just now"
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`
  return new Date(ms).toLocaleDateString(undefined, { dateStyle: "medium" })
}

// In the absolute view the date leads and the time + tz are deemphasized, so
// the day is the prominent signal and the clock/tz read as secondary detail.
const datePart = computed(() =>
  new Date(props.ms).toLocaleDateString(undefined, { dateStyle: "medium" }),
)
const timePart = computed(() =>
  new Date(props.ms).toLocaleTimeString(undefined, { timeStyle: "short" }),
)
// Deemphasized tz abbreviation (e.g. "IST", "GMT+5:30"); "" if it can't resolve.
const tzName = computed(() => {
  try {
    return (
      new Intl.DateTimeFormat(undefined, { timeZoneName: "short" })
        .formatToParts(new Date(props.ms))
        .find((p) => p.type === "timeZoneName")?.value ?? ""
    )
  } catch {
    return ""
  }
})
</script>

<template>
  <button
    type="button"
    class="humanized-time"
    :aria-pressed="showAbsolute"
    :title="`${datePart} ${timePart}`"
    @click="showAbsolute = !showAbsolute"
  >
    <span
      class="humanized-time-value"
      :class="{ 'humanized-time-absolute': showAbsolute }"
    >
      <template v-if="showAbsolute">
        {{ datePart }}<small class="humanized-time-time">{{ timePart }}</small
        ><small v-if="tzName" class="humanized-time-timezone">{{
          tzName
        }}</small>
      </template>
      <template v-else>
        <!-- The calendar hints at the absolute date one click away; it leaves
             once the date itself shows. -->
        <LucideIcon class="humanized-time-icon" :src="calendarIcon" />
        {{ relativeTime(ms) }}
      </template>
    </span>
  </button>
</template>
