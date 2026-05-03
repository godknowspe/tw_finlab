<script setup>
import { onMounted, ref } from 'vue';
import { createChart, CrosshairMode } from 'lightweight-charts';

const props = defineProps({
  mode: { type: String, default: 'symbol' },
  symbol: String
});

const chartContainer = ref(null);
let chart = null;

onMounted(() => {
  if (!chartContainer.value) return;
  chart = createChart(chartContainer.value, {
    layout: { background: { type: 'solid', color: '#0d1117' }, textColor: '#c9d1d9' },
    grid: { vertLines: { color: '#30363d' }, horzLines: { color: '#30363d' } },
    crosshair: { mode: CrosshairMode.Magnet },
    autoSize: true,
  });
});
</script>
<template>
  <div class="relative w-full h-full">
    <div ref="chartContainer" class="absolute inset-0"></div>
  </div>
</template>
