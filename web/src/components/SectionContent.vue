<script setup lang="ts">
defineProps<{ section: { heading: string; html: string }; definitions: Record<string, unknown> }>();
</script>
<template><div><h3>{{ section.heading }}</h3></div></template>
