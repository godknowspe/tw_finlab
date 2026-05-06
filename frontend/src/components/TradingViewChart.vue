<script setup>
import { onMounted, ref, watch, onUnmounted } from 'vue';
import { createChart, CrosshairMode } from 'lightweight-charts';
import { useMarketStore } from '@/stores/market';
import { usePortfolioStore } from '@/stores/portfolio';
import axios from 'axios';

const props = defineProps({
  mode: { type: String, default: 'symbol' },
  symbol: String
});

const marketStore = useMarketStore();
const portfolioStore = usePortfolioStore();
const chartContainer = ref(null);
const showEqTotal = ref(true);
const showEqTW = ref(true);
const showEqUS = ref(true);

const toggleEquityLine = (type) => {
  if (type === 'Total') {
    showEqTotal.value = !showEqTotal.value;
    if (equityTotalSeries) equityTotalSeries.applyOptions({ visible: showEqTotal.value });
  } else if (type === 'TW') {
    showEqTW.value = !showEqTW.value;
    if (equityTWSeries) equityTWSeries.applyOptions({ visible: showEqTW.value });
  } else if (type === 'US') {
    showEqUS.value = !showEqUS.value;
    if (equityUSSeries) equityUSSeries.applyOptions({ visible: showEqUS.value });
  }
};

const legendPos = ref({ x: 12, y: 12 });
const isLegendExpanded = ref(true);
let isDragging = false;
let dragOffset = { x: 0, y: 0 };

const startDrag = (e) => {
  isDragging = true;
  dragOffset.x = e.clientX - legendPos.value.x;
  dragOffset.y = e.clientY - legendPos.value.y;
  document.addEventListener('mousemove', doDrag);
  document.addEventListener('mouseup', stopDrag);
};

const doDrag = (e) => {
  if (!isDragging) return;
  const newX = Math.max(0, e.clientX - dragOffset.x);
  const newY = Math.max(0, e.clientY - dragOffset.y);
  legendPos.value = { x: newX, y: newY };
};

const stopDrag = () => {
  isDragging = false;
  document.removeEventListener('mousemove', doDrag);
  document.removeEventListener('mouseup', stopDrag);
};

const legendData = ref({
  time: '--', open: '--', high: '--', low: '--', close: '--', v: '--', indicators: {}
});

let chart = null;
let candleSeries = null;
let volumeSeries = null;
let equityTotalSeries = null;
let equityTWSeries = null;
let equityUSSeries = null;
let pnlSeries = null;
let backtestLineSeries = null;
let indicatorSeries = {}; 
let lastValidData = null;

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
      mode: CrosshairMode.Normal,
      vertLine: { labelBackgroundColor: '#1f6feb' },
      horzLine: { labelBackgroundColor: '#1f6feb' },
    },
    timeScale: { borderColor: '#30363d', timeVisible: true },
    rightPriceScale: { borderColor: '#30363d', autoScale: true },
    leftPriceScale: { borderColor: '#30363d', visible: false },
    handleScroll: true,
    handleScale: true,
    autoSize: true,
  });

  candleSeries = chart.addCandlestickSeries({
    upColor: '#3fb950', downColor: '#f85149', borderVisible: false,
    wickUpColor: '#3fb950', wickDownColor: '#f85149',
  });

  volumeSeries = chart.addHistogramSeries({
    color: '#238636', priceFormat: { type: 'volume' }, priceScaleId: '',
  });

  volumeSeries.priceScale().applyOptions({
    scaleMargins: { top: 0.8, bottom: 0 },
  });

  chart.subscribeCrosshairMove(param => {
    if (!param || !param.time || param.point.x < 0 || param.point.y < 0) {
      if (lastValidData) legendData.value = lastValidData;
      return;
    }
    
    if (!param.seriesPrices) return;

    const mainData = param.seriesPrices.get(candleSeries);
    if (mainData) {
      let timeStr = '';
      if (typeof param.time === 'string') timeStr = param.time;
      else if (typeof param.time === 'number') timeStr = new Date(param.time * 1000).toLocaleDateString();
      else if (param.time.year) timeStr = `${param.time.year}-${String(param.time.month).padStart(2, '0')}-${String(param.time.day).padStart(2, '0')}`;

      const newLegend = {
        time: timeStr, open: mainData.open?.toFixed(2), high: mainData.high?.toFixed(2),
        low: mainData.low?.toFixed(2), close: mainData.close?.toFixed(2), indicators: {}
      };

      const vol = param.seriesPrices.get(volumeSeries);
      if (vol !== undefined) newLegend.v = (vol / 1000).toFixed(0) + 'K';

      for (const [id, series] of Object.entries(indicatorSeries)) {
        const val = param.seriesPrices.get(series);
        if (val !== undefined && val !== null) newLegend.indicators[id] = val.toFixed(2);
      }
      
      if (pnlSeries) {
        const pVal = param.seriesPrices.get(pnlSeries);
        if (pVal !== undefined && pVal !== null) newLegend.indicators['PnL'] = pVal.toFixed(0);
      }
      
      if (backtestLineSeries) {
        const bVal = param.seriesPrices.get(backtestLineSeries);
        if (bVal !== undefined && bVal !== null) newLegend.indicators['BT Equity'] = bVal.toFixed(0);
      }

      legendData.value = newLegend;
    }
  });
};

const clearIndicators = () => {
  for (const series of Object.values(indicatorSeries)) { chart.removeSeries(series); }
  indicatorSeries = {};
  if (pnlSeries) { chart.removeSeries(pnlSeries); pnlSeries = null; }
  if (backtestLineSeries) { chart.removeSeries(backtestLineSeries); backtestLineSeries = null; }
  chart.applyOptions({ leftPriceScale: { visible: false } });
};

const fetchData = async () => {
  if (!chart) return;
  if (props.mode === 'symbol' && props.symbol) {
    try {
      const res = await axios.get(`/api/kbars/${props.symbol}`, { params: { interval: marketStore.currentInterval, t: Date.now() } });
      const data = res.data;
      if (!data || data.length === 0) return;

      const candles = data.map(d => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close }));
      const volumes = data.map(d => ({ time: d.time, value: d.value, color: d.close >= d.open ? 'rgba(63, 185, 80, 0.3)' : 'rgba(248, 81, 73, 0.3)' }));

      candleSeries.setData(candles);
      volumeSeries.setData(volumes);
      
      clearIndicators();
      const colors = { SMA5: '#f2c94c', SMA10: '#f2994a', SMA20: '#1f6feb', BB: '#9b51e0', RSI: '#56ccf2', MACD: '#2962FF' };

      marketStore.selectedIndicators.forEach(id => {
        const key = id.toLowerCase();
        if (id === 'BB' && data[0].bb_up !== undefined) {
          indicatorSeries['BB Up'] = chart.addLineSeries({ color: colors.BB, lineWidth: 1, lineStyle: 2, priceLineVisible: false });
          indicatorSeries['BB Low'] = chart.addLineSeries({ color: colors.BB, lineWidth: 1, lineStyle: 2, priceLineVisible: false });
          indicatorSeries['BB Mid'] = chart.addLineSeries({ color: '#56ccf2', lineWidth: 1, priceLineVisible: false });
          indicatorSeries['BB Up'].setData(data.map(d => ({ time: d.time, value: d.bb_up })));
          indicatorSeries['BB Low'].setData(data.map(d => ({ time: d.time, value: d.bb_low })));
          indicatorSeries['BB Mid'].setData(data.map(d => ({ time: d.time, value: d.bb_mid })));
        } else if (id === 'MACD' && data[0].macd !== undefined) {
          chart.applyOptions({ leftPriceScale: { visible: true, scaleMargins: { top: 0.75, bottom: 0.05 } } });
          indicatorSeries['MACD'] = chart.addLineSeries({ color: colors.MACD, lineWidth: 1, priceScaleId: 'left', priceLineVisible: false });
          indicatorSeries['Signal'] = chart.addLineSeries({ color: '#FF6D00', lineWidth: 1, priceScaleId: 'left', priceLineVisible: false });
          indicatorSeries['MACD'].setData(data.map(d => ({ time: d.time, value: d.macd })));
          indicatorSeries['Signal'].setData(data.map(d => ({ time: d.time, value: d.signal })));
        } else if (id === 'RSI' && data[0].rsi !== undefined) {
          chart.applyOptions({ leftPriceScale: { visible: true, scaleMargins: { top: 0.75, bottom: 0.05 } } });
          indicatorSeries['RSI'] = chart.addLineSeries({ color: colors.RSI, lineWidth: 1, priceScaleId: 'left', priceLineVisible: false });
          indicatorSeries['RSI'].setData(data.map(d => ({ time: d.time, value: d.rsi })));
        } else if (data[0][key] !== undefined) {
          indicatorSeries[id] = chart.addLineSeries({ color: colors[id] || '#56ccf2', lineWidth: 1, priceLineVisible: false });
          indicatorSeries[id].setData(data.map(d => ({ time: d.time, value: d[key] })));
        }
      });

      
      let markers = [];
      if (marketStore.backtestEnabled && marketStore.backtestResults) {
        // BACKTEST MODE
        const btTrades = marketStore.backtestResults.trades;
        let validBtMarkers = [];
        btTrades.forEach(t => {
           const tradeTimeMs = typeof t.time === 'number' ? t.time * 1000 : new Date(t.time).getTime();
           let closestCandle = null;
           let minDiff = Infinity;
           for (const d of data) {
             const candleTimeMs = typeof d.time === 'number' ? d.time * 1000 : new Date(d.time).getTime();
             const diff = Math.abs(candleTimeMs - tradeTimeMs);
             if (diff < minDiff) { minDiff = diff; closestCandle = d; }
           }
           if (closestCandle) {
             validBtMarkers.push({
               time: closestCandle.time,
               position: t.side === 'buy' ? 'belowBar' : 'aboveBar',
               color: t.side === 'buy' ? '#3fb950' : '#f85149',
               shape: t.side === 'buy' ? 'arrowUp' : 'arrowDown',
               text: 'BT ' + t.side.toUpperCase()
             });
           }
        });
        markers = validBtMarkers;

        
        if (marketStore.backtestResults.chart_data?.length > 0) {
          chart.applyOptions({ leftPriceScale: { visible: true, scaleMargins: { top: 0.1, bottom: 0.7 } } });
          backtestLineSeries = chart.addLineSeries({ color: '#f2c94c', lineWidth: 2, priceScaleId: 'left', title: 'BT Equity', priceLineVisible: false });
          backtestLineSeries.setData(marketStore.backtestResults.chart_data);
        }
      } else {
        
        // REAL PORTFOLIO MODE
        const actualTrades = portfolioStore.trades.filter(t => t.symbol === props.symbol);
        
        // We need to map trade timestamps to the EXACT candle time
        // If data is minute/hourly, data[i].time is a UNIX timestamp (number)
        // If daily, it's a string 'YYYY-MM-DD'
        
        let validMarkers = [];
        actualTrades.forEach(t => {
           // Find the closest candle for this trade
           const tradeTimeMs = new Date(t.timestamp).getTime();
           
           let closestCandle = null;
           let minDiff = Infinity;
           
           for (const d of data) {
             const candleTimeMs = typeof d.time === 'number' ? d.time * 1000 : new Date(d.time).getTime();
             const diff = Math.abs(candleTimeMs - tradeTimeMs);
             if (diff < minDiff) {
               minDiff = diff;
               closestCandle = d;
             }
           }
           
           if (closestCandle) {
             const existingMarker = validMarkers.find(m => m.time === closestCandle.time && m.originalAction === t.action);
             if (existingMarker) {
               existingMarker.shares += t.shares;
               existingMarker.text = `${t.action === 'BUY' ? 'B' : 'S'} ${existingMarker.shares}`;
             } else {
               validMarkers.push({
                 time: closestCandle.time,
                 originalAction: t.action,
                 position: t.action === 'BUY' ? 'belowBar' : 'aboveBar',
                 color: t.action === 'BUY' ? '#3fb950' : '#f85149',
                 shape: t.action === 'BUY' ? 'arrowUp' : 'arrowDown',
                 shares: t.shares,
                 text: `${t.action === 'BUY' ? 'B' : 'S'} ${t.shares}`
               });
             }
           }
        });
        
        // Remove the temporary 'originalAction' and 'shares' properties before passing to Lightweight Charts
        markers = validMarkers.map(m => ({
          time: m.time,
          position: m.position,
          color: m.color,
          shape: m.shape,
          text: m.text
        }));

        const pnlData = data.filter(d => d.total_pnl !== undefined && d.total_pnl !== null).map(d => ({ time: d.time, value: d.total_pnl }));
        if (pnlData.length > 0) {
            chart.applyOptions({ leftPriceScale: { visible: true, scaleMargins: { top: 0.1, bottom: 0.7 } } });
            pnlSeries = chart.addLineSeries({ color: '#ff7eb9', lineWidth: 2, priceScaleId: 'left', title: 'PnL', priceLineVisible: false });
            pnlSeries.setData(pnlData);
        }
      }

      markers.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
      candleSeries.setMarkers(markers);

      if (equityTotalSeries) { chart.removeSeries(equityTotalSeries); equityTotalSeries = null; }
      if (equityTWSeries) { chart.removeSeries(equityTWSeries); equityTWSeries = null; }
      if (equityUSSeries) { chart.removeSeries(equityUSSeries); equityUSSeries = null; }
      const barsToDisplay = 120;
      if (data.length > barsToDisplay) {
        chart.timeScale().setVisibleRange({ from: data[data.length - barsToDisplay].time, to: data[data.length - 1].time });
      } else { chart.timeScale().fitContent(); }

      const last = data[data.length - 1];
      const initialIndicators = {};
      Object.keys(indicatorSeries).forEach(id => {
         let val = last[id.toLowerCase().replace(' ', '_')];
         if (id === 'BB Up') val = last.bb_up; if (id === 'BB Low') val = last.bb_low; if (id === 'BB Mid') val = last.bb_mid;
         if (id === 'Signal') val = last.signal;
         if (val !== undefined && val !== null) initialIndicators[id] = val.toFixed(2);
      });
      if (last.total_pnl !== undefined && last.total_pnl !== null) initialIndicators['PnL'] = last.total_pnl.toFixed(0);
      lastValidData = {
        time: last.time, open: last.open.toFixed(2), high: last.high.toFixed(2), low: last.low.toFixed(2), close: last.close.toFixed(2),
        v: (last.value/1000).toFixed(0) + 'K', indicators: initialIndicators
      };
      legendData.value = lastValidData;
    } catch (e) { console.error('Fetch Error:', e); }
  } else if (props.mode === 'equity') {
    try {
      const res = await axios.get('/api/equity');
      const data = res.data;
      candleSeries.setData([]); volumeSeries.setData([]); clearIndicators();
      if (!equityTotalSeries) equityTotalSeries = chart.addLineSeries({ color: '#f2c94c', lineWidth: 3, title: 'Total' });
      if (!equityTWSeries) equityTWSeries = chart.addLineSeries({ color: '#1f6feb', lineWidth: 2, title: 'TW (TWD)' });
      if (!equityUSSeries) equityUSSeries = chart.addLineSeries({ color: '#f87171', lineWidth: 2, title: 'US (USD)' });
      
      if (data.total && data.total.length) equityTotalSeries.setData(data.total);
      if (data.tw && data.tw.length) equityTWSeries.setData(data.tw);
      if (data.us && data.us.length) equityUSSeries.setData(data.us);
      
      chart.timeScale().fitContent();
    } catch (e) { console.error('Equity Error:', e); }
  }
};

onMounted(() => { initChart(); fetchData(); });
watch(() => [props.symbol, props.mode, marketStore.currentInterval, marketStore.selectedIndicators, marketStore.backtestEnabled, portfolioStore.trades], () => fetchData(), { deep: true });
onUnmounted(() => { if (chart) chart.remove(); });
</script>

<template>
  <div class="relative w-full h-full select-none overflow-hidden">
    <div ref="chartContainer" class="absolute inset-0"></div>
    
    <!-- Equity Controls -->
    <div v-if="mode === 'equity'" class="absolute top-4 right-4 z-20 flex gap-2">
      <button @click="toggleEquityLine('Total')" :class="showEqTotal ? 'bg-yellow-500/20 text-yellow-500 border-yellow-500' : 'bg-gray-800 text-gray-500 border-gray-700'" class="px-2 py-1 text-xs font-bold border rounded transition-colors cursor-pointer select-none">Total</button>
      <button @click="toggleEquityLine('TW')" :class="showEqTW ? 'bg-blue-500/20 text-blue-500 border-blue-500' : 'bg-gray-800 text-gray-500 border-gray-700'" class="px-2 py-1 text-xs font-bold border rounded transition-colors cursor-pointer select-none">TW (TWD)</button>
      <button @click="toggleEquityLine('US')" :class="showEqUS ? 'bg-red-500/20 text-red-500 border-red-500' : 'bg-gray-800 text-gray-500 border-gray-700'" class="px-2 py-1 text-xs font-bold border rounded transition-colors cursor-pointer select-none">US (USD)</button>
    </div>
    <div :style="{ top: legendPos.y + 'px', left: legendPos.x + 'px' }" class="absolute bg-black/80 backdrop-blur-md border border-white/10 p-3 rounded-lg text-[11px] z-20 shadow-2xl flex flex-col gap-2 min-w-[220px] transition-opacity hover:opacity-100 opacity-90">
      <div @mousedown.prevent="startDrag" class="flex justify-between items-center border-b border-white/10 pb-1.5 cursor-move" title="Drag to move">
        <div class="flex items-center gap-2">
          <span class="text-white font-bold uppercase tracking-wider">{{ symbol }}</span>
          <span class="text-gray-500 font-mono">{{ legendData.time }}</span>
        </div>
        <button @mousedown.stop @click="isLegendExpanded = !isLegendExpanded" class="text-gray-500 hover:text-white px-1.5 py-0.5 rounded bg-white/5 cursor-pointer z-30">
          {{ isLegendExpanded ? '−' : '+' }}
        </button>
      </div>
      <div v-show="isLegendExpanded" class="flex flex-col gap-2">
        <div class="grid grid-cols-2 gap-x-4 gap-y-1.5">
          <div class="flex justify-between items-center"><span class="text-gray-500 text-[10px]">OPEN</span><span class="text-white font-mono">{{ legendData.open }}</span></div>
          <div class="flex justify-between items-center"><span class="text-gray-500 text-[10px]">HIGH</span><span class="text-white font-mono">{{ legendData.high }}</span></div>
          <div class="flex justify-between items-center"><span class="text-gray-500 text-[10px]">LOW</span><span class="text-white font-mono">{{ legendData.low }}</span></div>
          <div class="flex justify-between items-center"><span class="text-gray-500 text-[10px]">CLOSE</span><span :class="legendData.close >= legendData.open ? 'text-text-green' : 'text-text-red'" class="font-mono font-bold text-sm">{{ legendData.close }}</span></div>
          <div class="flex justify-between col-span-2 border-t border-white/10 pt-1.5 mt-0.5">
             <span class="text-gray-500 text-[10px]">VOLUME</span><span class="text-gray-300 font-mono">{{ legendData.v }}</span>
          </div>
        </div>
        <div v-if="Object.keys(legendData.indicators || {}).length > 0" class="border-t border-white/10 pt-1.5 mt-0.5 grid grid-cols-1 gap-1">
          <div v-for="(val, id) in legendData.indicators" :key="id" class="flex justify-between items-center">
            <span class="text-gray-500 text-[9px] uppercase tracking-tighter">{{ id.replace('_', ' ') }}</span>
            <span :class="id.includes('PnL') ? (parseFloat(val) >= 0 ? 'text-text-green' : 'text-text-red') : 'text-blue-400'" class="font-mono font-bold">{{ val }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
