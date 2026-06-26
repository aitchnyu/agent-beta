<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import { z } from "zod"
import RowDetailsContent from "../RowDetailsContent.vue"
import { RowDetailsProps } from "../../schemas"
import { rowDetailsUrl } from "../../utils/urls"

const PrevNextSlotProps = z.object({
  prev: z.object({ title: z.string(), id: z.number() }).optional(),
  next: z.object({ title: z.string(), id: z.number() }).optional(),
})
type PrevNextSlotProps = z.infer<typeof PrevNextSlotProps>

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- Inertia props are untyped
const { props } = defineProps<{ props: Record<string, any> }>()
const p = RowDetailsProps.parse(props)
const slot = p.slot_props
  ? (PrevNextSlotProps.parse(p.slot_props) as PrevNextSlotProps)
  : ({} as PrevNextSlotProps)
</script>

<template>
  <RowDetailsContent :props="props">
    <template #after-row>
      <div v-if="slot.prev || slot.next" class="row-navigation mt-3">
        <span v-if="slot.prev">
          prev:
          <Link :href="rowDetailsUrl(p.viewname, slot.prev.id)">{{
            slot.prev.title
          }}</Link>
        </span>
        <span v-if="slot.next" class="ms-3">
          next:
          <Link :href="rowDetailsUrl(p.viewname, slot.next.id)">{{
            slot.next.title
          }}</Link>
        </span>
      </div>
    </template>
  </RowDetailsContent>
</template>
