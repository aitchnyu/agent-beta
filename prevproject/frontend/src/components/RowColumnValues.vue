<script setup lang="ts">
import { type PropType, computed } from "vue"
import { RowColumnValueSchema } from "../schemas"
import RenderRawHtml from "./RenderRawHtml.vue"
import ExpandableCell from "./ExpandableCell.vue"
import {
  formatValue,
  isTextField,
  isForeignKey,
  getTextValue,
  getFkData,
} from "../utils/rowUpdate"

import type { z } from "zod"

type ColumnValue = z.infer<typeof RowColumnValueSchema>

const props = defineProps({
  columnValues: {
    type: Array as PropType<ColumnValue[]>,
    required: true,
  },
  action: {
    type: String as PropType<string>,
    required: true,
  },
})

const resolvedRows = computed(() =>
  props.columnValues.map((cv) => ({
    cv,
    fkOld: isForeignKey(cv) ? getFkData(cv, true) : null,
    fkNew: isForeignKey(cv) ? getFkData(cv, false) : null,
  })),
)
</script>

<template>
  <div class="column-values">
    <table v-if="action === 'created_row'" class="column-values-table">
      <thead>
        <tr>
          <th>Field</th>
          <th>New Value</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="{ cv, fkNew } in resolvedRows" :key="cv.name">
          <td class="field-name">{{ cv.name }}</td>
          <td class="field-value">
            <template v-if="isTextField(cv)">
              <ExpandableCell max-height="10rem">
                <RenderRawHtml
                  :html="getTextValue(cv, false)"
                  className="rich-text-display"
                />
              </ExpandableCell>
            </template>
            <template v-else-if="fkNew">
              <a
                v-if="fkNew.url"
                :href="fkNew.url ?? undefined"
                class="fk-link"
              >
                {{ fkNew.title }}
              </a>
              <template v-else>
                {{ fkNew.title }}
              </template>
            </template>
            <template v-else>
              {{ formatValue(cv, false) }}
            </template>
          </td>
        </tr>
      </tbody>
    </table>

    <table v-else class="column-values-table">
      <thead>
        <tr>
          <th>Field</th>
          <th>Old Value</th>
          <th>New Value</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="{ cv, fkOld, fkNew } in resolvedRows" :key="cv.name">
          <td class="field-name">{{ cv.name }}</td>
          <td class="field-old-value">
            <template v-if="isTextField(cv)">
              <ExpandableCell max-height="10rem">
                <RenderRawHtml
                  :html="getTextValue(cv, true)"
                  className="rich-text-display"
                />
              </ExpandableCell>
            </template>
            <template v-else-if="fkOld">
              <a
                v-if="fkOld.url"
                :href="fkOld.url ?? undefined"
                class="fk-link"
              >
                {{ fkOld.title }}
              </a>
              <template v-else>
                {{ fkOld.title }}
              </template>
            </template>
            <template v-else>
              {{ formatValue(cv, true) }}
            </template>
          </td>
          <td class="field-new-value">
            <template v-if="isTextField(cv)">
              <ExpandableCell max-height="10rem">
                <RenderRawHtml
                  :html="getTextValue(cv, false)"
                  className="rich-text-display"
                />
              </ExpandableCell>
            </template>
            <template v-else-if="fkNew">
              <a
                v-if="fkNew.url"
                :href="fkNew.url ?? undefined"
                class="fk-link"
              >
                {{ fkNew.title }}
              </a>
              <template v-else>
                {{ fkNew.title }}
              </template>
            </template>
            <template v-else>
              {{ formatValue(cv, false) }}
            </template>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
