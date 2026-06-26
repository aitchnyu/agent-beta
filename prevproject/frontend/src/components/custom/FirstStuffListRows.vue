<script setup lang="ts">
import { z } from "zod"
import ListRowsContent from "../ListRowsContent.vue"
import { ListRowsProps } from "../../schemas"

const SlotProps = z.object({
  row_count: z.number(),
  distinct_integers: z.array(z.number()),
})

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- Inertia props are untyped
const { props } = defineProps<{ props: Record<string, any> }>()
const p = ListRowsProps.parse(props)
const slot = p.slot_props ? SlotProps.parse(p.slot_props) : null
</script>

<template>
  <ListRowsContent :props="props">
    <template #before-table>
      <div v-if="slot" class="card mb-3 hook-firststuff-list">
        <div class="card-body">
          <h5 class="card-title">FirstStuff Stats</h5>
          <p class="card-text">
            Total rows: <strong>{{ slot.row_count }}</strong>
          </p>
          <p class="card-text">
            Distinct integer values:
            <strong>{{ slot.distinct_integers.join(", ") }}</strong>
          </p>
        </div>
      </div>
    </template>
  </ListRowsContent>
</template>
