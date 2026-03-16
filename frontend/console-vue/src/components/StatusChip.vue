<template>
  <span :class="badgeClassByStatus(status)">{{ text }}</span>
</template>

<script setup>
import { computed } from "vue";
import { badgeClassByStatus } from "../lib/constants";

const props = defineProps({
  status: { type: String, default: "" },
  text: { type: String, default: "-" },
});

const text = computed(() => String(props.text || props.status || "-"));
</script>
