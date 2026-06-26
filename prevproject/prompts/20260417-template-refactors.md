# v-if Chains with More Than 3 Branches

## 1. ListRows.vue — Filter dispatch (9 branches)

**File:** `frontend/src/pages/ListRows.vue:179-237`

| # | Directive | Condition |
|---|-----------|-----------|
| 1 | `v-if` | `c.discriminator === 'boolean'` → `<BooleanFilter>` |
| 2 | `v-else-if` | `c.discriminator === 'integer' && (c).choices` → `<IntegerChoiceFilterComponent>` |
| 3 | `v-else-if` | `c.discriminator === 'integer' && !(c).choices` → `<IntegerCompareFilterComponent>` |
| 4 | `v-else-if` | `c.discriminator === 'char' && (c).choices` → `<CharChoiceFilterComponent>` |
| 5 | `v-else-if` | `c.discriminator === 'char' && !(c).choices` → `<CharTextFilterComponent>` |
| 6 | `v-else-if` | `c.discriminator === 'text'` → `<CharTextFilterComponent>` |
| 7 | `v-else-if` | `c.discriminator === 'decimal'` → `<DecimalFilter>` |
| 8 | `v-else-if` | `c.discriminator === 'datetime'` → `<DatetimeFilter>` |
| 9 | `v-else-if` | `c.discriminator === 'foreignkey'` → `<ForeignKeyFilter>` |

---

## 2. ListRows.vue — Cell display (5 branches)

**File:** `frontend/src/pages/ListRows.vue:276-305`

| # | Directive | Condition |
|---|-----------|-----------|
| 1 | `v-if` | `column.discriminator === 'foreignkey' && row[column.name]` |
| 2 | `v-else-if` | `column.discriminator === 'boolean'` |
| 3 | `v-else-if` | `column.discriminator === 'file'` |
| 4 | `v-else-if` | `column.discriminator === 'text'` |
| 5 | `v-else` | (default: `{{ row[column.name] }}`) |

---

## 3. FieldDisplay.vue — Field value rendering (9 branches)

**File:** `frontend/src/components/FieldDisplay.vue:37-84`

| # | Directive | Condition |
|---|-----------|-----------|
| 1 | `v-if` | `field.discriminator === 'foreignkey'` |
| 2 | `v-else-if` | `field.discriminator === 'char'` |
| 3 | `v-else-if` | `field.discriminator === 'text'` |
| 4 | `v-else-if` | `field.discriminator === 'integer'` |
| 5 | `v-else-if` | `field.discriminator === 'boolean'` |
| 6 | `v-else-if` | `field.discriminator === 'decimal'` |
| 7 | `v-else-if` | `field.discriminator === 'datetime'` |
| 8 | `v-else-if` | `field.discriminator === 'file'` |
| 9 | `v-else` | (fallback: `cannot handle`) |

---

## 4. FieldInput.vue — Field input widget (8 branches)

**File:** `frontend/src/components/FieldInput.vue:78-244`

| # | Directive | Condition |
|---|-----------|-----------|
| 1 | `v-if` | `field.discriminator === 'text'` → RichTextEditor |
| 2 | `v-else-if` | `field.discriminator === 'char'` → select or input |
| 3 | `v-else-if` | `field.discriminator === 'integer' \|\| 'decimal'` → select or input |
| 4 | `v-else-if` | `field.discriminator === 'boolean'` → checkbox |
| 5 | `v-else-if` | `isDatetime` → datetime-local input |
| 6 | `v-else-if` | `field.discriminator === 'foreignkey'` → ForeignKeyMultiselect |
| 7 | `v-else-if` | `choices` → generic select |
| 8 | `v-else-if` | `field.discriminator === 'file'` → FileUploadWidget |

---

## Summary

| File | Chain location | Branches |
|------|---------------|----------|
| `ListRows.vue:179` | Filter dispatch | 9 |
| `ListRows.vue:276` | Cell display | 5 |
| `FieldDisplay.vue:37` | Value rendering | 9 |
| `FieldInput.vue:78` | Input widget | 8 |
