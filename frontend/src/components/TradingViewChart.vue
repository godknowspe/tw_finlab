<script setup>
import { onMounted, ref, watch, onUnmounted } from 'vue';
import { createChart, CrosshairMode } from 'lightweight-charts';
import axios from 'axios';

const props = defineProps({
  mode: { type: String, default: 'symbol' },
  symbol: String
});

const chartContainer = ref(null);
let chart = null;
let candleSeries = null;
let volumeSeries = null;
let lineSeries = {}; // To store indicators like SMA, MACD, etc.

const initChart = () => {
  if (!chartContainer.value) return;
  
  chart = createChart(chartContainer.value, {
    layout: {
      background: { type: 'solid', color: '#0d1117' },
      textColor: '#c9d1d9',
      fontSize: 11,
      fontFamily: 'Inter, system-ui, sans-serif',
    },
    grid: {
      vertLines: { color: '#30363d' },
      horzLines: { color: '#30363d' },
    },
    crosshair: {
      mode: CrosshairMode.Magnet,
      vertLine: { labelBackgroundColor: '#1f6feb' },
      horzLine: { labelBackgroundColor: '#1f6feb' },
    },
    timeScale: {
      borderColor: '#30363d',
      timeVisible: true,
      secondsVisible: false,
    },
    rightPriceScale: {
      borderColor: '#30363d',
    },
    handleScroll: true,
    handleScale: true,
    autoSize: true,
  });

  candleSeries = chart.addCandlestickSeries({
    upColor: '#3fb950',
    downColor: '#f85149',
    borderVisible: false,
    wickUpColor: '#3fb950',
    wickDownColor: '#f85149',
  });

  volumeSeries = chart.addHistogramSeries({
    color: '#238636',
    priceFormat: { type: 'volume' },
    priceScaleId: '', // Overlay mode
  });

  volumeSeries.priceScale().applyOptions({
    scaleMargins: { top: 0.8, bottom: 0 },
  });
};

const fetchData = async () => {
  if (props.mode === 'symbol' && props.symbol) {
    try {
      const res = await axios.get(`/api/kbars/${props.symbol}`);
      const data = res.data;
      if (!data || data.length === 0) return;

      const candles = data.map(d => ({
        time: d.time,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      }));

      const volumes = data.map(d => ({
        time: d.time,
        value: d.value,
        color: d.close >= d.open ? 'rgba(63, 185, 80, 0.3)' : 'rgba(248, 81, 73, 0.3)',
      }));

      candleSeries.setData(candles);
      volumeSeries.setData(volumes);

      // Add SMA20 if available
      if (data[0].sma20) {
        if (!lineSeries.sma20) {
          lineSeries.sma20 = chart.addLineSeries({ color: '#1f6feb', lineWidth: 1 });
        }
        lineSeries.sma20.setData(data.map(d => ({ time: d.time, value: d.sma20 })));
      }

      chart.timeScale().fitContent();
    } catch (e) {
      console.error('Failed to fetch chart data:', e);
    }
  } else if (props.mode === 'equity') {
    try {
      const res = await axios.get('/api/equity');
      const data = res.data;
      
      // Clear symbol-related series
      if (candleSeries) candleSeries.setData([]);
      if (volumeSeries) volumeSeries.setData([]);
      Object.values(lineSeries).forEach(s => s.setData([]));

      if (!lineSeries.equity) {
        lineSeries.equity = chart.addLineSeries({
          color: '#1f6feb',
          lineWidth: 2,
          title: 'Total Equity',
        });
      }
      lineSeries.equity.setData(data);
      chart.timeScale().fitContent();
    } catch (e) {
      console.error('Failed to fetch equity data:', e);
    }
  }
};

onMounted(() => {
  initChart();
  fetchData();
});

watch(() => props.symbol, () => {
  if (props.mode === 'symbol') fetchData();
});

watch(() => props.mode, () => {
  fetchData();
});

onUnmounted(() => {
  if (chart) {
    chart.remove();
    chart = null;
  }
});
</script>

<template>
  <div class="relative w-full h-full">
    <div ref="chartContainer" class="absolute inset-0"></div>
  </div>
</template>
