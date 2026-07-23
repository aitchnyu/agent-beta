<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import HumanizedTime from "../components/HumanizedTime.vue"
import Layout from "../components/Layout.vue"
import { FileViewerPropsSchema } from "../schemas"
import { fileUrl, downloadUrl, formatSize, rawUrl } from "../utils/files"

const props = defineProps<{ props: object }>()
const p = FileViewerPropsSchema.parse(props.props)
</script>

<template>
  <Layout>
    <div class="container files-page">
      <nav class="files-breadcrumb">
        <template v-for="c in p.breadcrumb" :key="c.rel">
          <Link class="files-crumb" :href="fileUrl(c.rel)">{{ c.label }}</Link>
          <span class="files-sep" aria-hidden="true">/</span>
        </template>
      </nav>
      <div class="files-header">
        <h1 class="files-name">{{ p.name }}</h1>
        <p class="text-muted files-meta">
          {{ formatSize(p.size) }} · {{ p.kind }} ·
          <HumanizedTime :ms="p.mtime" />
        </p>
        <!-- Plain anchors (full GETs): downloadUrl → attachment download;
             rawUrl serves bytes inline (real Content-Type) so <img> can render it. -->
        <a
          class="btn btn-sm btn-outline-secondary files-download"
          :href="downloadUrl(p.rel)"
          >Download</a
        >
      </div>
      <!-- Vue interpolation escapes the text, so a file's <script> can't run. -->
      <pre v-if="p.kind === 'text'" class="files-text">{{ p.text }}</pre>
      <img
        v-else-if="p.kind === 'image'"
        :src="rawUrl(p.rel)"
        :alt="p.name"
        class="files-image"
      />
      <p v-else class="text-muted files-binary">
        Binary file — not previewable.
      </p>
    </div>
  </Layout>
</template>
